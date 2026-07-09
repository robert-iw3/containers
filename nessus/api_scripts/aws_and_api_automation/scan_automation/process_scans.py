import csv
import io
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import boto3
from nessus import download_report, list_scans, prepare_export
from utils import load_config, logger
from typing import List, Dict

config = load_config()

@lru_cache(maxsize=None)
def logs_client():
    return boto3.client("logs", region_name=config["aws"]["region"])

def create_log_stream(group_name: str, stream_name: str) -> str:
    try:
        logs_client().create_log_stream(logGroupName=group_name, logStreamName=stream_name)
    except logs_client().exceptions.ResourceAlreadyExistsException:
        pass
    response = logs_client().describe_log_streams(logGroupName=group_name, logStreamNamePrefix=stream_name)
    return response["logStreams"][0].get("uploadSequenceToken", "0")

def process_csv(csv_text: str, scan: Dict):
    group_name = config["aws"]["log_group"]
    stream_name = f"{scan['last_modification_date']}-{scan['name']}"
    token = create_log_stream(group_name, stream_name)
    events = []

    with io.StringIO(csv_text) as f:
        reader = csv.reader(f)
        for row in reader:
            events.append({
                "timestamp": scan["last_modification_date"] * 1000,
                "message": ",".join(row).replace("\n", " "),
            })
            if len(events) >= 9999:
                token = put_log_events(group_name, stream_name, events, token)
                events = []
    if events:
        put_log_events(group_name, stream_name, events, token)

def put_log_events(group: str, stream: str, events: List[Dict], token: str) -> str:
    response = logs_client().put_log_events(
        logGroupName=group, logStreamName=stream, logEvents=events, sequenceToken=token
    )
    return response["nextSequenceToken"]

def process_scan(scan: Dict):
    if scan["status"] == "completed":
        logger.info(f"Preparing export for {scan['name']}")
        token_response = prepare_export(scan["id"])
        csv_text = download_report(token_response["token"])
        process_csv(csv_text, scan)
    elif scan["status"] == "empty":
        logger.warning(f"Scan {scan['name']} has not run.")

def find_scans():
    scans = list_scans()["scans"]
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_scan, scans)

def main(event=None, context=None):
    logger.info("Processing scans and sending to CloudWatch...")
    find_scans()

if __name__ == "__main__":
    main()