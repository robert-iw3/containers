import argparse
import logging
import os
import json
import yaml
import pandas as pd
from datetime import datetime
from pathlib import Path
import ansible_runner
import subprocess
import yamllint.config
from tqdm import tqdm
import zipfile
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import socket
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deploy_gotestwaf.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GoTestWAFDeployer:
    def __init__(self, args):
        self.args = args
        self.config = self.load_config()
        self.urls = self.read_urls()
        self.output_dir = Path(self.args.output_dir or self.config.get('output_dir', 'reports'))
        self.parallel = self.args.parallel or self.config.get('parallel', min(psutil.cpu_count() or 10, 20))
        self.batch_size = self.config.get('batch_size', 50)
        self.retries = self.config.get('retries', 3)
        self.timeout = self.config.get('timeout', 3600)

    def load_config(self):
        """Load configuration from deploy_config.yaml"""
        config_path = 'deploy_config.yaml'
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
                logger.info("Loaded configuration from deploy_config.yaml")
                return config
        except FileNotFoundError:
            logger.warning("deploy_config.yaml not found, using defaults")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Invalid deploy_config.yaml: {str(e)}")
            raise

    def read_urls(self):
        """Read URLs from input (single URL or file)"""
        url_input = self.args.urls
        try:
            if os.path.isfile(url_input):
                with open(url_input, 'r') as f:
                    urls = [line.strip() for line in f if line.strip()]
            else:
                urls = [url_input]
            # Validate URLs
            valid_urls = []
            for url in urls:
                try:
                    socket.gethostbyname(url.split('/')[2] if '//' in url else url)
                    valid_urls.append(url)
                except socket.gaierror:
                    logger.warning(f"Invalid URL skipped: {url}")
            if not valid_urls:
                raise ValueError("No valid URLs provided")
            logger.info(f"Loaded {len(valid_urls)} valid URLs")
            return valid_urls
        except Exception as e:
            logger.error(f"Failed to read URLs: {str(e)}")
            raise

    def validate_yaml(self, file_path):
        """Validate YAML file syntax using yamllint"""
        try:
            config = yamllint.config.YamlLintConfig('extends: default')
            with open(file_path, 'r') as f:
                yaml_content = f.read()
                result = subprocess.run(['yamllint', '-f', 'parsable', '-'], input=yaml_content, text=True, capture_output=True)
                if result.returncode != 0:
                    logger.error(f"YAML validation failed for {file_path}:\n{result.stderr}")
                    raise ValueError("Invalid YAML syntax")
                logger.info(f"YAML validation passed for {file_path}")
        except FileNotFoundError:
            logger.error(f"YAML file not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"YAML validation error: {str(e)}")
            raise

    def validate_ansible_playbook(self, playbook_path):
        """Validate Ansible playbook syntax"""
        try:
            result = subprocess.run(['ansible-playbook', '--syntax-check', playbook_path], capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"Ansible playbook syntax check failed:\n{result.stderr}")
                raise ValueError("Invalid Ansible playbook syntax")
            logger.info(f"Ansible playbook syntax check passed for {playbook_path}")
        except subprocess.TimeoutExpired:
            logger.error("Ansible playbook syntax check timed out")
            raise
        except Exception as e:
            logger.error(f"Ansible playbook validation error: {str(e)}")
            raise

    def validate_docker_compose(self):
        """Validate Docker Compose configuration"""
        try:
            result = subprocess.run(['docker-compose', 'config'], capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"Docker Compose validation failed:\n{result.stderr}")
                raise ValueError("Invalid Docker Compose configuration")
            logger.info("Docker Compose configuration validated")
        except subprocess.TimeoutExpired:
            logger.error("Docker Compose validation timed out")
            raise
        except Exception as e:
            logger.error(f"Docker Compose validation error: {str(e)}")
            raise

    def check_image_version(self):
        """Check if GoTestWAF image exists, build if missing"""
        if self.args.deploy_type == 'kubernetes':
            logger.info("Kubernetes deploy type: assuming gotestwaf image is already available in-cluster, skipping local build")
            return
        cmd = 'docker' if self.args.deploy_type == 'docker' else 'podman'
        try:
            result = subprocess.run([cmd, 'images', '-q', 'gotestwaf'], capture_output=True, text=True, timeout=30)
            if not result.stdout.strip():
                logger.info("GoTestWAF image not found, building...")
                subprocess.run([cmd, 'build', '-t', 'gotestwaf', '.'], check=True, timeout=3600)
            else:
                logger.info("GoTestWAF image found, skipping build")
        except subprocess.TimeoutExpired:
            logger.error("Image build timed out")
            raise
        except Exception as e:
            logger.error(f"Failed to check/build image: {str(e)}")
            raise

    def ansible_extravars(self):
        """Build the extravars passed to the static deploy_gotestwaf.yml playbook."""
        return {
            'deploy_type': self.args.deploy_type,
            'urls': self.urls,
            'output_dir': str(self.output_dir),
            'container_cmd': (
                'docker' if self.args.deploy_type == 'docker'
                else 'podman' if self.args.deploy_type == 'podman'
                else 'kubectl'
            ),
            'parallel': self.parallel,
            'batch_size': self.batch_size,
            'retries': self.retries,
            'timeout': self.timeout,
        }

    def validate_playbook(self):
        """Validate the static Ansible playbook's syntax before running it"""
        playbook_path = 'deploy_gotestwaf.yml'
        self.validate_yaml(playbook_path)
        self.validate_ansible_playbook(playbook_path)
        return playbook_path

    def run_ansible_playbook(self, playbook_path):
        """Execute Ansible playbook using ansible-runner"""
        if self.args.dry_run:
            logger.info("Dry run mode, skipping playbook execution")
            return
        try:
            logger.info(f"Running Ansible playbook: {playbook_path}")
            result = ansible_runner.run(
                private_data_dir='.',
                playbook=playbook_path,
                extravars=self.ansible_extravars(),
                quiet=False,
                timeout=self.timeout
            )
            if result.status == 'successful':
                logger.info("Ansible playbook executed successfully")
            else:
                logger.error(f"Ansible playbook failed with status: {result.status}")
                raise RuntimeError("Ansible playbook execution failed")
        except Exception as e:
            logger.error(f"Ansible playbook execution failed: {str(e)}")
            raise

    def process_report(self, url, timestamp):
        """Process reports for a single URL"""
        json_report = self.output_dir / f"gotestwaf_{url.replace('/', '_')}.json"
        html_report = self.output_dir / f"gotestwaf_{url.replace('/', '_')}.html"

        if not json_report.exists():
            logger.warning(f"No JSON report found for {url}")
            return None

        try:
            with open(json_report, 'r') as f:
                data = json.load(f)

            # Generate CSV and XLSX
            df = pd.json_normalize(data)
            fields = self.config.get('report_fields', None)
            if fields:
                df = df[[col for col in fields if col in df.columns]]

            csv_path = self.output_dir / f"gotestwaf_{url.replace('/', '_')}_{timestamp}.csv"
            xlsx_path = self.output_dir / f"gotestwaf_{url.replace('/', '_')}_{timestamp}.xlsx"
            df.to_csv(csv_path, index=False)
            df.to_excel(xlsx_path, index=False)
            logger.info(f"Generated CSV and XLSX reports for {url}")

            # Generate YAML
            yaml_path = self.output_dir / f"gotestwaf_{url.replace('/', '_')}_{timestamp}.yaml"
            with open(yaml_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
            logger.info(f"Generated YAML report for {url}")

            return data
        except json.JSONDecodeError:
            logger.error(f"Corrupted JSON report for {url}")
            return None
        except Exception as e:
            logger.error(f"Failed to process report for {url}: {str(e)}")
            return None

    def generate_summary_report(self, report_data, timestamp):
        """Generate a consolidated summary report"""
        try:
            summary = []
            for url, data in report_data.items():
                if data:
                    summary.append({
                        'url': url,
                        'tests_run': data.get('tests_run', 0),
                        'vulnerabilities_found': data.get('vulnerabilities_found', 0),
                        'timestamp': timestamp
                    })

            if not summary:
                logger.warning("No valid reports to summarize")
                return

            summary_df = pd.DataFrame(summary)
            summary_csv = self.output_dir / f"summary_report_{timestamp}.csv"
            summary_xlsx = self.output_dir / f"summary_report_{timestamp}.xlsx"
            summary_yaml = self.output_dir / f"summary_report_{timestamp}.yaml"

            summary_df.to_csv(summary_csv, index=False)
            summary_df.to_excel(summary_xlsx, index=False)
            with open(summary_yaml, 'w') as f:
                yaml.dump(summary, f, default_flow_style=False)
            logger.info("Generated summary reports")

            # Compress reports
            zip_path = self.output_dir / f"reports_{timestamp}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for report in self.output_dir.glob(f"*_{timestamp}.*"):
                    zf.write(report, report.name)
            logger.info(f"Compressed reports to {zip_path}")
        except Exception as e:
            logger.error(f"Failed to generate summary report: {str(e)}")
            raise

    def run(self):
        """Main deployment logic"""
        try:
            if self.args.dry_run:
                logger.info("Performing dry run")
                self.check_image_version()
                self.validate_playbook()
                if self.args.deploy_type in ['docker', 'podman']:
                    self.validate_docker_compose()
                return

            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.check_image_version()
            if self.args.deploy_type in ['docker', 'podman']:
                self.validate_docker_compose()
            playbook_path = self.validate_playbook()
            self.run_ansible_playbook(playbook_path)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_data = {}

            # Process reports in parallel with retries
            with ThreadPoolExecutor(max_workers=self.parallel) as executor:
                future_to_url = {}
                for batch in [self.urls[i:i + self.batch_size] for i in range(0, len(self.urls), self.batch_size)]:
                    for url in tqdm(batch, desc="Processing URLs"):
                        for attempt in range(self.retries):
                            try:
                                future = executor.submit(self.process_report, url, timestamp)
                                future_to_url[future] = url
                                break
                            except Exception as e:
                                logger.warning(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                                if attempt == self.retries - 1:
                                    logger.error(f"Failed to process {url} after {self.retries} attempts")
                                time.sleep(2 ** attempt)  # Exponential backoff

                    for future in as_completed(future_to_url):
                        url = future_to_url[future]
                        try:
                            report_data[url] = future.result()
                        except Exception as e:
                            logger.error(f"Error processing report for {url}: {str(e)}")

            self.generate_summary_report(report_data, timestamp)
        except Exception as e:
            logger.error(f"Deployment failed: {str(e)}")
            raise

def parse_args():
    parser = argparse.ArgumentParser(description="Deploy GoTestWAF to test WAF(s) with Ansible")
    parser.add_argument('--urls', type=str, required=True, help="Single WAF URL or path to file with URLs")
    parser.add_argument('--deploy-type', choices=['docker', 'podman', 'kubernetes'], default='docker',
                        help="Deployment type (default: docker)")
    parser.add_argument('--output-dir', type=str, help="Directory for reports (default: from config)")
    parser.add_argument('--parallel', type=int, help="Number of parallel tasks (default: from config or CPU count)")
    parser.add_argument('--dry-run', action='store_true', help="Validate setup without executing")
    return parser.parse_args()

def main():
    try:
        args = parse_args()
        deployer = GoTestWAFDeployer(args)
        deployer.run()
    except Exception as e:
        logger.critical(f"Critical failure: {str(e)}")
        exit(1)

if __name__ == '__main__':
    main()