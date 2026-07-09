import unittest
from unittest.mock import patch, MagicMock
import deploy_bitbucket

class TestDeployBitbucket(unittest.TestCase):
    @patch('deploy_bitbucket.docker.from_env')
    def test_docker_client(self, mock_docker):
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        deploy_bitbucket.main()
        mock_docker.assert_called_once()

    @patch('deploy_bitbucket.hvac.Client')
    def test_vault_secrets(self, mock_vault):
        mock_client = MagicMock()
        mock_vault.return_value = mock_client
        mock_client.secrets.kv.read_secret_version.return_value = {
            'data': {
                'data': {
                    'POSTGRESQL_PASSWORD': 'test_pass',
                    'POSTGRESQL_REPLICATION_PASSWORD': 'test_repl',
                    'BITBUCKET_ADMIN_USER': 'admin',
                    'BITBUCKET_ADMIN_PASSWORD': 'admin_pass'
                }
            }
        }
        secrets = deploy_bitbucket.get_vault_secrets()
        self.assertEqual(secrets['POSTGRESQL_PASSWORD'], 'test_pass')

    @patch('deploy_bitbucket.psycopg2.connect')
    def test_postgres_connection(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        deploy_bitbucket.check_postgres_connection()
        mock_connect.assert_called_once()

if __name__ == '__main__':
    unittest.main()