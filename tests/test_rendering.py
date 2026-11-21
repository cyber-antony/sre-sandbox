"""Render real Ansible configuration locally for two unrelated environments."""

from copy import deepcopy
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
ANSIBLE = shutil.which('ansible-playbook')


def load(path):
    return yaml.safe_load((ROOT / path).read_text())


@unittest.skipUnless(ANSIBLE, 'ansible-playbook is required for rendering checks')
class RenderingTests(unittest.TestCase):
    def test_two_environments(self):
        example = load('ansible/environment.example.yml')
        alternate = deepcopy(example)
        site = alternate['site']
        site['lab'].update(address='172.20.8.2', lan_cidr='172.20.8.0/24', uplink='eno2', bridge='br-lan')
        site['apt_proxy'].update(url='http://172.20.8.100:3142', manage_on_lab=False)
        site['mainhost'].update(address='172.20.8.9', runtime_dir='/data/runtime', mac='02:00:00:00:00:08')
        site['cluster'].update(cidr='172.20.9.0/24', gateway='172.20.9.1', dns=['172.20.8.1'], bridge='br-cluster')
        site['images'].update(directory='/data/images', mount='/mnt/base-images', filename='ubuntu.qcow2')
        site['postgres']['directory'] = '/data/postgres'
        for index, node in enumerate(site['cluster']['nodes'], 20):
            node.update(ip=f'172.20.9.{index}', mac=f'02:00:00:00:00:{index}')
        for environment in (example, alternate):
            with self.subTest(lan=environment['site']['lab']['lan_cidr']):
                self.render_and_check(environment)

    def render_and_check(self, environment):
        site = environment['site']
        defaults = {}
        roles = ('common', 'lab_bridge', 'lab_nfs_server', 'lab_vm_image_cache',
                 'mh_cluster_network', 'mh_k3s_cloud_init', 'mh_k3s_vm_disks', 'mh_nfs_client')
        for role in roles:
            defaults.update(load(f'ansible/roles/{role}/defaults/main.yml'))
        defaults.update(load('ansible/inventories/prod/group_vars/mainhosts.yml'))
        provision = load('ansible/playbooks/20-lab-create-mainhost.yml')[0]
        mainhost_command = next(t['ansible.builtin.command'] for t in provision['tasks'] if t['name'] == 'Create mainhost VM with virt-install')
        node_command = next(t['ansible.builtin.command']['cmd'] for t in load('ansible/roles/mh_k3s_vm_create/tasks/main.yml') if t['name'] == 'Create VMs with virt-install')
        bridge = next(t['ansible.builtin.copy']['content'] for t in load('ansible/roles/lab_bridge/tasks/main.yml') if 'ansible.builtin.copy' in t)
        cluster_bridge = next(t['ansible.builtin.copy']['content'] for t in load('ansible/roles/mh_cluster_network/tasks/main.yml') if 'ansible.builtin.copy' in t)
        exports = next(t['ansible.builtin.copy']['content'] for t in load('ansible/roles/lab_nfs_server/tasks/main.yml') if 'ansible.builtin.copy' in t)
        with tempfile.TemporaryDirectory(prefix='sre-render-') as directory:
            tmp = Path(directory)
            sources = {
                'mainhost-command': (mainhost_command, {**provision['vars'], 'ssh_key': 'test-key'}),
                'node-command': (node_command, {'item': {'item': site['cluster']['nodes'][0]}, 'vm_os_variant': 'ubuntu24.04'}),
                'lab-netplan': (bridge, {}),
                'cluster-netplan': (cluster_bridge, {'cluster_bridge_optional': True}),
                'exports': (exports, {}),
                'node-network': ((ROOT / 'ansible/roles/mh_k3s_cloud_init/templates/network-config.j2').read_text(), {'item': site['cluster']['nodes'][0]}),
                'node-user': ((ROOT / 'ansible/roles/mh_k3s_cloud_init/templates/user-data.j2').read_text(), {'item': site['cluster']['nodes'][0], 'ssh_pubkey_file': str(tmp / 'key.pub')}),
                'storage': ((ROOT / 'k8s/taskmanager/04-postgres-storage.yaml').read_text(), {}),
                'endpoint': ('{{ hostvars[groups["control_plane"][0]].ansible_host }}', {}),
            }
            (tmp / 'key.pub').write_text('ssh-ed25519 AAAATEST test\n')
            (tmp / 'variables.yml').write_text(yaml.safe_dump({**defaults, **environment}))
            tasks = []
            for name, (source, context) in sources.items():
                (tmp / f'{name}.j2').write_text(source)
                tasks.append({'name': f'Render {name}', 'ansible.builtin.template': {
                    'src': str(tmp / f'{name}.j2'), 'dest': str(tmp / name), 'mode': '0600'}, 'vars': context})
            play = [{'name': 'Render portability fixtures', 'hosts': 'localhost', 'connection': 'local',
                     'gather_facts': False, 'vars_files': [str(tmp / 'variables.yml')], 'tasks': tasks}]
            (tmp / 'render.yml').write_text(yaml.safe_dump(play, sort_keys=False))
            result = subprocess.run([ANSIBLE, '-i', 'localhost,', '-i', str(ROOT / 'ansible/inventories/global_hosts.yml'),
                                     '-e', '@' + str(tmp / 'variables.yml'), str(tmp / 'render.yml')],
                                    capture_output=True, text=True, env=os.environ.copy())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            mainhost = (tmp / 'mainhost-command').read_text()
            node = (tmp / 'node-command').read_text()
            self.assertIn(f"bridge={site['lab']['bridge']},model=virtio", mainhost)
            self.assertIn(f"bridge={site['cluster']['bridge']},model=virtio", node)
            for command, vm in ((mainhost, site['mainhost']), (node, site['cluster']['nodes'][0])):
                self.assertEqual('mac=' in command, 'mac' in vm)
                if 'mac' in vm:
                    self.assertIn('mac=' + vm['mac'], command)
            network = yaml.safe_load((tmp / 'node-network').read_text())['ethernets']['cluster0']
            self.assertEqual(network['addresses'], [site['cluster']['nodes'][0]['ip'] + '/' + site['cluster']['cidr'].split('/')[1]])
            self.assertEqual(network['routes'][0]['via'], site['cluster']['gateway'])
            self.assertEqual(network['nameservers']['addresses'], site['cluster']['dns'])
            self.assertEqual(network['match'], {'macaddress': site['cluster']['nodes'][0]['mac']} if 'mac' in site['cluster']['nodes'][0] else {'name': 'e*'})
            self.assertEqual(yaml.safe_load((tmp / 'node-user').read_text())['apt']['proxy'], site['apt_proxy']['url'])
            storage = list(yaml.safe_load_all((tmp / 'storage').read_text()))[0]
            self.assertEqual(storage['spec']['nfs'], {'server': site['lab']['address'], 'path': site['postgres']['directory']})
            self.assertEqual((tmp / 'endpoint').read_text().strip(), site['cluster']['nodes'][0]['ip'])
            self.assertIn(site['images']['directory'] + ' ' + site['lab']['lan_cidr'], (tmp / 'exports').read_text())
            self.assertIn(site['postgres']['directory'] + ' ' + site['cluster']['cidr'], (tmp / 'exports').read_text())
            lab_bridge = yaml.safe_load((tmp / 'lab-netplan').read_text())['network']['bridges'][site['lab']['bridge']]
            self.assertTrue(lab_bridge['dhcp4'])
            self.assertEqual(lab_bridge['routes'], [{'to': site['cluster']['cidr'], 'via': site['mainhost']['address']}])
            for name in sources:
                rendered = (tmp / name).read_text()
                self.assertNotIn('{{', rendered)


if __name__ == '__main__':
    unittest.main()
