#!/usr/bin/env python3
"""
Vulnerability Management Pipeline using Tenable Nessus

This script serves as an automation pipeline for vulnerability management phases:
1. Discovery/Identification: Schedule and run scans.
2. Assessment: Download and analyze scan results.
3. Prioritization: Rank vulnerabilities based on severity, CVSS, etc.
4. Remediation: Generate reports with remediation suggestions (integrate with ticketing if needed).
5. Verification: Trigger re-scans and compare results.

Requirements:
- pip install pytenable requests boto3 toml
- Set environment variables or use SSM for NESSUS_URL, ACCESS_KEY, SECRET_KEY.

Usage:
- python pipeline.py --phase all --config scan.toml
- Or as Lambda: main(event, context)
"""

import logging
import os
import time
import csv
import io
import json
from typing import List, Dict, Optional
from functools import lru_cache
from datetime import datetime
import argparse
import toml
import boto3
from tenable.nessus import Nessus
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from tenacity import retry, stop_after_attempt, wait_exponential
from jira import JIRA
from servicenow import ServiceNowClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AWS Clients
@lru_cache(maxsize=None)
def ssm_client():
    return boto3.client('ssm')

@lru_cache(maxsize=None)
def logs_client():
    return boto3.client('logs')

@lru_cache(maxsize=None)
def ec2_client():
    return boto3.client('ec2')

# Load secrets
def get_param(name: str, secure: bool = True) -> str:
    try:
        if os.getenv(name.upper()):
            return os.getenv(name.upper())
        param_name = f"/nessus/{name}"
        response = ssm_client().get_parameter(Name=param_name, WithDecryption=secure)
        return response['Parameter']['Value']
    except (ssm_client().exceptions.ParameterNotFound, FileNotFoundError):
        try:
            config = toml.load('nessus_config.toml')
            if name == 'url':
                return config['nessus']['url']
            elif name == 'access_key':
                return config['nessus']['api_keys']['access_key']
            elif name == 'secret_key':
                return config['nessus']['api_keys']['secret_key']
            elif name == 'username':
                return config['nessus']['credentials']['username']
            elif name == 'password':
                return config['nessus']['credentials']['password']
            elif name == 'jira_url':
                return config['ticketing']['jira']['url']
            elif name == 'jira_token':
                return config['ticketing']['jira']['token']
            elif name == 'servicenow_url':
                return config['ticketing']['servicenow']['url']
            elif name == 'servicenow_username':
                return config['ticketing']['servicenow']['username']
            elif name == 'servicenow_password':
                return config['ticketing']['servicenow']['password']
            raise ValueError(f"Parameter {name} not found")
        except (FileNotFoundError, KeyError) as e:
            logger.error(f"Failed to load {name}: {e}")
            raise

@lru_cache(maxsize=1)
def nessus_client() -> Nessus:
    try:
        config = toml.load('nessus_config.toml')
        verify_ssl = config['nessus'].get('verify_ssl', False)
        url = get_param('url')
        session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        try:
            access_key = get_param('access_key')
            secret_key = get_param('secret_key')
            return Nessus(url=url, access_key=access_key, secret_key=secret_key, session=session, verify_ssl=verify_ssl)
        except ValueError:
            username = get_param('username')
            password = get_param('password')
            return Nessus(url=url, username=username, password=password, session=session, verify_ssl=verify_ssl)
    except Exception as e:
        logger.error(f"Failed to initialize Nessus client: {e}")
        raise

def get_jira_client() -> Optional[JIRA]:
    try:
        jira_url = get_param('jira_url')
        jira_token = get_param('jira_token')
        return JIRA(server=jira_url, token_auth=jira_token)
    except Exception as e:
        logger.warning(f"Failed to initialize Jira client: {e}")
        return None

def get_servicenow_client() -> Optional[ServiceNowClient]:
    try:
        servicenow_url = get_param('servicenow_url')
        username = get_param('servicenow_username')
        password = get_param('servicenow_password')
        return ServiceNowClient(servicenow_url, username, password)
    except Exception as e:
        logger.warning(f"Failed to initialize ServiceNow client: {e}")
        return None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def schedule_scans(config_file: str = 'scan.toml') -> List[Dict]:
    try:
        config = toml.load(config_file)
        if not config:
            raise ValueError("Empty scan configuration")
        nessus = nessus_client()
        created_scans = []

        policies = nessus.policies.list()
        policy_id = next((p['id'] for p in policies if p['name'] == 'standard_scan'), None)
        if not policy_id:
            with open('standard_scan_template.json', 'r') as f:
                policy_template = json.load(f)
            policy_id = nessus.policies.create(policy_template)['id']
            logger.info(f"Created new policy with ID: {policy_id}")

        for scan_name, scan_config in config.items():
            if not all(k in scan_config for k in ['name', 'enabled', 'text_targets']):
                raise ValueError(f"Invalid scan config for {scan_name}")
            scan_payload = {
                'uuid': scan_config.get('uuid', ''),
                'settings': {
                    'name': scan_name,
                    'enabled': scan_config['enabled'],
                    'policy_id': policy_id,
                    'text_targets': scan_config['text_targets'],
                    'launch': scan_config.get('launch', 'ON_DEMAND'),
                    **({'rrules': f"FREQ={scan_config['rrules']['freq']};INTERVAL={scan_config['rrules']['interval']};BYDAY={scan_config['rrules']['byday']}"}
                       if 'rrules' in scan_config else {})
                }
            }

            existing_scans = nessus.scans.list()
            existing = next((s for s in existing_scans if s['name'] == scan_name), None)

            if existing:
                nessus.scans.configure(existing['id'], scan_payload)
                logger.info(f"Updated scan: {scan_name}")
            else:
                response = nessus.scans.create(scan_payload)
                created_scans.append(response)
                logger.info(f"Created scan: {scan_name} with ID {response['id']}")

        for scan in created_scans:
            nessus.scans.launch(scan['id'])

        return created_scans
    except Exception as e:
        logger.error(f"Failed to schedule scans: {e}")
        raise

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def assess_scans(folder_id: Optional[int] = None, min_severity: int = 0) -> List[Dict]:
    nessus = nessus_client()
    scans = nessus.scans.list(folder_id=folder_id) or []
    if not scans:
        logger.warning("No scans found")
        return []

    results = []
    for scan in scans:
        if scan['status'] == 'completed':
            try:
                export_id = nessus.scans.export_request(scan['id'], format='csv')
                while nessus.scans.export_status(scan['id'], export_id) != 'ready':
                    time.sleep(5)
                csv_data = nessus.scans.export_download(scan['id'], export_id)

                vulnerabilities = []
                with io.StringIO(csv_data) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            if int(row.get('severity', 0)) >= min_severity:
                                vulnerabilities.append(row)
                        except (ValueError, KeyError) as e:
                            logger.warning(f"Skipping invalid row in scan {scan['id']}: {e}")

                results.append({'scan_id': scan['id'], 'name': scan['name'], 'vulns': vulnerabilities})
                logger.info(f"Assessed scan {scan['name']}: {len(vulnerabilities)} vulnerabilities found")
            except Exception as e:
                logger.error(f"Failed to assess scan {scan['id']}: {e}")
    return results

def prioritize_vulns(assessments: List[Dict]) -> List[Dict]:
    if not assessments:
        logger.warning("No assessments to prioritize")
        return []

    prioritized = []
    for assessment in assessments:
        try:
            sorted_vulns = sorted(
                assessment['vulns'],
                key=lambda v: (
                    float(v.get('cvss', 0)) or 0,
                    v.get('risk', 'None'),
                    v.get('exploitable_with', 'No')
                ),
                reverse=True
            )
            prioritized.append({'scan_id': assessment['scan_id'], 'prioritized_vulns': sorted_vulns})
        except Exception as e:
            logger.error(f"Failed to prioritize vulnerabilities for scan {assessment['scan_id']}: {e}")

    logger.info(f"Prioritized {sum(len(a['prioritized_vulns']) for a in prioritized)} vulnerabilities")
    return prioritized

def create_jira_tickets(prioritized: List[Dict], project_key: str = 'VULN') -> None:
    jira = get_jira_client()
    if not jira:
        return

    for prio in prioritized:
        for vuln in prio['prioritized_vulns']:
            try:
                issue_dict = {
                    'project': {'key': project_key},
                    'summary': f"Vulnerability: {vuln.get('plugin_name', 'Unknown')}",
                    'description': f"Severity: {vuln.get('severity', '0')}\nCVSS: {vuln.get('cvss', '0.0')}\nSolution: {vuln.get('solution', 'No solution provided')}",
                    'issuetype': {'name': 'Task'}
                }
                jira.create_issue(fields=issue_dict)
                logger.info(f"Created Jira ticket for {vuln.get('plugin_name')}")
            except Exception as e:
                logger.error(f"Failed to create Jira ticket for {vuln.get('plugin_name')}: {e}")

def create_servicenow_tickets(prioritized: List[Dict]) -> None:
    sn_client = get_servicenow_client()
    if not sn_client:
        return

    for prio in prioritized:
        for vuln in prio['prioritized_vulns']:
            try:
                ticket = {
                    'short_description': f"Vulnerability: {vuln.get('plugin_name', 'Unknown')}",
                    'description': f"Severity: {vuln.get('severity', '0')}\nCVSS: {vuln.get('cvss', '0.0')}\nSolution: {vuln.get('solution', 'No solution provided')}",
                    'urgency': '1' if int(vuln.get('severity', 0)) >= 3 else '2'
                }
                sn_client.create_incident(ticket)
                logger.info(f"Created ServiceNow ticket for {vuln.get('plugin_name')}")
            except Exception as e:
                logger.error(f"Failed to create ServiceNow ticket for {vuln.get('plugin_name')}: {e}")

def generate_remediation_reports(prioritized: List[Dict], output_dir: str = 'reports', formats: List[str] = ['json']) -> None:
    os.makedirs(output_dir, exist_ok=True)
    nessus = nessus_client()
    try:
        config = toml.load('nessus_config.toml')
        report_formats = config.get('nessus', {}).get('report', {}).get('formats', formats)
        chapters = config.get('nessus', {}).get('report', {}).get('chapters', ['vuln_by_host'])
        db_password = config.get('nessus', {}).get('report', {}).get('db_password', 'nessus')
    except FileNotFoundError:
        report_formats = formats
        chapters = ['vuln_by_host']
        db_password = 'nessus'

    for prio in prioritized:
        scan_id = prio['scan_id']
        for fmt in report_formats:
            try:
                if fmt == 'json':
                    report_file = f"{output_dir}/{scan_id}_remediation.json"
                    with open(report_file, 'w') as f:
                        json.dump({
                            'vulnerabilities': [
                                {
                                    'plugin_name': v.get('plugin_name', 'Unknown'),
                                    'severity': v.get('severity', '0'),
                                    'solution': v.get('solution', 'No solution provided'),
                                    'cvss': v.get('cvss', '0.0')
                                } for v in prio['prioritized_vulns']
                            ]
                        }, f, indent=4)
                    logger.info(f"Generated JSON report: {report_file}")
                else:
                    export_params = {'format': fmt}
                    if fmt in ['html', 'nessus']:
                        export_params['chapters'] = ','.join(chapters)
                    if fmt == 'nessus':
                        export_params['password'] = db_password
                    export_id = nessus.scans.export_request(scan_id, **export_params)
                    while nessus.scans.export_status(scan_id, export_id) != 'ready':
                        time.sleep(5)
                    data = nessus.scans.export_download(scan_id, export_id)
                    report_file = f"{output_dir}/{scan_id}_remediation.{fmt}"
                    with open(report_file, 'wb' if fmt in ['pdf', 'nessus', 'html'] else 'w') as f:
                        f.write(data)
                    logger.info(f"Generated {fmt} report: {report_file}")
            except Exception as e:
                logger.error(f"Failed to generate {fmt} report for scan {scan_id}: {e}")

    create_jira_tickets(prioritized)
    create_servicenow_tickets(prioritized)
    log_to_cloudwatch(prioritized)

def log_to_cloudwatch(data: List[Dict]) -> None:
    group_name = '/gds/nessus-scans'
    stream_name = f"{datetime.now().strftime('%Y-%m-%d')}-vuln-pipeline"
    try:
        logs_client().create_log_stream(logGroupName=group_name, logStreamName=stream_name)
    except logs_client().exceptions.ResourceAlreadyExistsException:
        pass

    events = [{'timestamp': int(time.time() * 1000), 'message': json.dumps(d)} for d in data]
    response = logs_client().describe_log_streams(logGroupName=group_name, logStreamNamePrefix=stream_name)
    token = response['logStreams'][0].get('uploadSequenceToken', '0')

    try:
        logs_client().put_log_events(
            logGroupName=group_name,
            logStreamName=stream_name,
            logEvents=events,
            sequenceToken=token
        )
        logger.info("Logged results to CloudWatch")
    except Exception as e:
        logger.error(f"Failed to log to CloudWatch: {e}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def verify_remediation(scan_ids: List[int], previous_assessments: List[Dict]) -> Dict:
    nessus = nessus_client()
    verifications = {}

    for scan_id in scan_ids:
        try:
            nessus.scans.launch(scan_id)
            while nessus.scans.details(scan_id)['info']['status'] != 'completed':
                time.sleep(30)

            new_assessments = assess_scans(min_severity=0)
            new_assessment = next((a for a in new_assessments if a['scanlap_id'] == scan_id), {})
            prev = next((a for a in previous_assessments if a['scan_id'] == scan_id), {})
            fixed = len(prev.get('vulns', [])) - len(new_assessment.get('vulns', []))
            verifications[scan_id] = {'fixed': fixed, 'remaining': len(new_assessment.get('vulns', []))}
            logger.info(f"Verification for scan {scan_id}: {fixed} fixed, {len(new_assessment.get('vulns', []))} remaining")
        except Exception as e:
            logger.error(f"Failed to verify scan {scan_id}: {e}")

    return verifications

def run_pipeline(phases: List[str], config_file: str, nessus_config: str, min_severity: int) -> None:
    try:
        toml.load(nessus_config)  # Validate config
        if 'discovery' in phases or 'all' in phases:
            schedule_scans(config_file)

        if 'assessment' in phases or 'all' in phases:
            assessments = assess_scans(min_severity=min_severity)

        if 'prioritization' in phases or 'all' in phases:
            prioritized = prioritize_vulns(assessments)

        if 'remediation' in phases or 'all' in phases:
            generate_remediation_reports(prioritized)

        if 'verification' in phases or 'all' in phases:
            scan_ids = [a['scan_id'] for a in assessments]
            verify_remediation(scan_ids, assessments)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vulnerability Management Pipeline")
    parser.add_argument('--phase', choices=['all', 'discovery', 'assessment', 'prioritization', 'remediation', 'verification'], default='all', nargs='+')
    parser.add_argument('--config', default='scan.toml', help="TOML config file for scans")
    parser.add_argument('--nessus-config', default='nessus_config.toml', help="TOML config file for Nessus server")
    parser.add_argument('--min-severity', type=int, default=0, help="Minimum severity for assessments (0-4)")
    return parser.parse_args()

def main(event: Optional[Dict] = None, context: Optional[Dict] = None) -> Dict:
    args = parse_args() if not event else argparse.Namespace(
        phase=event.get('phase', ['all']),
        config=event.get('config', 'scan.toml'),
        nessus_config=event.get('nessus_config', 'nessus_config.toml'),
        min_severity=event.get('min_severity', 0)
    )
    logger.info(f"Running pipeline with phases: {args.phase}")
    run_pipeline(args.phase, args.config, args.nessus_config, args.min_severity)
    return {'status': 'success', 'phases': args.phase}

if __name__ == '__main__':
    main()