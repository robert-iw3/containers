import configparser
import sys

import requests

config = configparser.ConfigParser()
config.read('../config/config.ini')

CRIBL_HOST = config['cribl']['host']
CRIBL_USER = config['cribl']['user']
CRIBL_PASS = config['cribl']['pass']
PIPELINE_ID = config.get('csv', 'pipeline_id')
PIPELINE_GROUP = config.get('csv', 'pipeline_group', fallback='default')
PIPELINE_VARIANT = config.get('csv', 'pipeline_variant', fallback='logs')
PIPELINE_ID_VARIANT = f"{PIPELINE_ID}_{PIPELINE_VARIANT}"

login = requests.post(f"{CRIBL_HOST}/api/v1/auth/login",
                      json={'username': CRIBL_USER, 'password': CRIBL_PASS}, verify=False)
login.raise_for_status()
AUTH_HEADERS = {'Authorization': f"Bearer {login.json()['token']}"}

response = requests.get(
    f"{CRIBL_HOST}/api/v1/m/{PIPELINE_GROUP}/pipelines/{PIPELINE_ID_VARIANT}",
    headers=AUTH_HEADERS, verify=False,
)
if response.status_code == 200:
    print(f"Pipeline {PIPELINE_ID_VARIANT} exists")
else:
    print(f"Pipeline {PIPELINE_ID_VARIANT} not found (HTTP {response.status_code})")
    sys.exit(1)
