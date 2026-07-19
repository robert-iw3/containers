import os
import time
import logging
import configparser
import requests
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler('cribl_config.log'), logging.StreamHandler()])

INI_FILE = '../config/config.ini'
JSON_FILE = '../config/pipeline_config.json'
MAX_RETRIES = 5
BACKOFF = 2

if not os.path.isfile(INI_FILE):
    logging.error(f"INI file {INI_FILE} not found")
    exit(1)

config = configparser.ConfigParser()
config.read(INI_FILE)

try:
    CRIBL_HOST = config['cribl']['host']
    CRIBL_USER = config['cribl']['user']
    CRIBL_PASS = config['cribl']['pass']
    CSV_DIR = config['csv']['dir']
    FILE_FILTER = config.get('csv', 'file_filter', fallback='*.csv')
    DELIMITER = config.get('csv', 'delimiter', fallback=',')
    HAS_HEADER = config.get('csv', 'has_header', fallback=True)
    TRACKING_FIELD = config.get('csv', 'tracking_field', fallback='modtime')
    PIPELINE_ID = config.get('csv', 'pipeline_id', fallback='my_csv_pipeline')
    PIPELINE_GROUP = config.get('csv', 'pipeline_group', fallback='default')
    SOURCE_TAG = config.get('csv', 'source_tag', fallback='csv_files')
    AGG_INTERVAL = config.get('csv', 'aggregate_interval', fallback='1m')
    SAMPLE_RATE = config.get('csv', 'sample_rate', fallback=5)
    LIMIT_EVENTS = config.get('csv', 'limit_max_events', fallback=100000)
    ERROR_OUTPUT = config.get('csv', 'error_output', fallback='error_destination')
    MAIN_OUTPUT = config.get('csv', 'main_output', fallback='default')
    METRICS_OUTPUT = config.get('csv', 'metrics_output', fallback='devnull')
    PIPELINE_VARIANT = config.get('csv', 'pipeline_variant', fallback='logs')
except KeyError as e:
    logging.error(f"Missing key in {INI_FILE}: {e}")
    exit(1)

logging.info(f"Loaded: CRIBL_HOST={CRIBL_HOST}, USER={CRIBL_USER}, PASS=****")
logging.info(f"Loaded: CSV_DIR={CSV_DIR}, FILE_FILTER={FILE_FILTER}, DELIMITER={DELIMITER}, HAS_HEADER={HAS_HEADER}, TRACKING_FIELD={TRACKING_FIELD}")
logging.info(f"Loaded: PIPELINE_ID={PIPELINE_ID}, GROUP={PIPELINE_GROUP}")
logging.info(f"Loaded: SOURCE_TAG={SOURCE_TAG}, AGG_INTERVAL={AGG_INTERVAL}, SAMPLE_RATE={SAMPLE_RATE}, LIMIT_EVENTS={LIMIT_EVENTS}")
logging.info(f"Loaded: ERROR_OUTPUT={ERROR_OUTPUT}, MAIN_OUTPUT={MAIN_OUTPUT}")
logging.info(f"Loaded: PIPELINE_VARIANT={PIPELINE_VARIANT}")


def retry_api_call(func, *args, **kwargs):
    backoff = BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "exists" in str(e):
                logging.warning(f"Resource exists: {str(e)}. Skipping.")
                return
            logging.error(f"Attempt {attempt} failed: {str(e)}")
            if attempt == MAX_RETRIES:
                raise
            time.sleep(backoff)
            backoff *= 2

login = requests.post(f"{CRIBL_HOST}/api/v1/auth/login",
                      json={'username': CRIBL_USER, 'password': CRIBL_PASS}, verify=False)
login.raise_for_status()
AUTH_HEADERS = {'Authorization': f"Bearer {login.json()['token']}"}
headers = {'Content-Type': 'application/json'}

def cribl_post(path, payload):
    rid = payload.get('id')
    if rid:
        check = requests.get(f"{CRIBL_HOST}/api/v1/{path}/{rid}", headers=AUTH_HEADERS, verify=False)
        if check.status_code == 200:
            logging.info(f"{path}/{rid} exists. Skipping creation.")
            return

    def do_post():
        response = requests.post(f"{CRIBL_HOST}/api/v1/{path}", headers=AUTH_HEADERS, json=payload, verify=False)
        if response.status_code in (400, 409) and 'exists' in response.text:
            logging.warning(f"{path}: resource exists. Skipping.")
            return
        response.raise_for_status()
    retry_api_call(do_post)

logging.info(f"Checking/creating pipeline {PIPELINE_ID}")
pipeline_endpoint = f"{CRIBL_HOST}/api/v1/m/{PIPELINE_GROUP}/pipelines"
PIPELINE_ID_VARIANT = f"{PIPELINE_ID}_{PIPELINE_VARIANT}"
check_response = requests.get(f"{pipeline_endpoint}/{PIPELINE_ID_VARIANT}", headers=AUTH_HEADERS, verify=False)
if check_response.status_code == 200:
    logging.info("Pipeline exists. Skipping creation.")
else:
    with open(JSON_FILE, 'r') as f:
        pipeline_template = f.read()

    pipeline_template = pipeline_template.replace('{{pipeline_id}}', PIPELINE_ID_VARIANT)
    pipeline_template = pipeline_template.replace('{{source_tag}}', SOURCE_TAG)
    pipeline_template = pipeline_template.replace('{{aggregate_interval}}', AGG_INTERVAL)
    pipeline_template = pipeline_template.replace('{{sample_rate}}', str(SAMPLE_RATE))
    pipeline_template = pipeline_template.replace('{{limit_max_events}}', str(LIMIT_EVENTS))
    pipeline_template = pipeline_template.replace('{{error_output}}', ERROR_OUTPUT)
    pipeline_template = pipeline_template.replace('{{main_output}}', MAIN_OUTPUT)
    pipeline_template = pipeline_template.replace('{{metrics_destination}}', METRICS_OUTPUT)
    pipeline_template = pipeline_template.replace('{{delimiter}}', DELIMITER)
    pipeline_template = pipeline_template.replace('{{has_header}}', str(HAS_HEADER).lower())

    pipeline_payload = json.loads(pipeline_template)

    def create_pipeline():
        response = requests.post(pipeline_endpoint, headers=AUTH_HEADERS, json=pipeline_payload, verify=False)
        response.raise_for_status()
    retry_api_call(create_pipeline)

if not os.path.isdir(CSV_DIR):
    logging.error(f"CSV dir {CSV_DIR} not found")
    exit(1)

logging.info("Creating file collector")
collector_id = 'csv_file_collector'
collector_payload = {
    'id': collector_id,
    'type': 'collection',
    'ttl': '4h',
    'removeFields': [],
    'resumeOnBoot': False,
    'schedule': {
        'cronSchedule': '0 2 * * *', 'maxConcurrentRuns': 1, 'skippable': True,
        'run': {
            'rescheduleDroppedTasks': True, 'maxTaskReschedule': 1, 'logLevel': 'info',
            'jobTimeout': '0', 'mode': 'run', 'timeRangeType': 'relative',
            'timestampTimezone': 'UTC', 'expression': 'true',
            'minTaskSize': '1MB', 'maxTaskSize': '10MB',
        },
    },
    'collector': {'type': 'filesystem', 'conf': {'path': CSV_DIR, 'extractors': [], 'filenames': [FILE_FILTER]}},
    'input': {
        'type': 'collection', 'staleChannelFlushMs': 10000, 'sendToRoutes': False,
        'preprocess': {'disabled': True}, 'throttleRatePerSec': '0',
        'pipeline': PIPELINE_ID_VARIANT, 'output': 'default',
    },
}
cribl_post(f"m/{PIPELINE_GROUP}/lib/jobs", collector_payload)

logging.info("Completed")
