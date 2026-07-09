import argparse
import json
import time
from datetime import datetime
from typing import List
from typing import Dict
from nessus import get_ssm_param
from prettytable import PrettyTable
from utils import api_request, load_config, logger

config = load_config()
BASE_URL = config["nessus"]["base_url"]
HEADERS = {"Content-type": "application/json", "X-ApiKeys": f"accessKey={get_ssm_param('/nessus/access_key')}; secretKey={get_ssm_param('/nessus/secret_key')}"}
SLEEP_TIME = 1.0

FORMAT_MAP = {
    "0": "nessus",
    "1": "pdf",
    "2": "html",
    "3": "csv",
    "4": "db"
}

CHAPTER_MAP = {
    "0": "vuln_hosts_summary",
    "1": "vuln_by_host",
    "2": "vuln_by_plugin",
    "3": "compliance_exec",
    "4": "compliance",
    "5": "remediations"
}

def print_table(data: List[Dict], headers: List[str]):
    tab = PrettyTable(headers)
    for row in data:
        l = [datetime.fromtimestamp(int(row[h.lower().replace(" ", "_")])).strftime('%Y-%m-%d %H:%M:%S') if "date" in h.lower() else str(row[h.lower().replace(" ", "_")]) for h in headers]
        tab.add_row(l)
    print(tab)

def get_scan_data() -> Dict:
    return api_request("GET", f"{BASE_URL}/scans", headers=HEADERS)

def download_report(scan_id: int, report_format: Dict):
    url = f"{BASE_URL}/scans/{scan_id}/export"
    payload = {"format": report_format["format"], "chapters": report_format["chapters"]}
    if report_format["format"] == "db":
        payload["password"] = report_format["db_pass"]
    response = api_request("POST", url, headers=HEADERS, json_data=payload)
    file_token = response["file"]

    status_url = f"{BASE_URL}/scans/{scan_id}/export/{file_token}/status"
    while api_request("GET", status_url, headers=HEADERS)["status"] != "ready":
        time.sleep(SLEEP_TIME)

    download_url = f"{BASE_URL}/scans/{scan_id}/export/{file_token}/download"
    content = api_request("GET", download_url, headers=HEADERS, text=True if report_format["format"] != "db" else False)
    filename = f"scan_{scan_id}.{report_format['format']}"
    mode = "w" if isinstance(content, str) else "wb"
    with open(filename, mode) as f:
        f.write(content)
    logger.info(f"Report saved as {filename}")

def main():
    parser = argparse.ArgumentParser(description="Download Nessus reports.")
    parser.add_argument("-s", "--scan-id", help="Comma-separated scan IDs or 'all'")
    parser.add_argument("-d", "--folder-id", help="Comma-separated folder IDs")
    parser.add_argument("-f", "--format", default="0", help="Comma-separated formats (0=nessus,1=pdf,2=html,3=csv,4=db)")
    parser.add_argument("-c", "--chapter", default="1", help="Comma-separated chapters for PDF/HTML")
    parser.add_argument("--db-pass", default="nessus", help="DB password for .db exports")
    args = parser.parse_args()

    scan_data = get_scan_data()
    if not args.scan_id and not args.folder_id:
        print_table(scan_data["scans"], ["ID", "Name", "Folder ID", "Status", "Creation Date", "Last Modification Date"])
        return

    scan_ids = []  # Logic to get scan_ids from args.scan_id or args.folder_id similar to original
    # Placeholder: Assume scan_ids populated

    formats = [{"format": FORMAT_MAP[f], "chapters": CHAPTER_MAP[c] if f in ["1","2"] else "", "db_pass": args.db_pass if f == "4" else ""} for f in args.format.split(",") for c in args.chapter.split(",")]
    for scan_id in scan_ids:
        for fmt in formats:
            download_report(scan_id, fmt)

if __name__ == "__main__":
    main()