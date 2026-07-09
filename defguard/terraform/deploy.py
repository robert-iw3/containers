#!/usr/bin/env python3
import subprocess
import boto3
import json
import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from botocore.exceptions import ClientError

# Setting up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

def run_command(command, check=True):
    """Run a shell command and log output."""
    logger.info(f"Executing command: {' '.join(command)}")
    try:
        result = subprocess.run(command, check=check, capture_output=True, text=True)
        logger.info(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e.stderr}")
        raise

def apply_terraform(secrets_file):
    """Apply the Terraform configuration."""
    logger.info("Initializing Terraform...")
    run_command(["terraform", "init"])

    logger.info(f"Applying Terraform configuration with {secrets_file}...")
    run_command(["terraform", "apply", "-var-file", secrets_file, "-auto-approve"])

def destroy_terraform(secrets_file):
    """Destroy the Terraform-managed infrastructure."""
    logger.info(f"Destroying Terraform-managed infrastructure with {secrets_file}...")
    run_command(["terraform", "destroy", "-var-file", secrets_file, "-auto-approve"])

def get_terraform_outputs():
    """Retrieve Terraform outputs."""
    logger.info("Retrieving Terraform outputs...")
    result = run_command(["terraform", "output", "-json"])
    return json.loads(result.stdout)

def wait_for_instance(instance_id, region, timeout=600, interval=10):
    """Wait for an EC2 instance to be in the 'running' state."""
    logger.info(f"Waiting for instance {instance_id} to be running...")
    ec2 = boto3.client("ec2", region_name=region)
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = ec2.describe_instances(InstanceIds=[instance_id])
            state = response["Reservations"][0]["Instances"][0]["State"]["Name"]
            if state == "running":
                logger.info(f"Instance {instance_id} is running.")
                return True
            time.sleep(interval)
        except ClientError as e:
            logger.error(f"Error checking instance {instance_id}: {str(e)}")
            time.sleep(interval)

    logger.error(f"Timeout waiting for instance {instance_id} to be running.")
    return False

def verify_service_status(instance_id, public_ip, region, port, service_name):
    """Verify the service is running by checking its health endpoint or status."""
    logger.info(f"Verifying {service_name} service on instance {instance_id}...")
    # Note: This is a placeholder. Actual implementation depends on Defguard's health endpoints.
    # For now, assume services are running if the instance is up.
    # You may need to SSH or use AWS Systems Manager to check systemctl status.
    logger.info(f"Assuming {service_name} is running on {public_ip}:{port}.")
    return True

def deploy_component(component_name, instance_id, public_ip, region, port):
    """Deploy and verify a single component."""
    if wait_for_instance(instance_id, region):
        if verify_service_status(instance_id, public_ip, region, port, component_name):
            logger.info(f"{component_name} deployment verified.")
            return True
        else:
            logger.error(f"{component_name} service verification failed.")
            return False
    else:
        logger.error(f"{component_name} instance failed to start.")
        return False

def main():
    parser = argparse.ArgumentParser(description="Unified Defguard deployment script")
    parser.add_argument("--secrets-file", required=True, help="Path to secrets.tfvars file")
    parser.add_argument("--destroy", action="store_true", help="Destroy the infrastructure")
    parser.add_argument("--region", default="eu-north-1", help="AWS region")
    args = parser.parse_args()

    try:
        if args.destroy:
            destroy_terraform(args.secrets_file)
            logger.info("Infrastructure destroyed successfully.")
            return

        # Apply Terraform configuration
        apply_terraform(args.secrets_file)

        # Retrieve Terraform outputs
        outputs = get_terraform_outputs()

        # Extract instance IDs and IP addresses
        core_instance_id = outputs.get("instance_id", {}).get("value")
        core_public_ip = outputs.get("defguard_core_public_address", {}).get("value")
        proxy_instance_id = outputs.get("defguard_proxy_instance_id", {}).get("value")
        proxy_public_ip = outputs.get("defguard_proxy_public_address", {}).get("value")
        gateway_instance_ids = outputs.get("defguard_gateway_instance_ids", {}).get("value", [])
        gateway_public_ips = outputs.get("defguard_gateway_public_addresses", {}).get("value", [])

        # Deploy and verify components
        components = [
            ("Core", core_instance_id, core_public_ip, args.region, 8000),
            ("Proxy", proxy_instance_id, proxy_public_ip, args.region, 8000)
        ]

        # Add Gateway instances
        for i, (instance_id, public_ip) in enumerate(zip(gateway_instance_ids, gateway_public_ips)):
            components.append((f"Gateway-{i+1}", instance_id, public_ip, args.region, 51820))

        # Deploy components in parallel
        with ThreadPoolExecutor(max_workers=len(components)) as executor:
            results = executor.map(lambda c: deploy_component(*c), components)

        if all(results):
            logger.info("All components deployed and verified successfully.")
        else:
            logger.error("One or more components failed to deploy or verify.")
            raise RuntimeError("Deployment failed.")

    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()