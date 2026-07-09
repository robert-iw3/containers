import os
import re
from functools import lru_cache
from typing import List, Dict, Any, Optional

import boto3

from utils import get_ssm_param, load_config, api_request, logger

config = load_config()
BASE_URL = config["nessus"]["base_url"]

def verify_ssl() -> bool:
    return config["nessus"]["verify_ssl"]

@lru_cache(maxsize=1)
def username() -> str:
    return get_ssm_param(config["nessus"]["username_param"])

@lru_cache(maxsize=1)
def password() -> str:
    return get_ssm_param(config["nessus"]["password_param"])

@lru_cache(maxsize=1)
def get_token() -> Dict[str, str]:
    response = api_request("POST", f"{BASE_URL}/session", json_data={"username": username(), "password": password()})
    return {"X-Cookie": f"token={response['token']}"}

@lru_cache(maxsize=1)
def get_x_api_token() -> str:
    r = api_request("GET", f"{BASE_URL}/nessus6.js", text=True)
    m = re.search(r"([0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12})", r)
    return m.group(0) if m else ""

@lru_cache(maxsize=1)
def api_credentials() -> Dict[str, str]:
    access_key = get_ssm_param(config["nessus"]["access_key_param"])
    secret_key = get_ssm_param(config["nessus"]["secret_key_param"])
    return {"X-ApiKeys": f"accessKey={access_key}; secretKey={secret_key}"}

@lru_cache(maxsize=1)
def manager_credentials() -> Dict[str, str]:
    headers = {"X-API-Token": get_x_api_token()}
    headers.update(get_token())
    return headers

@lru_cache(maxsize=None)
def ec2_client():
    return boto3.client("ec2", region_name=config["aws"]["region"])

def get_ec2_param(param: str) -> str:
    return ec2_client().describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": ["Nessus Scanning Instance"]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]
    )["Reservations"][0]["Instances"][0][param]

@lru_cache(maxsize=1)
def base_url() -> str:
    if os.getenv("AWS_EXECUTION_ENV"):
        return f"https://{get_ec2_param('PrivateIpAddress')}:8834"
    return get_ssm_param(config["nessus"]["public_base_url_param"])

def get(path: str, text: bool = False) -> Any:
    url = f"{base_url()}{path}"
    headers = api_credentials()
    return api_request("GET", url, headers=headers) if not text else api_request("GET", url, headers=headers, text=True)

def post(path: str, payload: Dict, headers: Optional[Dict] = None) -> Dict:
    url = f"{base_url()}{path}"
    return api_request("POST", url, headers=headers or api_credentials(), json_data=payload)

def put(path: str, payload: Dict, headers: Optional[Dict] = None) -> Dict:
    url = f"{base_url()}{path}"
    return api_request("PUT", url, headers=headers or api_credentials(), json_data=payload)

def list_policies() -> Dict[str, List[Dict]]:
    policies = get("/policies")
    if policies.get("policies") is None:
        policies["policies"] = []
    return policies

def create_policy(policy: Dict) -> Dict:
    return post("/policies", policy)

def policy_details(policy_id: int) -> Dict:
    return get(f"/policies/{policy_id}")

def list_scans() -> Dict[str, List[Dict]]:
    scans = get("/scans")
    if "scans" not in scans or not scans["scans"]:
        scans["scans"] = []
    return scans

def create_scan(scan: Dict) -> Dict:
    return post("/scans", scan, manager_credentials())

def update_scan(scan: Dict, scan_id: int) -> Dict:
    return put(f"/scans/{scan_id}", scan, manager_credentials())

def describe_scan(scan_id: int) -> Dict:
    return get(f"/scans/{scan_id}")

def prepare_export(scan_id: int) -> Dict:
    return post(f"/scans/{scan_id}/export", {"format": "csv"})

def list_policy_templates() -> Dict:
    return get("/editor/policy/templates")

def download_report(token: str) -> str:
    return get(f"/tokens/{token}/download", text=True)