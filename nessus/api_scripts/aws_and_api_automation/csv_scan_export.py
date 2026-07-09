import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict
from nessus import get_ssm_param
from utils import api_request, load_config, logger

config = load_config()
BASE_URL = config["nessus"]["base_url"]
HEADERS = {"Content-type": "application/json", "X-ApiKeys": f"accessKey={get_ssm_param('/nessus/access_key')}; secretKey={get_ssm_param('/nessus/secret_key')}"}

def get_recent_scans(folder_id: int, days_ago: int) -> List[Dict]:
    epoch_time = int(time.time())
    last_day = epoch_time - (60 * 60 * 24 * days_ago)
    url = f"{BASE_URL}/scans?folder_id={folder_id}&last_modification_date={last_day}"
    data = api_request("GET", url, headers=HEADERS)
    return [scan for scan in data["scans"] if scan["status"] == "completed"]

def export_scan(scan_id: int):
    url = f"{BASE_URL}/scans/{scan_id}/export"
    payload = {
        "format": "csv",
        "reportContents": {
            "csvColumns": {
                "id": True, "cve": True, "cvss": True, "risk": True, "hostname": True, "protocol": True,
                "port": True, "plugin_name": True, "synopsis": False, "description": True, "solution": True,
                "see_also": False, "plugin_output": True, "stig_severity": False, "cvss3_base_score": True,
                "cvss_temporal_score": False, "cvss3_temporal_score": False, "risk_factor": False, "references": True,
                "plugin_information": True, "exploitable_with": True
            }
        },
        "extraFilters": {"host_ids": [], "plugin_ids": []},
        "filter.0.quality": "eq", "filter.0.filter": "severity", "filter.0.value": "Critical",
        "filter.1.quality": "eq", "filter.1.filter": "severity", "filter.1.value": "High",
        "filter.2.quality": "eq", "filter.2.filter": "severity", "filter.2.value": "Medium",
        "filter.3.quality": "eq", "filter.3.filter": "severity", "filter.3.value": "Low"
    }
    response = api_request("POST", url, headers=HEADERS, json_data=payload)
    file_token = response["file"]

    status_url = f"{BASE_URL}/scans/{scan_id}/export/{file_token}/status"
    while api_request("GET", status_url, headers=HEADERS)["status"] != "ready":
        time.sleep(5)

    download_url = f"{BASE_URL}/scans/{scan_id}/export/{file_token}/download"
    csv_data = api_request("GET", download_url, headers=HEADERS, text=True)
    return csv_data

def process_scan(scan: Dict):
    csv_data = export_scan(scan["id"])
    name = scan["name"].replace("/", "-")
    logger.info(f"CSV for {name}:\n{csv_data}")

def main():
    parser = argparse.ArgumentParser(description="Export recent Nessus scans to CSV.")
    parser.add_argument("--folder-id", type=int, default=3)
    parser.add_argument("--days-ago", type=int, default=config["scan"]["export_days_ago"])
    args = parser.parse_args()

    scans = get_recent_scans(args.folder_id, args.days_ago)
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_scan, scans)

if __name__ == "__main__":
    main()