import subprocess
import sys
import shutil
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(filename='logs/deployment.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def run_command(command):
    """Execute a shell command and handle errors."""
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logging.info(f"Cleanup command executed: {' '.join(command)}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"Cleanup command failed: {e.stderr}")
        return None

def cleanup_aws():
    """Clean up AWS resources."""
    print("Cleaning up AWS resources...")
    run_command(['terraform', 'destroy', '-auto-approve'])
    logging.info("AWS resources cleaned up")

def cleanup_bare_metal():
    """Clean up bare metal resources."""
    print("Cleaning up bare metal resources...")
    for path in ['/opt/splunk', '/opt/splunkforwarder', '/tmp/splunk-*.tgz', '/tmp/splunkforwarder-*.tgz']:
        if Path(path).exists():
            shutil.rmtree(path, ignore_errors=True)
            logging.info(f"Removed {path}")
    run_command(['systemctl', 'disable', 'splunk', '--now'])
    run_command(['systemctl', 'disable', 'splunkforwarder', '--now'])
    logging.info("Bare metal resources cleaned up")

def main():
    deployment_type = sys.argv[1] if len(sys.argv) > 1 else 'bare_metal'
    logging.info(f"Starting cleanup for deployment type: {deployment_type}")

    try:
        if deployment_type == 'aws':
            cleanup_aws()
        else:
            cleanup_bare_metal()
        print("Cleanup completed successfully!")
        logging.info("Cleanup completed successfully")
    except Exception as e:
        logging.error(f"Cleanup failed: {str(e)}")
        print(f"Cleanup failed: {str(e)}. Check logs/deployment.log.")
        sys.exit(1)

if __name__ == '__main__':
    main()