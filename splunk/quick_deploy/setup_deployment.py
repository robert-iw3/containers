import os
import subprocess
import getpass
import uuid
import yaml
import sys
import logging
import socket
import boto3
import json
from pathlib import Path
from tqdm import tqdm

# Configure logging
logging.basicConfig(filename='logs/deployment.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def check_prerequisites():
    """Check if required tools and connectivity are available."""
    logging.info("Running pre-flight checks...")
    tools = ['ansible', 'terraform', 'ansible-vault']
    for tool in tools:
        try:
            subprocess.run([tool, '--version'], check=True, capture_output=True)
        except FileNotFoundError:
            logging.error(f"{tool} is not installed")
            print(f"Error: {tool} is not installed. Please install it.")
            return False

    if not Path('ansible').exists() or not Path('terraform').exists() or not Path('config').exists():
        logging.error("Required directories (ansible, terraform, config) are missing")
        print("Error: Required directories (ansible, terraform, config) are missing.")
        return False

    # Check network connectivity
    try:
        socket.create_connection(("splunk.com", 443), timeout=5)
        logging.info("Network connectivity to splunk.com verified")
    except socket.error:
        logging.error("No network connectivity to splunk.com")
        print("Error: No network connectivity to splunk.com")
        return False

    return True

def check_aws_credentials():
    """Verify AWS credentials and S3/DynamoDB setup."""
    try:
        boto3.client('sts').get_caller_identity()
        boto3.client('s3').head_bucket(Bucket='splunk-terraform-state')
        boto3.client('dynamodb').describe_table(TableName='splunk-terraform-locks')
        logging.info("AWS credentials and resources verified")
        return True
    except Exception as e:
        logging.error(f"AWS credentials or resources invalid: {str(e)}")
        print(f"Error: Invalid AWS credentials or resources. Ensure AWS CLI is configured and splunk-terraform-state bucket and splunk-terraform-locks table exist.")
        return False

def check_disk_space():
    """Verify sufficient disk space for Splunk."""
    stat = os.statvfs('/')
    free_space = stat.f_bavail * stat.f_frsize / (1024 ** 3)  # GB
    if free_space < 50:
        logging.error(f"Insufficient disk space: {free_space} GB available, 50 GB required")
        print(f"Error: Insufficient disk space ({free_space} GB). At least 50 GB required.")
        return False
    logging.info(f"Disk space check passed: {free_space} GB available")
    return True

def encrypt_vault_variable(value, var_name):
    """Encrypt a variable using Ansible Vault."""
    try:
        result = subprocess.run(['ansible-vault', 'encrypt_string', value, '--name', var_name],
                               check=True, capture_output=True, text=True)
        logging.info(f"Encrypted vault variable: {var_name}")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Error encrypting {var_name}: {e.stderr}")
        print(f"Error encrypting {var_name}. Check logs/deployment.log.")
        sys.exit(1)

def update_config_file(config, config_file):
    """Update deployment_config.yaml with provided configuration."""
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    logging.info(f"Updated {config_file}")
    print(f"Updated {config_file}")

def validate_cidr(cidr):
    """Validate CIDR block format."""
    try:
        parts = cidr.split('/')
        ip_parts = parts[0].split('.')
        if len(ip_parts) != 4 or not all(0 <= int(x) <= 255 for x in ip_parts):
            return False
        if len(parts) > 1:
            prefix = int(parts[1])
            if not 0 <= prefix <= 32:
                return False
        return True
    except:
        return False

def validate_password(password):
    """Validate password complexity."""
    if len(password) < 8 or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
        return False
    return True

def create_aws_secrets():
    """Create AWS Secrets Manager secret for Splunk credentials."""
    try:
        client = boto3.client('secretsmanager')
        secret_value = {
            'ami_id': input("Enter AMI ID (Debian or RHEL): "),
            'key_name': input("Enter SSH key name: "),
            'subnet_id': input("Enter Subnet ID: "),
            'vpc_id': input("Enter VPC ID: ")
        }
        response = client.create_secret(
            Name=f"splunk-secrets-{uuid.uuid4()}",
            SecretString=json.dumps(secret_value)
        )
        logging.info(f"Created AWS Secrets Manager secret: {response['ARN']}")
        return response['ARN']
    except Exception as e:
        logging.error(f"Failed to create AWS secret: {str(e)}")
        print(f"Error creating AWS secret. Check logs/deployment.log.")
        sys.exit(1)

def main():
    if not check_prerequisites() or not check_disk_space():
        sys.exit(1)

    print("Setting up Splunk deployment configuration...")
    config_file = Path('config/deployment_config.yaml')
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    # Collect deployment configuration
    for _ in tqdm(range(1), desc="Configuring deployment"):
        config['splunk_instance_size'] = input("Enter Splunk instance size (small, medium, large) [medium]: ") or "medium"
        if config['splunk_instance_size'] not in ['small', 'medium', 'large']:
            logging.error(f"Invalid splunk_instance_size: {config['splunk_instance_size']}")
            print("Error: Invalid instance size. Using default 'medium'.")
            config['splunk_instance_size'] = "medium"

        try:
            config['indexing_volume'] = int(input("Enter indexing volume in GB [100]: ") or 100)
            if config['indexing_volume'] <= 0:
                raise ValueError
        except ValueError:
            logging.error(f"Invalid indexing_volume: {config['indexing_volume']}")
            print("Error: Invalid indexing volume. Using default 100 GB.")
            config['indexing_volume'] = 100

        config['allowed_cidr'] = input("Enter CIDR block for Splunk access (e.g., 192.168.1.0/24) [0.0.0.0/0]: ") or "0.0.0.0/0"
        if not validate_cidr(config['allowed_cidr']):
            logging.error(f"Invalid CIDR block: {config['allowed_cidr']}")
            print("Error: Invalid CIDR block. Using default 0.0.0.0/0.")
            config['allowed_cidr'] = "0.0.0.0/0"

        deployment_type = input("Enter deployment type (aws, bare_metal) [bare_metal]: ") or "bare_metal"
        if deployment_type == 'aws' and not check_aws_credentials():
            sys.exit(1)

        # Collect vault variables
        print("\nEnter secure passwords for Splunk configuration (minimum 8 characters, with uppercase and digits):")
        admin_password = getpass.getpass("Splunk admin password: ")
        if not validate_password(admin_password):
            logging.error("Invalid admin password")
            print("Error: Admin password must be at least 8 characters with uppercase and digits.")
            sys.exit(1)
        config['vault_splunk_admin_password'] = encrypt_vault_variable(admin_password, 'vault_splunk_admin_password')

        config['vault_splunk_hec_token'] = encrypt_vault_variable(str(uuid.uuid4()), 'vault_splunk_hec_token')

        analyst_password = getpass.getpass("Security analyst password: ")
        if not validate_password(analyst_password):
            logging.error("Invalid analyst password")
            print("Error: Analyst password must be at least 8 characters with uppercase and digits.")
            sys.exit(1)
        config['vault_sec_analyst_password'] = encrypt_vault_variable(analyst_password, 'vault_sec_analyst_password')

        admin_sec_password = getpass.getpass("Security admin password: ")
        if not validate_password(admin_sec_password):
            logging.error("Invalid security admin password")
            print("Error: Security admin password must be at least 8 characters with uppercase and digits.")
            sys.exit(1)
        config['vault_sec_admin_password'] = encrypt_vault_variable(admin_sec_password, 'vault_sec_admin_password')

        config['vault_splunk_symm_key'] = encrypt_vault_variable(str(uuid.uuid4()), 'vault_splunk_symm_key')

        if deployment_type == 'aws':
            config['secrets_id'] = create_aws_secrets()
        else:
            config['secrets_id'] = ""

        update_config_file(config, config_file)

    print("\nSetup complete! Run the deployment with:")
    print(f"python deploy_splunk.py --type {deployment_type}")

if __name__ == '__main__':
    main()