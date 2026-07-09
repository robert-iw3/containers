import os
import docker
import yaml
import hvac
import psycopg2
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_fixed
import requests

load_dotenv()

VAULT_ADDR = os.getenv('VAULT_ADDR', 'http://localhost:8200')
VAULT_TOKEN = os.getenv('VAULT_TOKEN')
VAULT_SECRET_PATH = os.getenv('VAULT_SECRET_PATH', 'bitbucket')
USE_VAULT = os.getenv('USE_VAULT', 'false').lower() == 'true'

def get_vault_secrets():
    if not USE_VAULT:
        return {
            'POSTGRESQL_PASSWORD': os.getenv('POSTGRESQL_PASSWORD', 'secure_password_123'),
            'POSTGRESQL_REPLICATION_PASSWORD': os.getenv('POSTGRESQL_REPLICATION_PASSWORD', 'replpass'),
            'BITBUCKET_ADMIN_USER': os.getenv('BITBUCKET_ADMIN_USER', 'admin'),
            'BITBUCKET_ADMIN_PASSWORD': os.getenv('BITBUCKET_ADMIN_PASSWORD', 'admin_password')
        }
    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    secret = client.secrets.kv.read_secret_version(path=VAULT_SECRET_PATH)
    return secret['data']['data']

@retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
def check_postgres_connection():
    conn = psycopg2.connect(
        dbname=os.getenv('POSTGRESQL_DATABASE', 'bitbucket'),
        user=os.getenv('POSTGRESQL_USERNAME', 'bitbucket_user'),
        password=get_vault_secrets()['POSTGRESQL_PASSWORD'],
        host=os.getenv('POSTGRESQL_IPv4', '172.28.0.2'),
        port=5432
    )
    conn.close()

@retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
def check_bitbucket_health():
    response = requests.get(f"http://{os.getenv('BITBUCKET_IPv4', '172.28.0.4')}:7990/status", timeout=5)
    response.raise_for_status()

@retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
def check_exporter_metrics():
    response = requests.get(f"http://{os.getenv('BITBUCKET_EXPORTER_IPv4', '172.28.0.9')}:8000/metrics", timeout=5)
    response.raise_for_status()
    if 'bitbucket_repo_pushes_total' not in response.text:
        raise Exception("Exporter metrics not found")

def main():
    client = docker.from_env()
    with open('docker-compose.yml', 'r') as f:
        compose_config = yaml.safe_load(f)

    secrets = get_vault_secrets()
    os.makedirs('secrets', exist_ok=True)
    with open('secrets/postgresql_password', 'w') as f:
        f.write(secrets['POSTGRESQL_PASSWORD'])
    with open('secrets/postgresql_replication_password', 'w') as f:
        f.write(secrets['POSTGRESQL_REPLICATION_PASSWORD'])

    client.containers.run('postgres-bitbucket', detach=True)
    check_postgres_connection()

    client.containers.run('postgres2-bitbucket', detach=True)
    client.containers.run('bitbucket', detach=True)
    check_bitbucket_health()

    client.containers.run('bitbucket-exporter', detach=True)
    check_exporter_metrics()

    client.containers.run('prometheus', detach=True)
    client.containers.run('grafana', detach=True)
    client.containers.run('alertmanager', detach=True)
    client.containers.run('postgres-exporter', detach=True)

if __name__ == '__main__':
    main()