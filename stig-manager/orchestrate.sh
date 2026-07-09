#!/bin/bash
###################################################################
# Orchestration Script for STIG-Manager Setup
# This script installs Docker or Podman based on configuration,
# installs prerequisites, generates SSL certs, creates directories,
# generates .env with random passwords, verifies syntax of files,
# and spins up the stack with error handling.
# @RW
###################################################################

# Configuration Variables (Set these as needed)
USE_DOCKER=true  # Set to false to use Podman instead
DOMAIN="localhost"  # Your domain for certs and URLs
CERT_DAYS=365  # Validity days for self-signed certs
COUNTRY="US"
STATE="TN"
LOCALITY="SmokeyMnts"
ORG="MyOrg"
OU="IT"
EMAIL="admin@example.com"

# MySQL and Keycloak config
MYSQL_ROOT_PASS_LENGTH=32
MYSQL_PASS_LENGTH=32
KEYCLOAK_DB_PASS_LENGTH=32
KEYCLOAK_ADMIN_PASS_LENGTH=32
SFTP_PASS_LENGTH=32  # For SFTP

# Directories
CERT_DIR="./certs"
NGINX_CONF="./nginx.conf"
COMPOSE_FILE="./docker-compose.yml"
ENV_FILE="./.env"
WATCHED_DIR="./watched"

# Function to generate random password
generate_password() {
    local length=$1
    tr -dc A-Za-z0-9 </dev/urandom | head -c ${length} ; echo ''
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Error handling function
handle_error() {
    echo "Error: $1" >&2
    exit 1
}

# Detect OS and install prerequisites
install_prerequisites() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command_exists apt; then
            # Debian/Ubuntu
            sudo apt update || handle_error "Failed to update packages"
            sudo apt install -y openssl curl python3 python3-pip yamllint shellcheck pylint || handle_error "Failed to install prerequisites"
        elif command_exists dnf; then
            # Fedora/RHEL 8+
            sudo dnf install -y --enablerepo=epel openssl curl python3 python3-pip yamllint shellcheck pylint || handle_error "Failed to install prerequisites"
        elif command_exists yum; then
            # CentOS/RHEL 7
            sudo yum install -y epel-release || handle_error "Failed to install EPEL"
            sudo yum install -y openssl curl python3 python3-pip yamllint shellcheck pylint || handle_error "Failed to install prerequisites"
        else
            handle_error "Unsupported package manager. Please install openssl, curl, python3, pip, yamllint, shellcheck, and pylint manually."
        fi
    else
        handle_error "Unsupported OS. This script is for Linux."
    fi

    # Install hadolint for Dockerfile lint
    if ! command_exists hadolint; then
        sudo curl -L https://github.com/hadolint/hadolint/releases/latest/download/hadolint-Linux-x86_64 -o /usr/local/bin/hadolint || handle_error "Failed to download hadolint"
        sudo chmod +x /usr/local/bin/hadolint || handle_error "Failed to make hadolint executable"
    fi
}

# Install Docker or Podman
install_container_engine() {
    if $USE_DOCKER; then
        if ! command_exists docker; then
            curl -fsSL https://get.docker.com -o get-docker.sh || handle_error "Failed to download Docker install script"
            sudo sh get-docker.sh || handle_error "Failed to install Docker"
            rm get-docker.sh
            sudo usermod -aG docker $USER || handle_error "Failed to add user to docker group"
            echo "Docker installed. Log out and back in for group changes."
        fi
        if ! command_exists docker-compose; then
            sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose || handle_error "Failed to download Docker Compose"
            sudo chmod +x /usr/local/bin/docker-compose || handle_error "Failed to make Docker Compose executable"
        fi
        COMPOSE_CMD="docker-compose"
        BUILD_CMD="docker"
    else
        if ! command_exists podman; then
            if command_exists apt; then
                sudo apt install -y podman || handle_error "Failed to install Podman"
            elif command_exists dnf; then
                sudo dnf install -y podman || handle_error "Failed to install Podman"
            elif command_exists yum; then
                sudo yum install -y podman || handle_error "Failed to install Podman"
            else
                handle_error "Unsupported package manager for Podman."
            fi
            sudo usermod -aG podman $USER || handle_error "Failed to add user to podman group (if exists)"
        fi
        if ! command_exists podman-compose; then
            pip install podman-compose || handle_error "Failed to install podman-compose via pip"
        fi
        COMPOSE_CMD="podman-compose"
        BUILD_CMD="podman"
    fi
}

# Create directories
create_directories() {
    mkdir -p "$CERT_DIR" "$WATCHED_DIR" || handle_error "Failed to create directories"
}

# Generate self-signed SSL certs for Nginx
generate_ssl_certs() {
    if [ ! -f "$CERT_DIR/server.key" ] || [ ! -f "$CERT_DIR/server.crt" ]; then
        openssl req -x509 -nodes -days $CERT_DAYS -newkey rsa:2048 \
            -keyout "$CERT_DIR/server.key" -out "$CERT_DIR/server.crt" \
            -subj "/C=$COUNTRY/ST=$STATE/L=$LOCALITY/O=$ORG/OU=$OU/CN=$DOMAIN/emailAddress=$EMAIL" \
            || handle_error "Failed to generate SSL certs"
        chmod 600 "$CERT_DIR/server.key" || handle_error "Failed to set permissions on key"
    else
        echo "SSL certs already exist. Skipping generation."
    fi
}

# Generate optional MySQL TLS certs (CA, server, client)
generate_mysql_tls_certs() {
    if [ ! -f "$CERT_DIR/db-ca.pem" ]; then
        # CA
        openssl genrsa -out "$CERT_DIR/db-ca.key" 2048 || handle_error "Failed to generate CA key"
        openssl req -x509 -new -nodes -key "$CERT_DIR/db-ca.key" -sha256 -days $CERT_DAYS \
            -out "$CERT_DIR/db-ca.pem" -subj "/CN=DB-CA" || handle_error "Failed to generate CA cert"

        # Server
        openssl genrsa -out "$CERT_DIR/db-server.key" 2048 || handle_error "Failed to generate server key"
        openssl req -new -key "$CERT_DIR/db-server.key" -out "$CERT_DIR/db-server.csr" -subj "/CN=db" || handle_error "Failed to generate server CSR"
        openssl x509 -req -in "$CERT_DIR/db-server.csr" -CA "$CERT_DIR/db-ca.pem" -CAkey "$CERT_DIR/db-ca.key" \
            -CAcreateserial -out "$CERT_DIR/db-server.pem" -days $CERT_DAYS -sha256 || handle_error "Failed to sign server cert"

        # Client
        openssl genrsa -out "$CERT_DIR/db-client-key.pem" 2048 || handle_error "Failed to generate client key"
        openssl req -new -key "$CERT_DIR/db-client-key.pem" -out "$CERT_DIR/db-client.csr" -subj "/CN=stigman" || handle_error "Failed to generate client CSR"
        openssl x509 -req -in "$CERT_DIR/db-client.csr" -CA "$CERT_DIR/db-ca.pem" -CAkey "$CERT_DIR/db-ca.key" \
            -CAcreateserial -out "$CERT_DIR/db-client-cert.pem" -days $CERT_DAYS -sha256 || handle_error "Failed to sign client cert"

        rm "$CERT_DIR/db-server.csr" "$CERT_DIR/db-client.csr" || echo "Cleanup failed, but continuing."
        chmod 600 "$CERT_DIR"/*.key || handle_error "Failed to set permissions on keys"
    else
        echo "MySQL TLS certs already exist. Skipping generation."
    fi
}

# Generate watcher PEM (unencrypted for Signed JWT)
generate_watcher_pem() {
    if [ ! -f "$CERT_DIR/watcher.pem" ]; then
        openssl genpkey -algorithm RSA -out "$CERT_DIR/watcher.key" 2048 || handle_error "Failed to generate watcher key"
        openssl req -new -x509 -key "$CERT_DIR/watcher.key" -out "$CERT_DIR/watcher.cert" -days $CERT_DAYS -subj "/CN=stigman-watcher" || handle_error "Failed to generate watcher cert"
        cat "$CERT_DIR/watcher.cert" "$CERT_DIR/watcher.key" > "$CERT_DIR/watcher.pem" || handle_error "Failed to combine watcher PEM"
        chmod 600 "$CERT_DIR/watcher.pem" || handle_error "Failed to set permissions on watcher PEM"
    else
        echo "Watcher PEM already exists. Skipping generation."
    fi
}

# Generate .env file with random passwords if not exists
generate_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        MYSQL_ROOT_PASSWORD=$(generate_password $MYSQL_ROOT_PASS_LENGTH)
        MYSQL_PASSWORD=$(generate_password $MYSQL_PASS_LENGTH)
        KEYCLOAK_DB_PASSWORD=$(generate_password $KEYCLOAK_DB_PASS_LENGTH)
        KEYCLOAK_ADMIN_PASSWORD=$(generate_password $KEYCLOAK_ADMIN_PASS_LENGTH)
        SFTP_PASSWORD=$(generate_password $SFTP_PASS_LENGTH)

        cat > "$ENV_FILE" << EOF
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD
MYSQL_PASSWORD=$MYSQL_PASSWORD
KEYCLOAK_DB_PASSWORD=$KEYCLOAK_DB_PASSWORD
KEYCLOAK_ADMIN_PASSWORD=$KEYCLOAK_ADMIN_PASSWORD
SFTP_PASSWORD=$SFTP_PASSWORD
DOMAIN=$DOMAIN
WATCHER_CLIENT_ID=stigman-watcher
COLLECTION_ID=1
SFTP_USER=sftpuser
EOF
        chmod 600 "$ENV_FILE" || handle_error "Failed to set permissions on .env"
    else
        echo ".env file already exists. Skipping generation."
    fi
}

# Build custom SFTP image
build_sftp_image() {
    $BUILD_CMD build -t custom-sftp . || handle_error "Failed to build custom SFTP image"
}

# Verify syntax of support files
verify_syntax() {
    # Verify docker-compose.yml
    if ! yamllint "$COMPOSE_FILE" >/dev/null 2>&1; then
        yamllint "$COMPOSE_FILE" || handle_error "YAML lint failed for $COMPOSE_FILE"
    fi
    python3 -c "import yaml; yaml.safe_load(open('$COMPOSE_FILE'))" || handle_error "YAML parsing failed for $COMPOSE_FILE"

    # Lint Dockerfile
    hadolint Dockerfile || handle_error "Dockerfile lint failed"

    # Lint entrypoint.sh
    shellcheck entrypoint.sh || handle_error "Shellcheck failed for entrypoint.sh"

    # Basic check for nginx.conf (install nginx temporarily if needed)
    if ! command_exists nginx; then
        if command_exists apt; then
            sudo apt install -y nginx || handle_error "Failed to install nginx for verification"
        elif command_exists dnf; then
            sudo dnf install -y nginx || handle_error "Failed to install nginx for verification"
        elif command_exists yum; then
            sudo yum install -y nginx || handle_error "Failed to install nginx for verification"
        fi
    fi
    nginx -t -c "$NGINX_CONF" || handle_error "Nginx config test failed"

    # Lint this script itself (optional)
    shellcheck "$0" || echo "Shellcheck warnings on this script, but continuing."

    echo "Syntax verification passed."
}

# Spin up the stack
spin_up_stack() {
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d || handle_error "Failed to start the stack"
    echo "Stack started successfully. Access Keycloak at https://$DOMAIN:8443 for initial setup (or via nginx proxy)."
}

# Main execution
install_prerequisites
install_container_engine
create_directories
generate_ssl_certs
generate_mysql_tls_certs
generate_watcher_pem
generate_env_file
build_sftp_image
verify_syntax
spin_up_stack