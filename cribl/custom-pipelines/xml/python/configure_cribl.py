import os
import time
import logging
import configparser
import requests
import json
from cribl import CriblClient

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
    XML_DIR = config['xml']['dir']
    FILE_FILTER = config.get('xml', 'file_filter', fallback='*.xml')
    TRACKING_FIELD = config.get('xml', 'tracking_field', fallback='modtime')
    PIPELINE_ID = config.get('xml', 'pipeline_id', fallback='my_xml_pipeline')
    PIPELINE_GROUP = config.get('xml', 'pipeline_group', fallback='local')
    SOURCE_TAG = config.get('xml', 'source_tag', fallback='xml_files')
    AGG_INTERVAL = config.get('xml', 'aggregate_interval', fallback='1m')
    SAMPLE_RATE = config.get('xml', 'sample_rate', fallback=0.5)
    LIMIT_EVENTS = config.get('xml', 'limit_max_events', fallback=100000)
    ERROR_OUTPUT = config.get('xml', 'error_output', fallback='error_destination')
    MAIN_OUTPUT = config.get('xml', 'main_output', fallback='main_destination')
    PIPELINE_VARIANT = config.get('xml', 'pipeline_variant', fallback='logs')
except KeyError as e:
    logging.error(f"Missing key in {INI_FILE}: {e}")
    exit(1)

logging.info(f"Loaded: CRIBL_HOST={CRIBL_HOST}, USER={CRIBL_USER}, PASS=****")
logging.info(f"Loaded: XML_DIR={XML_DIR}, FILE_FILTER={FILE_FILTER}, TRACKING_FIELD={TRACKING_FIELD}")
logging.info(f"Loaded: PIPELINE_ID={PIPELINE_ID}, GROUP={PIPELINE_GROUP}")
logging.info(f"Loaded: SOURCE_TAG={SOURCE_TAG}, AGG_INTERVAL={AGG_INTERVAL}, SAMPLE_RATE={SAMPLE_RATE}, LIMIT_EVENTS={LIMIT_EVENTS}")
logging.info(f"Loaded: ERROR_OUTPUT={ERROR_OUTPUT}, MAIN_OUTPUT={MAIN_OUTPUT}")
logging.info(f"Loaded: PIPELINE_VARIANT={PIPELINE_VARIANT}")

client = CriblClient(host=CRIBL_HOST, username=CRIBL_USER, password=CRIBL_PASS)

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

auth = (CRIBL_USER, CRIBL_PASS)
headers = {'Content-Type': 'application/json'}

logging.info(f"Checking/creating pipeline {PIPELINE_ID}")
pipeline_endpoint = f"{CRIBL_HOST}/api/v1/m/{PIPELINE_GROUP}/pipelines"
PIPELINE_ID_VARIANT = f"{PIPELINE_ID}_{PIPELINE_VARIANT}"
check_response = requests.get(f"{pipeline_endpoint}/{PIPELINE_ID_VARIANT}", auth=auth, verify=False)
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

    pipeline_payload = json.loads(pipeline_template)

    def create_pipeline():
        response = requests.post(pipeline_endpoint, auth=auth, json=pipeline_payload, verify=False)
        response.raise_for_status()
    retry_api_call(create_pipeline)

if not os.path.isdir(XML_DIR):
    logging.error(f"XML dir {XML_DIR} not found")
    exit(1)

logging.info("Creating file collector")
collector_id = 'xml_file_collector'
collector_config = {
    'type': 'file',
    'description': 'File Collector for XML files with incremental loads',
    'config': {
        'path': XML_DIR,
        'fileFilter': FILE_FILTER,
        'schedule': '0 2 * * *',
        'stateEnabled': True,
        'trackingColumn': TRACKING_FIELD,
        'incrementalLoad': True,
        'batchSize': 5000,
        'pipelineId': PIPELINE_ID_VARIANT,
        'throttlingRate': '5 MB',
        'maxRetries': 3,
        'retryDelay': 10,
        'connectionTimeout': 30000,
        'requestTimeout': 60000,
        'addFields': {'query_type': PIPELINE_VARIANT}
    }
}
retry_api_call(client.create_collector, collector_id, collector_config)

logging.info("Completed")