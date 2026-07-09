import yaml
import logging
import subprocess
import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional
import re
import stat
import hashlib
import hmac
from jinja2 import Template

logger = logging.getLogger(__name__)

# HTML report template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Kube-bench Report - {{ endpoint }}</title>
    <style>
        body { font-family: Arial, sans-serif; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .pass { color: green; }
        .fail { color: red; }
    </style>
</head>
<body>
    <h1>Kube-bench Report - {{ endpoint }}</h1>
    <table>
        <tr><th>ID</th><th>Description</th><th>Status</th></tr>
        {% for check in checks %}
        <tr>
            <td>{{ check.id }}</td>
            <td>{{ check.description }}</td>
            <td class="{{ 'pass' if check.status == 'PASS' else 'fail' }}">{{ check.status }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

class KubeBenchError(Exception):
    """Custom exception for kube-bench orchestrator errors."""
    pass

class KubeBenchOrchestrator:
    def __init__(self, config_path: str, binary_signature: Optional[str] = None):
        """Initialize orchestrator with config file and optional binary signature.

        Args:
            config_path (str): Path to the YAML configuration file.
            binary_signature (Optional[str]): Expected HMAC signature for kube-bench binary.
        """
        self.config = self.load_config(config_path)
        self.reports_dir = self.sanitize_path(self.config.get('reports_dir', '/tmp/kube-bench-reports'))
        self.log_file = self.sanitize_path(self.config.get('log_file', 'kube_bench_scan.log'))
        self.deployment_type = self.config.get('deployment_type', 'docker')
        self.max_concurrent = self.config.get('max_concurrent_scans', 2)
        self.binary_signature = binary_signature
        os.makedirs(self.reports_dir, exist_ok=True, mode=0o750)
        self.configure_logging()

    def configure_logging(self) -> None:
        """Configure logging with custom log file path."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        os.chmod(self.log_file, 0o640)
        logger.info(f"Logging configured to {self.log_file}")

    def sanitize_path(self, path: str) -> str:
        """Sanitize file paths to prevent directory traversal.

        Args:
            path (str): Input path to sanitize.

        Returns:
            str: Sanitized path.

        Raises:
            KubeBenchError: If path is invalid or contains unsafe characters.
        """
        if not re.match(r'^[a-zA-Z0-9_~/.-]+$', path):
            raise KubeBenchError(f"Invalid characters in path: {path}")
        if '..' in path.split('/'):
            raise KubeBenchError(f"Invalid characters in path: {path}")
        return os.path.abspath(os.path.expanduser(path))

    def validate_endpoint(self, endpoint: str) -> None:
        """Validate endpoint URL to prevent command injection.

        Args:
            endpoint (str): Endpoint to validate.

        Raises:
            KubeBenchError: If endpoint contains unsafe characters.
        """
        if not re.match(r'^[a-zA-Z0-9.-]+$', endpoint):
            raise KubeBenchError(f"Invalid endpoint: {endpoint}")

    def verify_binary_signature(self, binary_path: str) -> None:
        """Verify kube-bench binary signature.

        Args:
            binary_path (str): Path to kube-bench binary.

        Raises:
            KubeBenchError: If signature verification fails.
        """
        if not self.binary_signature:
            logger.warning("No binary signature provided, skipping verification")
            return

        hmac_key = os.getenv('KUBE_BENCH_HMAC_KEY')
        if not hmac_key:
            raise KubeBenchError(
                "KUBE_BENCH_HMAC_KEY is not set; a binary signature was provided but there is "
                "no secret key to verify it against"
            )

        try:
            with open(binary_path, 'rb') as f:
                binary_data = f.read()
            computed_signature = hmac.new(
                hmac_key.encode(), binary_data, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(computed_signature, self.binary_signature):
                raise KubeBenchError("Binary signature verification failed")
            logger.info("Binary signature verified successfully")
        except Exception as e:
            raise KubeBenchError(f"Signature verification error: {str(e)}")

    def load_config(self, config_path: str) -> Dict:
        """Load and validate configuration from YAML file.

        Args:
            config_path (str): Path to YAML configuration file.

        Returns:
            Dict: Parsed configuration.

        Raises:
            KubeBenchError: If configuration is invalid or missing required fields.
        """
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            required_fields = ['endpoint_configs', 'reports_dir', 'deployment_type']
            for field in required_fields:
                if field not in config:
                    raise KubeBenchError(f"Missing required config field: {field}")

            if config['deployment_type'] not in ['docker', 'podman', 'kubernetes']:
                raise KubeBenchError("Invalid deployment_type. Must be 'docker', 'podman', or 'kubernetes'")

            valid_formats = ['txt', 'json', 'xml', 'html']
            for fmt in config.get('report_formats', ['txt']):
                if fmt not in valid_formats:
                    raise KubeBenchError(f"Invalid report format: {fmt}")

            for endpoint_config in config.get('endpoint_configs', []):
                self.validate_endpoint(endpoint_config['endpoint'])
                if 'timeout' in endpoint_config and not isinstance(endpoint_config['timeout'], int):
                    raise KubeBenchError(f"Invalid timeout for {endpoint_config['endpoint']}: must be an integer")

            logger.info("Configuration validated successfully")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {str(e)}")
            raise KubeBenchError(f"Configuration error: {str(e)}")

    def generate_report(self, output: str, endpoint: str, format: str) -> str:
        """Generate report in specified format.

        Args:
            output (str): Scan output to write to report.
            endpoint (str): Endpoint name for report filename.
            format (str): Report format (txt, json, xml, html).

        Returns:
            str: Path to generated report.

        Raises:
            KubeBenchError: If report generation fails.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = os.path.join(self.reports_dir, f"kube_bench_{endpoint}_{timestamp}.{format}")

        try:
            old_umask = os.umask(0o027)
            try:
                if format == 'json':
                    with open(report_path, 'w') as f:
                        json.dump(json.loads(output), f, indent=2)
                elif format == 'xml':
                    root = ET.Element("kube_bench_report")
                    root.text = output
                    tree = ET.ElementTree(root)
                    tree.write(report_path)
                elif format == 'html':
                    try:
                        data = json.loads(output)
                        checks = data.get('checks', [])
                        with open(report_path, 'w') as f:
                            template = Template(HTML_TEMPLATE)
                            f.write(template.render(endpoint=endpoint, checks=checks))
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON for HTML report, falling back to text")
                        with open(report_path, 'w') as f:
                            f.write(output)
                else:  # default to text
                    with open(report_path, 'w') as f:
                        f.write(output)
            finally:
                os.umask(old_umask)

            os.chmod(report_path, 0o640)
            logger.info(f"Generated {format} report for {endpoint} at {report_path}")
            return report_path
        except Exception as e:
            logger.error(f"Failed to generate {format} report for {endpoint}: {str(e)}")
            raise KubeBenchError(f"Report generation failed: {str(e)}")

    def generate_aggregate_report(self, results: List[Dict]) -> str:
        """Generate an aggregated report summarizing all endpoint scans.

        Args:
            results (List[Dict]): List of scan results.

        Returns:
            str: Path to aggregated report.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = os.path.join(self.reports_dir, f"kube_bench_aggregate_{timestamp}.json")

        try:
            old_umask = os.umask(0o027)
            try:
                summary = {
                    'total_endpoints': len(results),
                    'successful': len([r for r in results if r and r['returncode'] == 0]),
                    'failed': len([r for r in results if not r or r['returncode'] != 0]),
                    'endpoints': [
                        {
                            'endpoint': r['endpoint'],
                            'status': 'success' if r and r['returncode'] == 0 else 'failed',
                            'output': r['stdout'] if r else '',
                            'error': r['stderr'] if r else 'Timeout or error'
                        } for r in results
                    ]
                }
                with open(report_path, 'w') as f:
                    json.dump(summary, f, indent=2)
            finally:
                os.umask(old_umask)

            os.chmod(report_path, 0o640)
            logger.info(f"Generated aggregate report at {report_path}")
            return report_path
        except Exception as e:
            logger.error(f"Failed to generate aggregate report: {str(e)}")
            raise KubeBenchError(f"Aggregate report generation failed: {str(e)}")

    def run_scan(self, endpoint_config: Dict) -> Optional[Dict]:
        """Run kube-bench scan on a single endpoint.

        Args:
            endpoint_config (Dict): Configuration for the endpoint, including endpoint and timeout.

        Returns:
            Optional[Dict]: Scan results or None if scan fails.

        Raises:
            KubeBenchError: If scan execution fails critically.
        """
        endpoint = endpoint_config['endpoint']
        timeout = endpoint_config.get('timeout', self.config.get('timeout', 300))

        try:
            self.validate_endpoint(endpoint)
            cmd = self.build_command(endpoint)
            logger.info(f"Starting scan on {endpoint} with timeout {timeout}s")

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            result = {
                'endpoint': endpoint,
                'stdout': process.stdout,
                'stderr': process.stderr,
                'returncode': process.returncode
            }

            if process.returncode == 0:
                logger.info(f"Scan completed successfully for {endpoint}")
                for format in self.config.get('report_formats', ['txt']):
                    self.generate_report(process.stdout, endpoint, format)
            else:
                logger.error(f"Scan failed for {endpoint}: {process.stderr}")

            return result
        except subprocess.TimeoutExpired:
            logger.error(f"Scan timeout for {endpoint}")
            return None
        except Exception as e:
            logger.error(f"Scan failed for {endpoint}: {str(e)}")
            raise KubeBenchError(f"Scan execution failed: {str(e)}")

    def build_command(self, endpoint: str) -> List[str]:
        """Build command based on deployment type.

        Args:
            endpoint (str): Endpoint to scan.

        Returns:
            List[str]: Command to execute.
        """
        base_cmd = []
        kubeconfig_path = self.sanitize_path(self.config.get('kubeconfig_path', '~/.kube/config'))
        kubectl_path = self.sanitize_path(self.config.get('kubectl_path', '/usr/local/bin/kubectl'))

        if self.deployment_type == 'docker':
            base_cmd = [
                'docker', 'run', '--rm',
                '--pid=host',
                '--security-opt', 'apparmor=kube_bench_profile',
                '-v', '/etc:/etc:ro',
                '-v', '/var:/var:ro',
                '-v', f"{kubectl_path}:/usr/local/mount-from-host/bin/kubectl",
                '-v', f"{kubeconfig_path}:/.kube/config",
                '-e', 'KUBECONFIG=/.kube/config',
                'kube-bench:latest'
            ]
        elif self.deployment_type == 'podman':
            base_cmd = [
                'podman', 'run', '--rm',
                '--pid=host',
                '--selinux', 'label=type:kube_bench_t',
                '-v', '/etc:/etc:ro',
                '-v', '/var:/var:ro',
                '-v', f"{kubectl_path}:/usr/local/mount-from-host/bin/kubectl",
                '-v', f"{kubeconfig_path}:/.kube/config",
                '-e', 'KUBECONFIG=/.kube/config',
                'kube-bench:latest'
            ]
        elif self.deployment_type == 'kubernetes':
            job_path = self.sanitize_path(f"/tmp/kube-bench-job-{endpoint}.yaml")
            base_cmd = ['kubectl', 'apply', '-f', job_path]

        return base_cmd + self.config.get('extra_args', [])

    def orchestrate_scans(self) -> Dict:
        """Orchestrate scans across all endpoints.

        Returns:
            Dict: Summary of scan results.
        """
        endpoint_configs = self.config.get('endpoint_configs', [])
        logger.info(f"Starting scans on {len(endpoint_configs)} endpoints")

        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            results = list(executor.map(self.run_scan, endpoint_configs))

        aggregate_report = self.generate_aggregate_report(results)

        return {
            'total': len(endpoint_configs),
            'successful': len([r for r in results if r and r['returncode'] == 0]),
            'failed': len([r for r in results if not r or r['returncode'] != 0]),
            'results': results,
            'aggregate_report': aggregate_report
        }

def main():
    """Main entry point for the orchestrator."""
    try:
        config_path = os.getenv('KUBE_BENCH_CONFIG', 'config/config.yaml')
        # Example binary signature (replace with actual HMAC-SHA256 signature)
        binary_signature = os.getenv('KUBE_BENCH_SIGNATURE', None)
        orchestrator = KubeBenchOrchestrator(config_path, binary_signature)
        if binary_signature:
            orchestrator.verify_binary_signature('/usr/local/bin/kube-bench')
        results = orchestrator.orchestrate_scans()
        logger.info(f"Scan summary: {json.dumps(results, indent=2)}")
    except KubeBenchError as e:
        logger.error(f"Orchestration failed: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()