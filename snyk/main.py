import argparse
import io
import logging
import os
import subprocess
import sys
import zipfile
from typing import List
import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(command: List[str], cwd: str = None) -> bool:
    """Run a shell command and return True if successful."""
    try:
        result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
        logger.info(result.stdout)
        if result.stderr:
            logger.warning(result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        logger.error(e.stdout)
        logger.error(e.stderr)
        return False

def authenticate_snyk(token: str) -> bool:
    """Authenticate with Snyk using the provided token."""
    return run_command(['snyk', 'auth', token])

def scan_code_base(dir_path: str, all_projects: bool = True, severity_threshold: str = 'medium', json_output: str = None, html_output: str = None) -> bool:
    """Scan a code base directory using Snyk best practices."""
    command = ['snyk', 'test', '--all-projects', '--severity-threshold', severity_threshold]
    if json_output:
        command.extend(['--json-file-output', json_output])
    success = run_command(command, cwd=dir_path)
    if success and html_output:
        run_command(['snyk-to-html', '-i', json_output, '-o', html_output])
    return success

def scan_sast(dir_path: str, severity_threshold: str = 'medium', json_output: str = None, html_output: str = None) -> bool:
    """Perform SAST scan using Snyk Code."""
    command = ['snyk', 'code', 'test', '--severity-threshold', severity_threshold]
    if json_output:
        command.extend(['--json-file-output', json_output])
    success = run_command(command, cwd=dir_path)
    if success and html_output:
        run_command(['snyk-to-html', '-i', json_output, '-o', html_output])
    return success

def find_project_root(unzip_dir: str) -> str:
    """Find the main project directory after unzipping, looking for master/main or similar."""
    for subdir in os.listdir(unzip_dir):
        if 'master' in subdir.lower() or 'main' in subdir.lower():
            return os.path.join(unzip_dir, subdir)
    return unzip_dir  # Fallback to the unzip dir if no match

def download_and_unzip(url: str, target_dir: str) -> str:
    """Download and unzip a codebase from URL."""
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    response = requests.get(url)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        z.extractall(target_dir)
    return find_project_root(target_dir)

def scan_jars(dir_path: str, remote_repo_url: str, project_name_prefix: str = '') -> dict:
    """Scan JAR files with per-file monitoring for custom naming, handling whitespace."""
    detected_jars = []
    undetected_jars = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.endswith('.jar'):
                full_path = os.path.join(root, file)
                project_name = f"{project_name_prefix}{os.path.relpath(full_path, dir_path)}"
                command = ['snyk', 'monitor', '--scan-unmanaged', '--file', full_path, '--project-name', project_name, '--remote-repo-url', remote_repo_url]
                if run_command(command):
                    detected_jars.append(full_path)
                else:
                    undetected_jars.append(full_path)
    return {
        'detected_jars': detected_jars,
        'undetected_jars': undetected_jars,
        'detected_count': len(detected_jars),
        'undetected_count': len(undetected_jars),
    }

def main():
    parser = argparse.ArgumentParser(description='Snyk Scanner: Scan local or remote code bases and JAR files using Snyk in a containerized environment.')
    parser.add_argument('--token', required=True, help='Snyk API token')
    parser.add_argument('--dirs', help='Comma-separated list of directories to scan as code bases')
    parser.add_argument('--sast-dirs', help='Comma-separated list of directories for SAST scans')
    parser.add_argument('--jar-dirs', help='Comma-separated list of directories containing JAR files')
    parser.add_argument('--remote-repo-url', default='', help='Remote repo URL for JAR monitoring')
    parser.add_argument('--severity-threshold', default='medium', help='Severity threshold for scans')
    parser.add_argument('--monitor', action='store_true', help='Upload results to Snyk platform (monitor)')
    parser.add_argument('--url', help='URL to download and scan remote codebase zip')
    parser.add_argument('--code-name', default='report', help='Name for report outputs')
    parser.add_argument('--html-output-dir', default='/reports', help='Directory for HTML report outputs')
    parser.add_argument('--temp-dir', default='/tmp/codebase', help='Temporary directory for remote downloads')

    args = parser.parse_args()

    if not authenticate_snyk(args.token):
        logger.error('Snyk authentication failed')
        sys.exit(1)

    os.makedirs(args.html_output_dir, exist_ok=True)

    scan_dirs = []
    if args.url:
        logger.info(f"Downloading and unzipping from {args.url}")
        project_dir = download_and_unzip(args.url, args.temp_dir)
        scan_dirs.append(project_dir)

    if args.dirs:
        scan_dirs.extend(args.dirs.split(','))

    # Scan code bases
    for dir_path in scan_dirs:
        if not os.path.isdir(dir_path):
            logger.warning(f"Directory not found: {dir_path}")
            continue
        logger.info(f"Scanning code base: {dir_path}")
        json_output = os.path.join(args.html_output_dir, f"{args.code_name}-dependencies.json")
        html_output = os.path.join(args.html_output_dir, f"{args.code_name}-dependencies.html")
        scan_code_base(dir_path, severity_threshold=args.severity_threshold, json_output=json_output, html_output=html_output)
        if args.monitor:
            run_command(['snyk', 'monitor', '--all-projects'], cwd=dir_path)

    # Scan SAST
    sast_dirs = scan_dirs if not args.sast_dirs else args.sast_dirs.split(',')
    for dir_path in sast_dirs:
        if not os.path.isdir(dir_path):
            logger.warning(f"Directory not found: {dir_path}")
            continue
        logger.info(f"Performing SAST scan: {dir_path}")
        json_output = os.path.join(args.html_output_dir, f"{args.code_name}-code-review.json")
        html_output = os.path.join(args.html_output_dir, f"{args.code_name}-code-review.html")
        scan_sast(dir_path, severity_threshold=args.severity_threshold, json_output=json_output, html_output=html_output)

    # Scan JARs
    jar_dirs = scan_dirs if not args.jar_dirs else args.jar_dirs.split(',')
    if jar_dirs and args.remote_repo_url:
        for dir_path in jar_dirs:
            if not os.path.isdir(dir_path):
                logger.warning(f"Directory not found: {dir_path}")
                continue
            logger.info(f"Scanning JARs in: {dir_path}")
            results = scan_jars(dir_path, args.remote_repo_url, project_name_prefix=f"{args.code_name}/")
            logger.info(f"JAR scan results: Detected {results['detected_count']}, Undetected {results['undetected_count']}")
            logger.info("Detected JARs:\n" + '\n'.join(results['detected_jars']))
            logger.info("Undetected JARs:\n" + '\n'.join(results['undetected_jars']))

    logger.info('Scanning completed.')

if __name__ == '__main__':
    main()