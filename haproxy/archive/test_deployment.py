import requests
import yaml
import os
import logging
from typing import Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config(config_file: str) -> Dict:
    default_config = {
        'services': [{'name': 'default', 'backend': 'localhost', 'port': 8080, 'num_servers': 100}],
        'opensearch_host': 'opensearch',
        'opensearch_port': 9200,
        'domain': 'haproxy.example.com'
    }
    if not os.path.exists(config_file):
        logger.warning(f"Config file {config_file} not found, using defaults")
        return default_config
    try:
        with open(config_file, 'r') as f:
            return yaml.safe_load(f) or default_config
    except Exception as e:
        logger.error(f"Failed to load config: {e}, using defaults")
        return default_config

def test_haproxy(config_file: str, host: str = "localhost"):
    config = load_config(config_file)
    services = config.get('services', [])

    # Test SSL health endpoints
    for service in services:
        try:
            url = f"https://{config['domain']}:{service['port']}/health"
            logger.info(f"Testing service {service['name']} SSL health at {url}")
            response = requests.get(url, timeout=5, verify=False)  # Disable verification for self-signed certs
            if response.status_code == 200:
                logger.info(f"Service {service['name']} SSL health check passed")
            else:
                logger.error(f"Service {service['name']} SSL health check failed: {response.status_code}")
        except requests.RequestException as e:
            logger.error(f"Service {service['name']} SSL health check failed: {e}")
            raise

    # Test Prometheus metrics
    try:
        metrics_url = f"http://{host}:8404/metrics"
        logger.info(f"Testing HAProxy metrics at {metrics_url}")
        response = requests.get(metrics_url, timeout=5)
        if response.status_code == 200 and "haproxy" in response.text:
            logger.info("HAProxy metrics endpoint is accessible")
            # Check scalability metrics
            if "haproxy_frontend_session_rate" in response.text and "haproxy_backend_response_time_ms" in response.text:
                logger.info("Scalability metrics (session rate, response time) are present")
            else:
                logger.error("Scalability metrics missing")
        else:
            logger.error(f"HAProxy metrics check failed: {response.status_code}")
    except requests.RequestException as e:
        logger.error(f"HAProxy metrics check failed: {e}")
        raise

    # Test OpenSearch logging
    try:
        os_url = f"http://{config['opensearch_host']}:{config['opensearch_port']}/haproxy-logs/_search"
        logger.info(f"Testing OpenSearch logs at {os_url}")
        response = requests.get(os_url, timeout=5)
        if response.status_code == 200:
            logger.info("OpenSearch logs endpoint is accessible")
        else:
            logger.error(f"OpenSearch logs check failed: {response.status_code}")
    except requests.RequestException as e:
        logger.error(f"OpenSearch logs check failed: {e}")
        raise

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test HAProxy deployment")
    parser.add_argument('--config', default='config.yml', help='Path to configuration file')
    parser.add_argument('--host', default='localhost', help='Host to test services against')
    args = parser.parse_args()

    test_haproxy(args.config, args.host)

if __name__ == "__main__":
    main()