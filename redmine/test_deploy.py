import unittest
import os
import tempfile
import yaml
from deploy import load_config, validate_config

class TestDeployScript(unittest.TestCase):
    def setUp(self):
        self.temp_fd, self.temp_config = tempfile.mkstemp(suffix='.yml')
        self.valid_config = {
            'deployment': {
                'target': 'docker',
                'ansible_inventory': 'ansible/inventory/hosts.yml',
                'ansible_playbook_dir': 'ansible/playbooks'
            },
            'redmine': {
                'version': '6.1.2',
                'port': 10445,
                'http_port': 10083,
                'secret_token': 'test_token',
                'timezone': 'America/Denver'
            },
            'postgres': {
                'user': 'redmine',
                'password': 'securepassword',
                'db': 'redmine_production',
                'port': 5432
            },
            'smtp': {
                'enabled': False,
                'domain': 'www.example.com',
                'host': 'smtp.gmail.com',
                'port': 587,
                'user': 'mailer@example.com',
                'password': 'securepassword',
                'starttls': True
            },
            'haproxy': {
                'http_port': 80,
                'https_port': 443
            },
            'paths': {
                'certs': './certs',
                'errors': './errors',
                'haproxy_config': './haproxy.cfg',
                'docker_socket': '/var/run/docker.sock'
            }
        }

    def tearDown(self):
        os.remove(self.temp_config)

    def test_load_config_valid(self):
        with open(self.temp_config, 'w') as f:
            yaml.dump(self.valid_config, f)
        config = load_config(self.temp_config)
        self.assertEqual(config, self.valid_config)

    def test_load_config_invalid(self):
        with open(self.temp_config, 'w') as f:
            f.write('invalid: yaml: content')
        with self.assertRaises(yaml.YAMLError):
            load_config(self.temp_config)

    def test_validate_config_valid(self):
        validate_config(self.valid_config)
        self.assertTrue(True)  # No exception means success

    def test_validate_config_missing_key(self):
        invalid_config = self.valid_config.copy()
        del invalid_config['redmine']['secret_token']
        with self.assertRaises(ValueError) as cm:
            validate_config(invalid_config)
        self.assertIn("Missing configuration key: redmine.secret_token", str(cm.exception))

    def test_validate_config_invalid_target(self):
        invalid_config = self.valid_config.copy()
        invalid_config['deployment']['target'] = 'invalid'
        with self.assertRaises(ValueError) as cm:
            validate_config(invalid_config)
        self.assertIn("Invalid deployment target: invalid", str(cm.exception))

if __name__ == '__main__':
    unittest.main()