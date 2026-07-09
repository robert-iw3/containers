import argparse
import subprocess
import os
import dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_env():
    """Validate required environment variables."""
    dotenv.load_dotenv()
    required_vars = [
        'ANTHROPIC_API_KEY', 'GOOGLE_CREDENTIAL_PATH', 'GOOGLE_VERTEX_PROJECT',
        'GOOGLE_VERTEX_LOCATION', 'GROQ_API_KEY', 'OPENAI_API_KEY',
        'POSTGRES_DB_URL', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'FQDN'
    ]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        raise ValueError("Environment validation failed")

def main():
    parser = argparse.ArgumentParser(description="Automation script for deploying LiteLLM setup")
    parser.add_argument('--platform', choices=['docker', 'podman', 'kubernetes'], required=True, help="Deployment platform")
    args = parser.parse_args()

    try:
        validate_env()
        if args.platform == 'docker':
            logger.info("Deploying with Docker Compose...")
            subprocess.run(['docker', 'compose', 'up', '-d'], check=True)
        elif args.platform == 'podman':
            logger.info("Deploying with Podman Compose...")
            subprocess.run(['podman-compose', 'up', '-d'], check=True)
        elif args.platform == 'kubernetes':
            logger.info("Deploying to Kubernetes...")
            subprocess.run(['kubectl', 'apply', '-f', 'k8s/'], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Deployment failed: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        exit(1)

if __name__ == "__main__":
    main()