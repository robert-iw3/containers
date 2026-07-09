import unittest
import requests
import time

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.bitbucket_url = "http://172.28.0.4:7990"
        self.exporter_url = "http://172.28.0.9:8000"
        self.postgres_host = "172.28.0.2"
        self.postgres_user = "bitbucket_user"
        self.postgres_db = "bitbucket"
        self.postgres_password = "secure_password_123"

    def test_bitbucket_status(self):
        response = requests.get(f"{self.bitbucket_url}/status", timeout=5)
        self.assertEqual(response.status_code, 200)

    def test_postgres_connection(self):
        import psycopg2
        conn = psycopg2.connect(
            dbname=self.postgres_db,
            user=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=5432
        )
        conn.close()
        self.assertTrue(True)

    def test_exporter_metrics(self):
        response = requests.get(f"{self.exporter_url}/metrics", timeout=5)
        self.assertEqual(response.status_code, 200)
        self.assertIn("bitbucket_repo_pushes_total", response.text)

if __name__ == '__main__':
    unittest.main()