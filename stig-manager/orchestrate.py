#!/usr/bin/env python3
"""
Docstring for sql.stig-manager.orchestrate

Orchestration Script for STIG-Manager Setup (Python Version)
This script installs Docker or Podman based on configuration,
installs prerequisites, generates SSL certs, creates directories,
generates .env with random passwords, verifies syntax of files,
and spins up the stack with error handling.

@RW
"""

import os
import subprocess
import secrets
import string
import sys
import yaml
from pathlib import Path

# Configuration Variables (Set these as needed)
USE_DOCKER = True  # Set to False to use Podman instead
DOMAIN = "localhost"  # Your domain for certs and URLs
CERT_DAYS = 365  # Validity days for self-signed certs
COUNTRY = "US"
STATE = "TN"
LOCALITY = "SmokeyMnts"
ORG = "MyOrg"
OU = "IT"
EMAIL = "admin@example.com"

# MySQL and Keycloak config
MYSQL_ROOT_PASS_LENGTH = 32
MYSQL_PASS_LENGTH = 32
KEYCLOAK_DB_PASS_LENGTH = 32
KEYCLOAK_ADMIN_PASS_LENGTH = 32
SFTP_PASS_LENGTH = 32  # For SFTP

# Directories
CERT_DIR = "./certs"
NGINX_CONF = "./nginx.conf"
COMPOSE_FILE = "./docker-compose.yml"
ENV_FILE = "./.env"
WATCHED_DIR = "./watched"

def generate_password(length):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))

def command_exists(cmd):
    try:
        subprocess.check_output(["command", "-v", cmd])
        return True
    except subprocess.CalledProcessError:
        return False

def run_command(cmd, error_msg):
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

def install_prerequisites():
    if sys.platform.startswith('linux'):
        if command_exists('apt'):
            # Debian/Ubuntu
            run_command(['sudo', 'apt', 'update'], "Failed to update packages")
            run_command(['sudo', 'apt', 'install', '-y', 'openssl', 'curl', 'python3', 'python3-pip', 'yamllint', 'shellcheck', 'pylint'], "Failed to install prerequisites")
        elif command_exists('dnf'):
            # Fedora/RHEL 8+
            run_command(['sudo', 'dnf', 'install', '-y', '--enablerepo=epel', 'openssl', 'curl', 'python3', 'python3-pip', 'yamllint', 'shellcheck', 'pylint'], "Failed to install prerequisites")
        elif command_exists('yum'):
            # CentOS/RHEL 7
            run_command(['sudo', 'yum', 'install', '-y', 'epel-release'], "Failed to install EPEL")
            run_command(['sudo', 'yum', 'install', '-y', 'openssl', 'curl', 'python3', 'python3-pip', 'yamllint', 'shellcheck', 'pylint'], "Failed to install prerequisites")
        else:
            print("Error: Unsupported package manager. Please install openssl, curl, python3, pip, yamllint, shellcheck, and pylint manually.", file=sys.stderr)
            sys.exit(1)
    else:
        print("Error: Unsupported OS. This script is for Linux.", file=sys.stderr)
        sys.exit(1)

    # Install hadolint for Dockerfile lint
    if not command_exists('hadolint'):
        run_command(['sudo', 'curl', '-L', 'https://github.com/hadolint/hadolint/releases/latest/download/hadolint-Linux-x86_64', '-o', '/usr/local/bin/hadolint'], "Failed to download hadolint")
        run_command(['sudo', 'chmod', '+x', '/usr/local/bin/hadolint'], "Failed to make hadolint executable")

def install_container_engine():
    global COMPOSE_CMD, BUILD_CMD
    if USE_DOCKER:
        if not command_exists('docker'):
            run_command(['curl', '-fsSL', 'https://get.docker.com', '-o', 'get-docker.sh'], "Failed to download Docker install script")
            run_command(['sudo', 'sh', 'get-docker.sh'], "Failed to install Docker")
            os.remove('get-docker.sh')
            run_command(['sudo', 'usermod', '-aG', 'docker', os.environ['USER']], "Failed to add user to docker group")
            print("Docker installed. Log out and back in for group changes.")
        if not command_exists('docker-compose'):
            arch = os.uname().sysname.lower() + '-' + os.uname().machine
            run_command(['sudo', 'curl', '-L', f"https://github.com/docker/compose/releases/latest/download/docker-compose-{arch}", '-o', '/usr/local/bin/docker-compose'], "Failed to download Docker Compose")
            run_command(['sudo', 'chmod', '+x', '/usr/local/bin/docker-compose'], "Failed to make Docker Compose executable")
        COMPOSE_CMD = "docker-compose"
        BUILD_CMD = "docker"
    else:
        if not command_exists('podman'):
            if command_exists('apt'):
                run_command(['sudo', 'apt', 'install', '-y', 'podman'], "Failed to install Podman")
            elif command_exists('dnf'):
                run_command(['sudo', 'dnf', 'install', '-y', 'podman'], "Failed to install Podman")
            elif command_exists('yum'):
                run_command(['sudo', 'yum', 'install', '-y', 'podman'], "Failed to install Podman")
            else:
                print("Error: Unsupported package manager for Podman.", file=sys.stderr)
                sys.exit(1)
            run_command(['sudo', 'usermod', '-aG', 'podman', os.environ['USER']], "Failed to add user to podman group (if exists)")
        if not command_exists('podman-compose'):
            run_command(['pip', 'install', 'podman-compose'], "Failed to install podman-compose via pip")
        COMPOSE_CMD = "podman-compose"
        BUILD_CMD = "podman"

def create_directories():
    Path(CERT_DIR).mkdir(parents=True, exist_ok=True)
    Path(WATCHED_DIR).mkdir(parents=True, exist_ok=True)

def generate_ssl_certs():
    key_path = Path(f"{CERT_DIR}/server.key")
    cert_path = Path(f"{CERT_DIR}/server.crt")
    if not key_path.exists() or not cert_path.exists():
        subj = f"/C={COUNTRY}/ST={STATE}/L={LOCALITY}/O={ORG}/OU={OU}/CN={DOMAIN}/emailAddress={EMAIL}"
        run_command(['openssl', 'req', '-x509', '-nodes', '-days', str(CERT_DAYS), '-newkey', 'rsa:2048',
                     '-keyout', str(key_path), '-out', str(cert_path), '-subj', subj], "Failed to generate SSL certs")
        key_path.chmod(0o600)
    else:
        print("SSL certs already exist. Skipping generation.")

def generate_mysql_tls_certs():
    ca_path = Path(f"{CERT_DIR}/db-ca.pem")
    if not ca_path.exists():
        # CA
        run_command(['openssl', 'genrsa', '-out', f"{CERT_DIR}/db-ca.key", '2048'], "Failed to generate CA key")
        run_command(['openssl', 'req', '-x509', '-new', '-nodes', '-key', f"{CERT_DIR}/db-ca.key", '-sha256', '-days', str(CERT_DAYS),
                     '-out', f"{CERT_DIR}/db-ca.pem", '-subj', '/CN=DB-CA'], "Failed to generate CA cert")

        # Server
        run_command(['openssl', 'genrsa', '-out', f"{CERT_DIR}/db-server.key", '2048'], "Failed to generate server key")
        run_command(['openssl', 'req', '-new', '-key', f"{CERT_DIR}/db-server.key", '-out', f"{CERT_DIR}/db-server.csr", '-subj', '/CN=db'], "Failed to generate server CSR")
        run_command(['openssl', 'x509', '-req', '-in', f"{CERT_DIR}/db-server.csr", '-CA', f"{CERT_DIR}/db-ca.pem", '-CAkey', f"{CERT_DIR}/db-ca.key",
                     '-CAcreateserial', '-out', f"{CERT_DIR}/db-server.pem", '-days', str(CERT_DAYS), '-sha256'], "Failed to sign server cert")

        # Client
        run_command(['openssl', 'genrsa', '-out', f"{CERT_DIR}/db-client-key.pem", '2048'], "Failed to generate client key")
        run_command(['openssl', 'req', '-new', '-key', f"{CERT_DIR}/db-client-key.pem", '-out', f"{CERT_DIR}/db-client.csr", '-subj', '/CN=stigman'], "Failed to generate client CSR")
        run_command(['openssl', 'x509', '-req', '-in', f"{CERT_DIR}/db-client.csr", '-CA', f"{CERT_DIR}/db-ca.pem", '-CAkey', f"{CERT_DIR}/db-ca.key",
                     '-CAcreateserial', '-out', f"{CERT_DIR}/db-client-cert.pem", '-days', str(CERT_DAYS), '-sha256'], "Failed to sign client cert")

        try:
            os.remove(f"{CERT_DIR}/db-server.csr")
            os.remove(f"{CERT_DIR}/db-client.csr")
        except OSError:
            print("Cleanup failed, but continuing.")

        for key_file in Path(CERT_DIR).glob("*.key"):
            key_file.chmod(0o600)
    else:
        print("MySQL TLS certs already exist. Skipping generation.")

def generate_watcher_pem():
    pem_path = Path(f"{CERT_DIR}/watcher.pem")
    if not pem_path.exists():
        run_command(['openssl', 'genpkey', '-algorithm', 'RSA', '-out', f"{CERT_DIR}/watcher.key", '2048'], "Failed to generate watcher key")
        run_command(['openssl', 'req', '-new', '-x509', '-key', f"{CERT_DIR}/watcher.key", '-out', f"{CERT_DIR}/watcher.cert", '-days', str(CERT_DAYS), '-subj', '/CN=stigman-watcher'], "Failed to generate watcher cert")
        with open(pem_path, 'w') as f:
            with open(f"{CERT_DIR}/watcher.cert", 'r') as cert, open(f"{CERT_DIR}/watcher.key", 'r') as key:
                f.write(cert.read() + key.read())
        pem_path.chmod(0o600)
    else:
        print("Watcher PEM already exists. Skipping generation.")

def generate_env_file():
    env_path = Path(ENV_FILE)
    if not env_path.exists():
        mysql_root_password = generate_password(MYSQL_ROOT_PASS_LENGTH)
        mysql_password = generate_password(MYSQL_PASS_LENGTH)
        keycloak_db_password = generate_password(KEYCLOAK_DB_PASS_LENGTH)
        keycloak_admin_password = generate_password(KEYCLOAK_ADMIN_PASS_LENGTH)
        sftp_password = generate_password(SFTP_PASS_LENGTH)

        with open(ENV_FILE, 'w') as f:
            f.write(f"MYSQL_ROOT_PASSWORD={mysql_root_password}\n")
            f.write(f"MYSQL_PASSWORD={mysql_password}\n")
            f.write(f"KEYCLOAK_DB_PASSWORD={keycloak_db_password}\n")
            f.write(f"KEYCLOAK_ADMIN_PASSWORD={keycloak_admin_password}\n")
            f.write(f"SFTP_PASSWORD={sftp_password}\n")
            f.write(f"DOMAIN={DOMAIN}\n")
            f.write("WATCHER_CLIENT_ID=stigman-watcher\n")
            f.write("COLLECTION_ID=1\n")
            f.write("SFTP_USER=sftpuser\n")
        env_path.chmod(0o600)
    else:
        print(".env file already exists. Skipping generation.")

def build_sftp_image():
    run_command([BUILD_CMD, 'build', '-t', 'custom-sftp', '.'], "Failed to build custom SFTP image")

def verify_syntax():
    # Verify docker-compose.yml
    try:
        subprocess.run(['yamllint', COMPOSE_FILE], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(e.output.decode())
        print(f"Error: YAML lint failed for {COMPOSE_FILE}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(COMPOSE_FILE, 'r') as f:
            yaml.safe_load(f)
    except Exception:
        print(f"Error: YAML parsing failed for {COMPOSE_FILE}", file=sys.stderr)
        sys.exit(1)

    # Lint Dockerfile
    run_command(['hadolint', 'Dockerfile'], "Dockerfile lint failed")

    # Lint entrypoint.sh
    run_command(['shellcheck', 'entrypoint.sh'], "Shellcheck failed for entrypoint.sh")

    # Basic check for nginx.conf (install nginx temporarily if needed)
    if not command_exists('nginx'):
        if command_exists('apt'):
            run_command(['sudo', 'apt', 'install', '-y', 'nginx'], "Failed to install nginx for verification")
        elif command_exists('dnf'):
            run_command(['sudo', 'dnf', 'install', '-y', 'nginx'], "Failed to install nginx for verification")
        elif command_exists('yum'):
            run_command(['sudo', 'yum', 'install', '-y', 'nginx'], "Failed to install nginx for verification")
    run_command(['nginx', '-t', '-c', NGINX_CONF], "Nginx config test failed")

    # Lint this script (optional, requires pylint)
    try:
        subprocess.run(['pylint', __file__], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(e.output.decode())
        print("Pylint warnings on this script, but continuing.")

    print("Syntax verification passed.")

def spin_up_stack():
    run_command([COMPOSE_CMD, '-f', COMPOSE_FILE, 'up', '-d'], "Failed to start the stack")
    print(f"Stack started successfully. Access Keycloak at https://{DOMAIN}:8443 for initial setup (or via nginx proxy).")

# Main execution
install_prerequisites()
install_container_engine()
create_directories()
generate_ssl_certs()
generate_mysql_tls_certs()
generate_watcher_pem()
generate_env_file()
build_sftp_image()
verify_syntax()
spin_up_stack()