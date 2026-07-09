import json
import logging
import os
import time
from functools import lru_cache
from typing import Dict, Any, Optional

import boto3
import requests
import toml

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CONFIG_FILE = "config.toml"

@lru_cache(maxsize=1)
def load_config() -> Dict[str, Any]:
    """Load centralized config from TOML file."""
    if os.path.exists(CONFIG_FILE):
        return toml.load(CONFIG_FILE)
    logger.warning(f"Config file {CONFIG_FILE} not found, using defaults.")
    return {
        "nessus": {
            "base_url": "https://127.0.0.1:8834",
            "verify_ssl": False,
            "access_key_param": "/nessus/access_key",
            "secret_key_param": "/nessus/secret_key",
            "username_param": "/nessus/username",
            "password_param": "/nessus/password",
            "public_base_url_param": "/nessus/public_base_url",
        },
        "aws": {"region": "us-east-1", "log_group": "/gds/nessus-scans"},
        "scan": {
            "policy_template": "scan_config/standard_scan_template.json",
            "scan_config": "scan_config/scan.toml",
            "export_days_ago": 5,
        },
    }

@lru_cache(maxsize=10)
def get_ssm_param(param: str, with_decryption: bool = True) -> str:
    """Fetch parameter from AWS SSM."""
    config = load_config()
    session = boto3.Session(region_name=config["aws"]["region"])
    ssm = session.client("ssm")
    response = ssm.get_parameter(Name=param, WithDecryption=with_decryption)
    return response["Parameter"]["Value"]

def api_request(method: str, url: str, headers: Optional[Dict] = None, json_data: Optional[Dict] = None, retries: int = 3) -> Any:
    """Generic API request with retries."""
    config = load_config()
    verify = config["nessus"]["verify_ssl"]
    for attempt in range(retries):
        try:
            response = requests.request(method, url, headers=headers, json=json_data, verify=verify)
            response.raise_for_status()
            return response.json() if "application/json" in response.headers.get("Content-Type", "") else response.text
        except requests.RequestException as e:
            logger.error(f"API request failed (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
    raise RuntimeError(f"API request failed after {retries} attempts: {url}")