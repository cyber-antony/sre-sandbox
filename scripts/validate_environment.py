#!/usr/bin/env python3
"""Validate the environment JSON supplied by the local Ansible preflight."""

import ipaddress
import json
import re
import sys
from urllib.parse import urlparse


def validate(site):
    lan = ipaddress.IPv4Network(site['lab']['lan_cidr'])
    cluster = ipaddress.IPv4Network(site['cluster']['cidr'])
    if lan.overlaps(cluster):
        raise ValueError('LAN and cluster networks must not overlap')

    def host(value, network):
        address = ipaddress.IPv4Address(value)
        if address not in network or address in (network.network_address, network.broadcast_address):
            raise ValueError(f'{value} must be a usable host address in {network}')
        return address

    addresses = [host(site['lab']['address'], lan), host(site['mainhost']['address'], lan),
                 host(site['cluster']['gateway'], cluster)]
    nodes = site['cluster']['nodes']
    if sorted(node['name'] for node in nodes) != ['cc1', 'wk1', 'wk2']:
        raise ValueError('The inventory expects exactly cc1, wk1, and wk2')
    macs = []
    for node in nodes:
        addresses.append(host(node['ip'], cluster))
        expected_role = 'control_plane' if node['name'] == 'cc1' else 'worker'
        if node['role'] != expected_role:
            raise ValueError(f"{node['name']} must have role {expected_role}")
    if len(set(addresses)) != len(addresses):
        raise ValueError('Host and gateway addresses must be unique')
    if not site['cluster']['dns']:
        raise ValueError('At least one DNS server is required')
    for address in site['cluster']['dns']:
        ipaddress.IPv4Address(address)
    for vm in [site['mainhost'], *nodes]:
        for key in ('memory_mb', 'disk_gb'):
            if type(vm[key]) is not int or vm[key] <= 0:
                raise ValueError(f'{key} must be a positive integer')
        cpu = vm['vcpus'] if vm is site['mainhost'] else vm['vcpu']
        if type(cpu) is not int or cpu <= 0:
            raise ValueError('VM CPU counts must be positive integers')
        if 'mac' in vm:
            mac = vm['mac'].lower()
            if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', mac):
                raise ValueError('Invalid optional VM MAC address')
            if int(mac[:2], 16) & 1:
                raise ValueError('VM MAC addresses must be unicast')
            macs.append(mac)
    if len(set(macs)) != len(macs):
        raise ValueError('Optional VM MAC addresses must be unique')
    for interface in (site['lab']['uplink'], site['lab']['bridge'], site['cluster']['bridge']):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,15}', interface):
            raise ValueError('Invalid network interface name')
    if site['lab']['uplink'] == site['lab']['bridge']:
        raise ValueError('The physical uplink and bridge must have different names')
    paths = [site['images']['directory'], site['images']['mount'],
             site['postgres']['directory'], site['mainhost']['runtime_dir']]
    for path in paths:
        if not re.fullmatch(r'/[A-Za-z0-9_./-]+', path) or '..' in path.split('/'):
            raise ValueError('Storage paths must be absolute and contain no spaces or parent traversal')
    image_dir, _, postgres_dir, _ = [p.rstrip('/') for p in paths]
    if image_dir == postgres_dir or image_dir.startswith(postgres_dir + '/') or postgres_dir.startswith(image_dir + '/'):
        raise ValueError('Image and PostgreSQL exports must be separate directories')
    if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*', site['images']['filename']):
        raise ValueError('The image filename must be a plain filename')
    for label, value in [('proxy', site['apt_proxy']['url']), ('image source', site['images']['url'])]:
        url = urlparse(value)
        if url.scheme not in ('http', 'https') or not url.hostname:
            raise ValueError(f'The {label} URL must use HTTP or HTTPS')
    for mapping, key in [(site['apt_proxy'], 'manage_on_lab'), (site['images'], 'download')]:
        if type(mapping[key]) is not bool:
            raise ValueError(f'{key} must be true or false')
    if site['apt_proxy']['manage_on_lab']:
        proxy = urlparse(site['apt_proxy']['url'])
        if proxy.scheme != 'http' or proxy.hostname != site['lab']['address'] or proxy.port != 3142:
            raise ValueError('A managed local proxy must use http://<lab-address>:3142; use manage_on_lab: false for an external proxy')


if __name__ == '__main__':
    try:
        validate(json.load(sys.stdin)['site'])
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        print(f'Invalid environment configuration: {error}', file=sys.stderr)
        sys.exit(1)
    print('Environment configuration is valid.')
