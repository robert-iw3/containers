#!/bin/bash

# Ensure the script is run with bash
if [ -z "$BASH_VERSION" ]; then
    echo "This script must be run with bash"
    exit 1
fi

# Check for required tools
command -v python3 >/dev/null 2>&1 || { echo "Python3 is required"; exit 1; }
command -v docker >/dev/null 2>&1 || command -v podman >/dev/null 2>&1 || command -v kubectl >/dev/null 2>&1 || { echo "At least one of Docker, Podman, or kubectl is required"; exit 1; }

# Create secrets directory and files
mkdir -p secrets
if [ ! -f secrets/postgres_db.txt ]; then
    echo "artifactory" > secrets/postgres_db.txt
fi
if [ ! -f secrets/postgres_user.txt ]; then
    echo "artifactory" > secrets/postgres_user.txt
fi
if [ ! -f secrets/postgres_password.txt ]; then
    python3 -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16)))" > secrets/postgres_password.txt
fi

# Create .setup-env if it doesn't exist
if [ ! -f .setup-env ]; then
    cp .setup-env.example .setup-env
fi

echo "Setup complete. Run 'python3 deploy.py --platform <docker|podman|kubernetes>' to deploy Artifactory."