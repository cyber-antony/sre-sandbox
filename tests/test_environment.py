"""Portability checks for the public example and environment validation."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate_environment', ROOT / 'scripts/validate_environment.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.site = yaml.safe_load((ROOT / 'ansible/environment.example.yml').read_text())['site']

    def test_example_works_without_mac_addresses(self):
        validator.validate(self.site)
        self.assertNotIn('mac', self.site['mainhost'])
        self.assertTrue(all('mac' not in node for node in self.site['cluster']['nodes']))

    def test_different_networks_and_storage_paths(self):
        self.site['lab'].update(address='172.20.8.2', lan_cidr='172.20.8.0/24', uplink='eno2')
        self.site['apt_proxy']['url'] = 'http://172.20.8.2:3142'
        self.site['mainhost'].update(address='172.20.8.9', runtime_dir='/data/runtime')
        self.site['cluster'].update(cidr='172.20.9.0/24', gateway='172.20.9.1', dns=['172.20.8.1'])
        self.site['images'].update(directory='/data/images', mount='/mnt/base-images', filename='ubuntu.qcow2')
        self.site['postgres']['directory'] = '/data/postgres'
        for index, node in enumerate(self.site['cluster']['nodes'], 20):
            node['ip'] = f'172.20.9.{index}'
        validator.validate(self.site)

    def test_invalid_environments_are_rejected(self):
        cases = [
            ('overlap', lambda s: s['cluster'].update(cidr=s['lab']['lan_cidr'])),
            ('outside subnet', lambda s: s['cluster']['nodes'][0].update(ip='203.0.113.8')),
            ('duplicate address', lambda s: s['mainhost'].update(address=s['lab']['address'])),
            ('network address', lambda s: s['lab'].update(address='10.20.0.0')),
            ('missing node', lambda s: s['cluster']['nodes'].pop()),
            ('wrong role', lambda s: s['cluster']['nodes'][0].update(role='worker')),
            ('multicast MAC', lambda s: s['mainhost'].update(mac='01:00:00:00:00:08')),
            ('duplicate MAC', lambda s: [n.update(mac='02:00:00:00:00:08') for n in s['cluster']['nodes']]),
            ('unsafe path', lambda s: s['mainhost'].update(runtime_dir='/data/../')),
            ('shared exports', lambda s: s['postgres'].update(directory=s['images']['directory'])),
            ('bad proxy URL', lambda s: s['apt_proxy'].update(url='proxy-without-scheme')),
            ('wrong local proxy host', lambda s: s['apt_proxy'].update(url='http://10.20.0.100:3142')),
            ('wrong local proxy port', lambda s: s['apt_proxy'].update(url='http://10.20.0.2:8080')),
            ('string boolean', lambda s: s['images'].update(download='false')),
        ]
        for name, mutate in cases:
            with self.subTest(name=name):
                changed = deepcopy(self.site)
                mutate(changed)
                with self.assertRaises((ValueError, KeyError, TypeError)):
                    validator.validate(changed)

    def test_existing_external_proxy_is_supported(self):
        self.site['apt_proxy'].update(manage_on_lab=False, url='http://10.20.0.100:8080')
        validator.validate(self.site)


if __name__ == '__main__':
    unittest.main()
