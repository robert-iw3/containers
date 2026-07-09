import json
from functools import lru_cache
import toml
from typing import List, Dict
from nessus import (
    list_policies, create_policy, list_policy_templates, create_scan, update_scan, describe_scan, list_scans
)
from utils import load_config, logger

config = load_config()

@lru_cache(maxsize=1)
def find_scan_policy(name: str = "standard_scan") -> Dict:
    for policy in list_policies()["policies"]:
        if policy["name"] == name:
            return policy
    return {}

def create_scan_policy(policy_file: str = config["scan"]["policy_template"]) -> Dict:
    with open(policy_file, "r") as f:
        policy = json.load(f)
    policy["uuid"] = advanced_dynamic_policy_template_uuid()
    return create_policy(policy)

def gds_scan_policy_id() -> int:
    policy = find_scan_policy()
    return policy.get("id") or create_scan_policy()["policy_id"]

@lru_cache(maxsize=1)
def advanced_dynamic_policy_template_uuid() -> str:
    templates = list_policy_templates()["templates"]
    for template in templates:
        if template["title"] == "Advanced Dynamic Scan":
            return template["uuid"]
    raise ValueError("Advanced Dynamic Scan template not found")

def config_rrules(scan: Dict) -> str:
    return f"FREQ={scan['rrules']['freq']};INTERVAL={scan['rrules']['interval']};BYDAY={scan['rrules']['byday']}"

def create_scan_config(scan: Dict, policy_id: int) -> Dict:
    return {
        "uuid": advanced_dynamic_policy_template_uuid(),
        "settings": {
            "name": scan["name"],
            "enabled": scan["enabled"],
            "rrules": config_rrules(scan),
            "policy_id": policy_id,
            "starttime": scan["starttime"],
            "timezone": "America/Denver",
            "text_targets": scan["text_targets"],
            "agent_group_id": [],
        },
    }

def load_scan_config() -> Dict:
    with open(config["scan"]["scan_config"], "r") as f:
        return toml.load(f)

def update_scans(toml_config: Dict, nessus_scans: List[Dict]):
    nessus_scan_names = [scan["name"] for scan in nessus_scans]
    toml_scans = list(toml_config.values())
    for toml_scan in toml_scans:
        if toml_scan["name"] not in nessus_scan_names:
            logger.info(f"Creating new scan: {toml_scan['name']}")
            create_scan(create_scan_config(toml_scan, gds_scan_policy_id()))
            continue

        nessus_scan = next(s for s in nessus_scans if s["name"] == toml_scan["name"])
        if (
            config_rrules(toml_scan) == nessus_scan["rrules"]
            and describe_scan(nessus_scan["id"])["info"]["targets"].split(",") == toml_scan["text_targets"].split(",")
            and all(nessus_scan[k] == toml_scan[k] for k in ["enabled", "starttime"])
        ):
            logger.info(f"Scan {toml_scan['name']} unchanged, skipping.")
        else:
            logger.info(f"Updating scan {toml_scan['name']}")
            update_scan(create_scan_config(toml_scan, gds_scan_policy_id()), nessus_scan["id"])

def check_scan():
    scan_list = list_scans()
    toml_config = load_scan_config()
    nessus_scans = scan_list.get("scans", [])
    if not nessus_scans:
        policy_id = gds_scan_policy_id()
        for scan in toml_config.values():
            create_scan(create_scan_config(scan, policy_id))
    else:
        update_scans(toml_config, nessus_scans)

def main():
    logger.info("Scheduling scans...")
    check_scan()

if __name__ == "__main__":
    main()