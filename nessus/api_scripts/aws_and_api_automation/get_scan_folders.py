import argparse
import json

from nessus import list_scans
from utils import api_request, load_config, logger

config = load_config()
BASE_URL = config["nessus"]["base_url"]

def get_folders():
    return api_request("GET", f"{BASE_URL}/folders")

def main():
    parser = argparse.ArgumentParser(description="Get Nessus folders and scans.")
    args = parser.parse_args()

    folders = get_folders()
    logger.info("Folders:\n" + json.dumps(folders, indent=4))

    scans = list_scans()
    logger.info("Scans:\n" + json.dumps(scans, indent=4))

if __name__ == "__main__":
    main()