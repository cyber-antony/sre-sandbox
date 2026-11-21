"""Exercise bootstrap ordering with fake package commands and a local TCP listener."""

from copy import deepcopy
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
ANSIBLE = shutil.which('ansible-playbook')


class DirectAptTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('apt-config'), 'APT tools are required')
    def test_old_proxy_configuration_is_overridden_without_editing_it(self):
        options = yaml.safe_load((ROOT / 'ansible/roles/lab_apt_proxy/defaults/main.yml').read_text())['lab_apt_proxy_direct_apt'][1:]
        with tempfile.TemporaryDirectory(prefix='sre-apt-config-') as directory:
            config = Path(directory) / '01proxy'
            stale = 'Acquire::http::Proxy "http://127.0.0.1:1";\nAcquire::https::Proxy "http://127.0.0.1:1";\n'
            config.write_text(stale)
            env = {**os.environ, 'APT_CONFIG': str(config)}
            result = subprocess.run(['apt-config', *options, 'dump'], env=env, capture_output=True, text=True, check=True)
            self.assertIn('Acquire::http::Proxy "DIRECT";', result.stdout)
            self.assertIn('Acquire::https::Proxy "DIRECT";', result.stdout)
            self.assertEqual(config.read_text(), stale)


@unittest.skipUnless(ANSIBLE, 'ansible-playbook is required for bootstrap checks')
class ProxyBootstrapTests(unittest.TestCase):
    def test_clean_host_stale_client_and_stopped_service(self):
        for scenario in ('clean', 'stale-client', 'installed-but-stopped', 'external-proxy'):
            with self.subTest(scenario=scenario):
                self.run_scenario(scenario)

    def run_scenario(self, scenario):
        with tempfile.TemporaryDirectory(prefix='sre-proxy-test-') as directory, socket.socket() as listener:
            tmp = Path(directory)
            listener.bind(('127.0.0.1', 0))
            listener.listen(5)
            binaries = tmp / 'bin'
            binaries.mkdir()
            fake = '''#!/usr/bin/env python3
import os
from pathlib import Path
import sys
root = Path(os.environ['SRE_PROXY_TEST_ROOT'])
name = Path(sys.argv[0]).name
args = sys.argv[1:]
def event(value):
    with (root / 'events').open('a') as stream:
        stream.write(value + '\\n')
if name == 'dpkg-query':
    assert '--showformat=${db:Status-Status}' in args
    if (root / 'installed').exists():
        print('installed')
    else:
        sys.exit(1)
elif name == 'apt-get':
    assert 'Acquire::http::Proxy=DIRECT' in args, 'HTTP proxy was not bypassed'
    assert 'Acquire::https::Proxy=DIRECT' in args, 'HTTPS proxy was not bypassed'
    if 'update' in args:
        event('update')
    elif 'install' in args:
        assert os.environ['DEBIAN_FRONTEND'] == 'noninteractive'
        (root / 'installed').touch()
        event('install')
    else:
        sys.exit(2)
elif name == 'proxy-service':
    assert (root / 'installed').exists(), 'Service started before installation'
    if not (root / 'running').exists():
        (root / 'running').touch()
        event('service')
        print('started')
    else:
        print('running')
elif name == 'proxy-client':
    assert (root / 'running').exists(), 'Client configured before proxy was started'
    if not (root / 'client-configured').exists():
        (root / 'client-configured').touch()
        event('client')
        print('configured')
    else:
        print('unchanged')
'''
            for name in ('dpkg-query', 'apt-get', 'proxy-service', 'proxy-client'):
                path = binaries / name
                path.write_text(fake)
                path.chmod(0o755)
            if scenario == 'stale-client':
                (tmp / '01proxy').write_text('Acquire::http::Proxy "http://127.0.0.1:3142";\n')
            if scenario == 'installed-but-stopped':
                (tmp / 'installed').touch()
            if scenario == 'external-proxy':
                (tmp / 'running').touch()
            role = tmp / 'roles/lab_apt_proxy'
            (role / 'tasks').mkdir(parents=True)
            (role / 'defaults').mkdir()
            shutil.copy2(ROOT / 'ansible/roles/lab_apt_proxy/defaults/main.yml', role / 'defaults/main.yml')
            tasks = yaml.safe_load((ROOT / 'ansible/roles/lab_apt_proxy/tasks/main.yml').read_text())
            for task in tasks:
                # Keep real package commands and readiness logic; replace only systemd.
                if 'ansible.builtin.systemd' in task:
                    original = task.pop('ansible.builtin.systemd')
                    self.assertEqual(original, {'name': 'apt-cacher-ng', 'state': 'started', 'enabled': True})
                    task['ansible.builtin.command'] = {'argv': [str(binaries / 'proxy-service')]}
                    task['register'] = 'test_service'
                    task['changed_when'] = "test_service.stdout == 'started'"
                if 'ansible.builtin.wait_for' in task:
                    task['ansible.builtin.wait_for']['port'] = listener.getsockname()[1]
                    task['ansible.builtin.wait_for']['timeout'] = 3
            (role / 'tasks/main.yml').write_text(yaml.safe_dump(tasks, sort_keys=False))
            common = tmp / 'roles/common/tasks'
            common.mkdir(parents=True)
            (common / 'main.yml').write_text(yaml.safe_dump([{
                'name': 'Require a running proxy before client setup',
                'ansible.builtin.command': {'argv': [str(binaries / 'proxy-client')]},
                'register': 'test_client', 'changed_when': "test_client.stdout == 'configured'",
            }], sort_keys=False))
            production = yaml.safe_load((ROOT / 'ansible/playbooks/10-lab-prepare.yml').read_text())[0]
            play = {
                'name': 'Test physical-host proxy bootstrap', 'hosts': 'localhost',
                'connection': 'local', 'gather_facts': False,
                'environment': {'PATH': str(binaries) + ':' + os.environ['PATH'], 'SRE_PROXY_TEST_ROOT': str(tmp)},
                'vars': {'site': {'lab': {'address': '127.0.0.1'}, 'apt_proxy': {'manage_on_lab': scenario != 'external-proxy'}}},
                'roles': [deepcopy(role) for role in production['roles'] if role['role'] in ('common', 'lab_apt_proxy')],
            }
            (tmp / 'play.yml').write_text(yaml.safe_dump([play], sort_keys=False))
            args = [ANSIBLE, '-i', 'localhost,', str(tmp / 'play.yml')]
            for attempt in range(2):
                result = subprocess.run(args, cwd=tmp, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                if attempt:
                    self.assertIn('changed=0', result.stdout)
            events = (tmp / 'events').read_text().splitlines()
            expected = ['service', 'client'] if scenario == 'installed-but-stopped' else ['update', 'install', 'service', 'client']
            if scenario == 'external-proxy':
                expected = ['client']
            self.assertEqual(events, expected)
            if scenario == 'stale-client':
                self.assertEqual((tmp / '01proxy').read_text(), 'Acquire::http::Proxy "http://127.0.0.1:3142";\n')


if __name__ == '__main__':
    unittest.main()
