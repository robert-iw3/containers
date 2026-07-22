import os
import secrets
import subprocess
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_default_gateway():
    """Get the default gateway IP."""
    try:
        result = subprocess.run(['ip', 'route'], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if 'default' in line:
                return line.split()[2]
        logger.error("No default gateway found")
        return '192.168.1.1'
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get default gateway: {e}")
        return '192.168.1.1'

def generate_env():
    """Generate .env file with secure defaults."""
    env_file = Path('.env')
    if env_file.exists():
        logger.info(".env file already exists, skipping generation")
        return

    env_content = {
        'TS_AUTHKEY': os.getenv('TS_AUTHKEY', ''),
        'SUBNET_CIDR': os.getenv('SUBNET_CIDR', '192.168.1.0/24'),
        'PG_USER': 'authentik',
        'PG_DB': 'authentik',
        'PG_PASS': secrets.token_urlsafe(36),
        'AUTHENTIK_SECRET_KEY': secrets.token_urlsafe(60),
        'AUTHENTIK_ERROR_REPORTING__ENABLED': 'true',
        'GATEWAY': get_default_gateway(),
        'TS_AUTH_PORT': '443',
        'TS_AUTH_SCHEME': 'https'
    }

    with env_file.open('w') as f:
        for key, value in env_content.items():
            f.write(f"{key}={value}\n")
    logger.info(".env file generated at %s", env_file)

if __name__ == "__main__":
    generate_env()