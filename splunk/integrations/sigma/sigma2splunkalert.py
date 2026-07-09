#!/usr/bin/env python3

# Sigma to Splunk Alert Converter
# original author: (@bareiss_patrick)
# Updated 2025 for CIM compliance and multi-source Sigma integration

import sys
import argparse
import os
import yaml
import subprocess
from subprocess import DEVNULL
from jinja2 import Environment, FileSystemLoader
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import git
import tempfile
import requests
from typing import List, Dict, Optional
from pathlib import Path
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sigma2splunkalert.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SigmaRuleValidator:
    @staticmethod
    def validate_rule(rule_data: Dict) -> bool:
        """Validate Sigma rule structure."""
        required_fields = ['title', 'detection']
        return all(field in rule_data for field in required_fields)

class UseCase:
    def __init__(self, sigma_rule: Dict, config: Dict, splunk_search: str, datamodel: Optional[str] = None):
        self.sigma_rule = sigma_rule
        self.config = config
        self.splunk_search = splunk_search
        self.title = sigma_rule.get('title', 'Untitled')
        self.description = sigma_rule.get('description', '')
        self.tags = sigma_rule.get('tags', [])
        self.level = sigma_rule.get('level', 'medium')
        self.fields = sigma_rule.get('fields', [])
        self.datamodel = datamodel
        self.mitre_techniques = [tag for tag in self.tags if tag.startswith('attack.t')]
        self.mitre_tactics = [tag for tag in self.tags if tag.startswith('attack.') and not tag.startswith('attack.t')]

class DetectionRuleConverter:
    @staticmethod
    def convertSigmaRule(sigma_config_path: str, rule_file: str) -> str:
        """Convert a Sigma rule to a Splunk search using sigmac."""
        try:
            cmd = [
                'sigmac',
                '-t', 'splunk',
                '-c', sigma_config_path,
                '--format', 'default',
                rule_file
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to convert {rule_file}: {e.stderr}")
            return ""

    @staticmethod
    def performSearchTransformation(transformations: List[Dict], search: str, sigma_rule: Dict) -> str:
        """Apply search transformations to the Splunk search."""
        for transform in transformations:
            if transform.get('type') == 'whitelist':
                search += f" | search NOT [| inputlookup {transform.get('lookup')}]"
            elif transform.get('type') == 'custom_command':
                search += f" | {transform.get('command')}"
            elif transform.get('type') == 'cim_tags':
                tags = ','.join(sigma_rule.get('tags', []))
                search += f" | eval mitre_tags=\"{tags}\""
        return search

    @staticmethod
    def addToSummaryIndex(search: str, config: Dict, sigma_rule: Dict) -> str:
        """Add summary index action if specified."""
        if config.get('summary_index', {}).get('enabled', False):
            index = config['summary_index'].get('index', 'threat-hunting')
            tags = ','.join([f"sigma_tag={tag}" for tag in sigma_rule.get('tags', [])])
            search += f" | collect index={index} marker=\"{tags},level={sigma_rule.get('level', 'medium')}\""
        return search

    @staticmethod
    def mapToCIMDatamodel(sigma_rule: Dict, sigma_config: Dict) -> Optional[str]:
        """Map Sigma rule to a CIM data model based on tags and fields."""
        datamodels = sigma_config.get('datamodels', {})
        for dm_name, dm_config in datamodels.items():
            dm_tags = set(dm_config.get('tags', []))
            rule_tags = set(sigma_rule.get('tags', []))
            if dm_tags.intersection(rule_tags):
                return dm_name
        return None

def openSigma2SplunkConfiguration(config_path: str) -> Dict:
    """Load Sigma2SplunkAlert configuration."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load configuration {config_path}: {e}")
        return {}

def openSigmaConfiguration(sigma_config_path: str) -> Dict:
    """Load Sigma configuration."""
    try:
        with open(sigma_config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load Sigma configuration {sigma_config_path}: {e}")
        return {}

def loadSigmaRules(input_path: str) -> List[str]:
    """Recursively load Sigma rule files from a directory or file."""
    sigma_files = []
    input_path = Path(input_path)
    if input_path.is_file() and input_path.suffix in ('.yml', '.yaml'):
        sigma_files.append(str(input_path))
    elif input_path.is_dir():
        for file in input_path.rglob('*.yml'):
            sigma_files.append(str(file))
        for file in input_path.rglob('*.yaml'):
            sigma_files.append(str(file))
    return sigma_files

def fetchRemoteSigmaRules(url: str, temp_dir: str) -> str:
    """Fetch Sigma rules from a remote source (Git or URL)."""
    parsed_url = urlparse(url)
    if parsed_url.scheme in ('http', 'https') and url.endswith('.git'):
        try:
            logger.info(f"Cloning repository {url} to {temp_dir}")
            repo = git.Repo.clone_from(url, temp_dir)
            return os.path.join(temp_dir, 'sigma')
        except git.exc.GitCommandError as e:
            logger.error(f"Failed to clone repository {url}: {e}")
            return ""
    elif parsed_url.scheme in ('http', 'https'):
        try:
            logger.info(f"Downloading Sigma rule from {url}")
            response = requests.get(url)
            response.raise_for_status()
            temp_file = os.path.join(temp_dir, os.path.basename(url))
            with open(temp_file, 'w') as f:
                f.write(response.text)
            return temp_file
        except requests.RequestException as e:
            logger.error(f"Failed to download {url}: {e}")
            return ""
    return ""

def generate_savedsearches_conf(detection_rules: List[UseCase], config: Dict) -> str:
    """Generate Splunk savedsearches.conf using Jinja2 template."""
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('savedsearches.conf.j2')
    return template.render(detection_rules=detection_rules, config=config)

def process_rule(file: str, sigma_config_path: str, config: Dict, sigma_config: Dict) -> Optional[UseCase]:
    """Process a single Sigma rule."""
    try:
        with open(file, 'r') as f:
            sigma_rule = yaml.safe_load(f)
        if not SigmaRuleValidator.validate_rule(sigma_rule):
            logger.warning(f"Invalid Sigma rule format: {file}")
            return None
        splunk_search = DetectionRuleConverter.convertSigmaRule(sigma_config_path, file)
        if not splunk_search:
            return None
        splunk_search = DetectionRuleConverter.performSearchTransformation(
            config.get('search_transformations', []), splunk_search, sigma_rule
        )
        splunk_search = DetectionRuleConverter.addToSummaryIndex(splunk_search, config, sigma_rule)
        datamodel = DetectionRuleConverter.mapToCIMDatamodel(sigma_rule, sigma_config)
        return UseCase(sigma_rule, config, splunk_search, datamodel)
    except Exception as e:
        logger.error(f"Error processing {file}: {e}")
        return None

def main(argv):
    parser = argparse.ArgumentParser(
        description='Convert Sigma rules to Splunk Alerts savedsearches.conf configuration with CIM compliance.'
    )
    parser.add_argument('sources', nargs='*', default=['https://github.com/robert-iw3/detection-rules.git'], help='Folders, files, or URLs containing Sigma rules')
    parser.add_argument('--config', '-c', default='config/config.yml', help='Sigma2SplunkAlert configuration file')
    parser.add_argument('--sigma-config', '-sc', default='sigma_config/splunk-all.yml', help='Sigma configuration file')
    parser.add_argument('--output', '-o', default='savedsearches.conf', help='Output file for savedsearches.conf')
    parser.add_argument('--dry-run', action='store_true', help='Preview output without writing to file')
    args = parser.parse_args()

    # Load configurations
    config = openSigma2SplunkConfiguration(args.config)
    sigma_config = openSigmaConfiguration(args.sigma_config)
    if not config or not sigma_config:
        sys.exit(1)

    # Process Sigma sources
    all_files = []
    temp_dirs = []
    for source in args.sources:
        if source.startswith(('http://', 'https://')):
            temp_dir = tempfile.mkdtemp()
            temp_dirs.append(temp_dir)
            source_path = fetchRemoteSigmaRules(source, temp_dir)
            if source_path:
                all_files.extend(loadSigmaRules(source_path))
        else:
            all_files.extend(loadSigmaRules(source))

    # Process rules in parallel
    detection_rules = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_file = {executor.submit(process_rule, file, args.sigma_config, config, sigma_config): file for file in all_files}
        for future in as_completed(future_to_file):
            result = future.result()
            if result:
                detection_rules.append(result)

    # Generate and output savedsearches.conf
    savedsearches_conf = generate_savedsearches_conf(detection_rules, config)
    if args.dry_run:
        print(savedsearches_conf)
    else:
        with open(args.output, 'w') as f:
            f.write(savedsearches_conf)
        logger.info(f"Saved searches written to {args.output}")

    # Clean up temporary directories
    for temp_dir in temp_dirs:
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to clean up {temp_dir}: {e}")

if __name__ == "__main__":
    main(sys.argv)