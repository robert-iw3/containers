import requests
import configparser

config = configparser.ConfigParser()
config.read('../config/config.ini')

CRIBL_HOST = config['cribl']['host']
CRIBL_USER = config['cribl']['user']
CRIBL_PASS = config['cribl']['pass']
PIPELINE_ID = config.get('xml', 'pipeline_id')

auth = (CRIBL_USER, CRIBL_PASS)

response = requests.get(f"{CRIBL_HOST}/api/v1/pipelines/{PIPELINE_ID}", auth=auth, verify=False)
if response.status_code == 200:
  print("Pipeline exists")
else:
  print("Pipeline not found")