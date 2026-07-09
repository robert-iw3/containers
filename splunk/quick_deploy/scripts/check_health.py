import subprocess
import sys
import requests
import time
import logging
from pathlib import Path
import yaml

# Configure logging
logging.basicConfig(filename='logs/deployment.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def check_service_status(service_name):
    """Check if a systemd service is running."""
    try:
        result = subprocess.run(['systemctl', 'is-active', service_name],
                              check=True, capture_output=True, text=True)
        status = result.stdout.strip() == 'active'
        logging.info(f"Service {service_name} status: {'active' if status else 'inactive'}")
        return status
    except subprocess.CalledProcessError:
        logging.error(f"Service {service_name} check failed")
        return False

def check_splunk_web(ip, port=8000):
    """Check if Splunk Web is accessible."""
    try:
        response = requests.get(f"https://{ip}:{port}", verify=False, timeout=10)
        status = response.status_code == 200
        logging.info(f"Splunk Web check at https://{ip}:{port}: {'successful' if status else 'failed'}")
        return status
    except requests.RequestException as e:
        logging.error(f"Splunk Web check failed: {str(e)}")
        return False

def check_splunk_hec(ip, port=8088, token=None):
    """Check if Splunk HEC is accessible."""
    try:
        headers = {'Authorization': f'Splunk {token}'}
        response = requests.post(f"https://{ip}:{port}/services/collector/event",
                                json={'event': 'health_check'}, headers=headers, verify=False, timeout=10)
        status = response.status_code == 200
        logging.info(f"Splunk HEC check at https://{ip}:{port}: {'successful' if status else 'failed'}")
        return status
    except requests.RequestException as e:
        logging.error(f"Splunk HEC check failed: {str(e)}")
        return False

def check_splunk_index(ip, port=8089, username='admin', password=None):
    """Check if Splunk index is operational."""
    try:
        response = requests.get(f"https://{ip}:{port}/services/data/indexes/main",
                               auth=(username, password), verify=False, timeout=10)
        status = response.status_code == 200
        logging.info(f"Splunk index check at https://{ip}:{port}: {'successful' if status else 'failed'}")
        return status
    except requests.RequestException as e:
        logging.error(f"Splunk index check failed: {str(e)}")
        return False

def main():
    deployment_type = sys.argv[1] if len(sys.argv) > 1 else 'bare_metal'
    ip = 'localhost' if deployment_type == 'bare_metal' else subprocess.run(
        ['terraform', 'output', '-raw', 'splunk_server_public_ip'],
        capture_output=True, text=True).stdout.strip()

    print("Checking Splunk deployment health...")

    # Check Splunk Enterprise service
    if not check_service_status('splunk'):
        print("Error: Splunk Enterprise service is not running.")
        sys.exit(1)
    print("Splunk Enterprise service is running.")

    # Check Splunk Universal Forwarder service
    if not check_service_status('splunkforwarder'):
        print("Error: Splunk Universal Forwarder service is not running.")
        sys.exit(1)
    print("Splunk Universal Forwarder service is running.")

    # Check Splunk Web
    if not check_splunk_web(ip):
        print(f"Error: Splunk Web is not accessible at https://{ip}:8000")
        sys.exit(1)
    print(f"Splunk Web is accessible at https://{ip}:8000")

    # Check Splunk HEC (assuming token is available in config)
    config = yaml.safe_load(Path('config/deployment_config.yaml').read_text())
    if not check_splunk_hec(ip, config['splunk_hec_port'], config['vault_splunk_hec_token']):
        print(f"Error: Splunk HEC is not accessible at https://{ip}:{config['splunk_hec_port']}")
        sys.exit(1)
    print(f"Splunk HEC is accessible at https://{ip}:{config['splunk_hec_port']}")

    # Check Splunk index
    if not check_splunk_index(ip, config['splunk_port'], config['splunk_admin_user'], config['vault_splunk_admin_password']):
        print(f"Error: Splunk index 'main' is not operational at https://{ip}:{config['splunk_port']}")
        sys.exit(1)
    print(f"Splunk index 'main' is operational at https://{ip}:{config['splunk_port']}")

    logging.info("Health check passed")
    print("Health check passed!")

if __name__ == '__main__':
    main()