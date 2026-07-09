import json
import os
import time
from functools import lru_cache

import boto3

from utils import get_ssm_param, load_config, logger, api_request
from nessus import get_token, base_url, get_ec2_param, ec2_client  # Assuming nessus.py is updated similarly

@lru_cache(maxsize=None)
def ssm_client():
    config = load_config()
    return boto3.client("ssm", region_name=config["aws"]["region"])

def get_fqdn():
    tf_fqdn = os.environ.get("fqdn")
    if tf_fqdn:
        return f"https://{tf_fqdn}"
    else:
        return base_url()

def instance_ready():
    try:
        nessus_status_checks = ec2_client().describe_instance_status(InstanceIds=[get_ec2_param("InstanceId")])
        status = nessus_status_checks["InstanceStatuses"][0]["InstanceStatus"]["Status"]
        reachability = nessus_status_checks["InstanceStatuses"][0]["InstanceStatus"]["Details"][0]["Status"]
        if status != "ok" or reachability != "passed":
            logger.warning(f"EC2 not ready: Status={status}, Reachability={reachability}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking instance status: {e}")
        return False

def update_ssm_base_url():
    fqdn = get_fqdn()
    put_param(fqdn, "public_base_url")
    logger.info(f"Updated SSM base URL to {fqdn}")

def put_keys():
    keys_url = f"{base_url()}/session/keys"
    keys_response = api_request("PUT", keys_url, headers=get_token())
    keys = json.loads(keys_response)
    access_key = keys["accessKey"]
    secret_key = keys["secretKey"]
    put_param(access_key, "access_key")
    put_param(secret_key, "secret_key")
    logger.info("API keys stored in SSM")

def put_param(value: str, name: str):
    ssm_client().put_parameter(
        Name=f"/nessus/{name}",
        Description=f"{name} for Nessus instance",
        Value=value,
        Overwrite=True,
        Type="SecureString",
    )

def nessus_ready():
    try:
        server_status_url = f"{base_url()}/server/status"
        status = api_request("GET", server_status_url)
        return json.loads(status)["status"] == "ready"
    except Exception as e:
        logger.error(f"Nessus not ready: {e}")
        return False

def main():
    config = load_config()
    ec2_timeout = time.time() + 60 * 10
    while not instance_ready():
        if time.time() > ec2_timeout:
            raise TimeoutError("EC2 status check timeout")
        time.sleep(60)

    update_ssm_base_url()

    nessus_timeout = time.time() + 60 * 60
    while not nessus_ready():
        if time.time() > nessus_timeout:
            raise TimeoutError("Nessus readiness timeout")
        logger.info("Waiting for Nessus...")
        time.sleep(300)

    put_keys()

if __name__ == "__main__":
    logger.info("Generating API keys...")
    main()