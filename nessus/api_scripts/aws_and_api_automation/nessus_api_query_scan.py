import argparse
import pprint
from nessus import list_scans, get_ssm_param
from utils import api_request, load_config, logger

config = load_config()
BASE_URL = config["nessus"]["base_url"]
HEADERS = {"Content-type": "application/json", "X-ApiKeys": f"accessKey={get_ssm_param('/nessus/access_key')}; secretKey={get_ssm_param('/nessus/secret_key')}"}

def query_vulnerabilities(scan_id: int = None):
    scans = list_scans()["scans"] if not scan_id else [next(s for s in list_scans()["scans"] if s["id"] == scan_id)]
    for scan in scans:
        hosts = api_request("GET", f"{BASE_URL}/scans/{scan['id']}", headers=HEADERS)["hosts"]
        for host in hosts:
            host_details = api_request("GET", f"{BASE_URL}/scans/{scan['id']}/hosts/{host['host_id']}", headers=HEADERS)
            for vuln in host_details["vulnerabilities"]:
                if vuln["severity"] > 0:
                    output = {"host": vuln["hostname"], "vulnerability": vuln["plugin_name"], "severity": vuln["severity"]}
                    pprint.pprint(output)

def main():
    parser = argparse.ArgumentParser(description="Query Nessus scan vulnerabilities.")
    parser.add_argument("--scan-id", type=int, help="Specific scan ID")
    args = parser.parse_args()

    query_vulnerabilities(args.scan_id)

if __name__ == "__main__":
    main()