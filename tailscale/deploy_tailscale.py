import os
import subprocess
import sys
import argparse
from pathlib import Path
import logging
import yaml

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_prerequisites(orchestrator):
    """Check if required tools are installed based on the orchestrator."""
    required = ['ip', 'sysctl']
    if orchestrator in ['docker', 'podman']:
        if orchestrator == 'docker':
            required.extend(['docker'])
        else:
            required.extend(['podman'])
        # Assuming compose is available via 'docker compose' or 'podman-compose'
    elif orchestrator == 'kubernetes':
        required.append('kubectl')
    elif orchestrator == 'ansible':
        required.append('ansible-playbook')

    for cmd in required:
        try:
            subprocess.run([cmd, '--version'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"{cmd} is installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error(f"{cmd} is not installed. Please install it and try again.")
            sys.exit(1)

def validate_subnet(subnet):
    """Validate the subnet CIDR."""
    try:
        import ipaddress
        ipaddress.ip_network(subnet, strict=False)
        logger.info(f"Subnet {subnet} is valid")
        return True
    except ValueError as e:
        logger.error(f"Invalid subnet {subnet}: {e}")
        return False

def generate_env_file(subnet="192.168.1.0/24"):
    """Generate .env file with secure defaults."""
    env_file = Path('.env')
    if env_file.exists():
        logger.info(".env file already exists, skipping generation")
        return

    env_content = {
        'TS_AUTHKEY': os.getenv('TS_AUTHKEY'),
        'SUBNET_CIDR': subnet,
    }

    with env_file.open('w') as f:
        for key, value in env_content.items():
            f.write(f"{key}={value}\n")
    logger.info(".env file generated")

def configure_system():
    """Configure system settings for Tailscale routing."""
    sysctl_settings = [
        ('net.ipv4.ip_forward', '1'),
        ('net.ipv6.conf.all.forwarding', '1')
    ]
    sysctl_file = Path('/etc/sysctl.d/99-tailscale.conf')
    existing_settings = set()
    if sysctl_file.exists():
        with sysctl_file.open('r') as f:
            for line in f:
                if '=' in line:
                    key = line.split('=')[0].strip()
                    existing_settings.add(key)

    for key, value in sysctl_settings:
        if key not in existing_settings:
            try:
                subprocess.run(['sysctl', f'{key}={value}'], check=True, stdout=subprocess.DEVNULL)
                with sysctl_file.open('a') as f:
                    f.write(f"{key} = {value}\n")
                logger.info(f"Set {key}={value}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to set {key}: {e}")
                sys.exit(1)
        else:
            logger.info(f"{key} already set in {sysctl_file}")

    # Load TUN module
    try:
        subprocess.run(['modprobe', 'tun'], check=True, stdout=subprocess.DEVNULL)
        logger.info("TUN module loaded")
    except subprocess.CalledProcessError:
        logger.warning("Failed to load TUN module; it may already be loaded or not required")

def configure_dns():
    """Configure DNS with public resolvers as a fallback."""
    try:
        resolv_conf = Path('/etc/resolv.conf')
        resolv_conf_bak = Path('/etc/resolv.conf.bak')
        if resolv_conf.exists() and not resolv_conf_bak.exists():
            resolv_conf.rename(resolv_conf_bak)
            logger.info("Backed up original resolv.conf")
        with resolv_conf.open('w') as f:
            f.write("nameserver 9.9.9.9\nnameserver 149.112.112.112\n")
        logger.info("DNS configured with Quad9 servers")
    except Exception as e:
        logger.error(f"Failed to configure DNS: {e}")
        sys.exit(1)

def configure_firewall():
    """Configure firewall rules for Tailscale using firewalld if available."""
    try:
        # Check if firewalld is installed and running
        subprocess.run(['firewall-cmd', '--version'], check=True, stdout=subprocess.DEVNULL)
        logger.info("firewalld detected; configuring...")

        commands = [
            ['firewall-cmd', '--permanent', '--new-zone=tailscale'],
            ['firewall-cmd', '--reload'],
            ['firewall-cmd', '--zone=tailscale', '--permanent', '--add-masquerade'],
            ['firewall-cmd', '--zone=tailscale', '--permanent', '--set-target=ACCEPT'],  # Changed to ACCEPT for better compatibility
            ['firewall-cmd', '--zone=tailscale', '--permanent', '--add-interface=tailscale0'],
            ['firewall-cmd', '--zone=tailscale', '--permanent', '--add-port=443/tcp'],
            ['firewall-cmd', '--zone=tailscale', '--permanent', '--add-port=41641/udp'],
            ['firewall-cmd', '--zone=tailscale', '--permanent', '--add-port=3478/udp'],
            ['firewall-cmd', '--reload']
        ]
        for cmd in commands:
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
                logger.info(f"Executed: {' '.join(cmd)}")
            except subprocess.CalledProcessError as e:
                if "ALREADY_EXISTS" in str(e.stderr):  # Ignore if zone already exists
                    logger.info(f"Skipped existing configuration: {' '.join(cmd)}")
                else:
                    raise
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("firewalld not detected or configuration failed. Skipping firewall setup. Ensure your firewall allows Tailscale traffic manually.")
    except Exception as e:
        logger.error(f"Firewall configuration failed: {e}")
        sys.exit(1)

def generate_compose_file(orchestrator, subnet, file_path=Path("docker-compose.yml")):
    """Generate docker-compose.yml or podman-compose.yml if it doesn't exist."""
    if file_path.exists():
        logger.info(f"{file_path} already exists, skipping generation")
        return

    volumes = [
        './tailscale-state:/var/lib/tailscale',
        '/dev/net/tun:/dev/net/tun'
    ]
    if orchestrator == 'podman':
        volumes = [v + ':Z' for v in volumes]

    compose = {
        'version': '3.8',
        'services': {
            'tailscale': {
                'image': 'tailscale/tailscale:latest',
                'container_name': 'tailscale',
                'network_mode': 'host',
                'cap_add': ['NET_ADMIN', 'NET_RAW'],
                'security_opt': ['no-new-privileges:true'],
                'devices': ['/dev/net/tun:/dev/net/tun'],
                'volumes': volumes,
                'environment': {
                    'TS_AUTHKEY': '${TS_AUTHKEY}',
                    'TS_STATE_DIR': '/var/lib/tailscale',
                    'TS_USERSPACE': 'false',
                    'TS_SOCKET': '/var/run/tailscale/tailscaled.sock',
                    'TS_ROUTES': '${SUBNET_CIDR}',
                    'TS_EXTRA_ARGS': '--advertise-exit-node --accept-routes',
                    'TS_LOCAL_ADDR_PORT': '127.0.0.1:41234',
                    'TS_ENABLE_HEALTH_CHECK': 'true',
                    'TS_ENABLE_METRICS': 'true'
                },
                'restart': 'unless-stopped',
                'healthcheck': {
                    'test': ['CMD', 'wget', '--spider', '-q', 'http://127.0.0.1:41234/healthz'],
                    'interval': '30s',
                    'timeout': '10s',
                    'retries': 3,
                    'start_period': '10s'
                }
            }
        }
    }

    with file_path.open('w') as f:
        yaml.safe_dump(compose, f, default_flow_style=False)
    logger.info(f"Compose file generated at {file_path}")

def deploy_docker_podman(orchestrator, compose_file="docker-compose.yml"):
    """Deploy Tailscale using Docker or Podman."""
    try:
        if orchestrator == 'docker':
            compose_cmd = ['docker', 'compose']
        else:
            compose_cmd = ['podman-compose']
        subprocess.run(compose_cmd + ['-f', compose_file, 'up', '-d'], check=True)
        logger.info(f"Tailscale container deployed using {orchestrator}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"Failed to deploy Tailscale with {orchestrator}: {e}")
        sys.exit(1)

def generate_kubernetes_manifest(subnet, namespace="default"):
    """Generate Kubernetes manifest for Tailscale deployment."""
    manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "tailscale-exit-node",
            "namespace": namespace,
            "labels": {
                "app": "tailscale"
            }
        },
        "spec": {
            "hostNetwork": True,
            "containers": [
                {
                    "name": "tailscale",
                    "image": "docker.io/tailscale/tailscale:latest",
                    "env": [
                        {"name": "TS_AUTHKEY", "valueFrom": {"secretKeyRef": {"name": "tailscale-secret", "key": "authkey"}}},
                        {"name": "TS_STATE_DIR", "value": "/var/lib/tailscale"},
                        {"name": "TS_USERSPACE", "value": "false"},
                        {"name": "TS_SOCKET", "value": "/var/run/tailscale/tailscaled.sock"},
                        {"name": "TS_ROUTES", "value": subnet},
                        {"name": "TS_EXTRA_ARGS", "value": "--advertise-exit-node --accept-routes"},
                        {"name": "TS_LOCAL_ADDR_PORT", "value": "127.0.0.1:41234"},
                        {"name": "TS_ENABLE_HEALTH_CHECK", "value": "true"},
                        {"name": "TS_ENABLE_METRICS", "value": "true"}
                    ],
                    "volumeMounts": [
                        {"name": "tailscale-state", "mountPath": "/var/lib/tailscale"},
                        {"name": "tun-device", "mountPath": "/dev/net/tun"}
                    ],
                    "securityContext": {
                        "capabilities": {
                            "add": ["NET_ADMIN", "NET_RAW"]
                        },
                        "privileged": False
                    },
                    "resources": {
                        "limits": {"cpu": "500m", "memory": "512Mi"},
                        "requests": {"cpu": "100m", "memory": "128Mi"}
                    }
                }
            ],
            "volumes": [
                {"name": "tailscale-state", "emptyDir": {}},
                {"name": "tun-device", "hostPath": {"path": "/dev/net/tun", "type": "CharDevice"}}
            ]
        }
    }

    manifest_file = Path("tailscale-k8s.yaml")
    with manifest_file.open('w') as f:
        yaml.safe_dump(manifest, f, default_flow_style=False)
    logger.info(f"Kubernetes manifest generated at {manifest_file}")

    # Generate secret manifest
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": "tailscale-secret",
            "namespace": namespace
        },
        "stringData": {
            "authkey": os.getenv('TS_AUTHKEY')
        }
    }

    secret_file = Path("tailscale-secret.yaml")
    with secret_file.open('w') as f:
        yaml.safe_dump(secret, f, default_flow_style=False)
    logger.info(f"Kubernetes secret manifest generated at {secret_file}")

    return manifest_file, secret_file

def deploy_kubernetes(manifest_file, secret_file, namespace="default"):
    """Deploy Tailscale using Kubernetes."""
    try:
        subprocess.run(['kubectl', 'apply', '-f', str(secret_file), '-n', namespace], check=True)
        subprocess.run(['kubectl', 'apply', '-f', str(manifest_file), '-n', namespace], check=True)
        logger.info("Tailscale deployed to Kubernetes")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to deploy Tailscale to Kubernetes: {e}")
        sys.exit(1)

def generate_ansible_playbook(subnet):
    """Generate Ansible playbook for Tailscale deployment."""
    playbook = [
        {
            "name": "Deploy Tailscale container",
            "hosts": "tailscale_hosts",
            "become": True,
            "tasks": [
                {
                    "name": "Ensure TUN module is loaded",
                    "modprobe": {"name": "tun"}
                },
                {
                    "name": "Enable IP forwarding",
                    "sysctl": {
                        "name": "{{ item.name }}",
                        "value": "{{ item.value }}",
                        "state": "present",
                        "sysctl_file": "/etc/sysctl.d/99-tailscale.conf"
                    },
                    "loop": [
                        {"name": "net.ipv4.ip_forward", "value": "1"},
                        {"name": "net.ipv6.conf.all.forwarding", "value": "1"}
                    ]
                },
                {
                    "name": "Configure DNS",
                    "copy": {
                        "content": "nameserver 9.9.9.9\nnameserver 149.112.112.112\n",
                        "dest": "/etc/resolv.conf",
                        "backup": True
                    }
                },
                {
                    "name": "Ensure firewalld is installed",
                    "package": {"name": "firewalld", "state": "present"}
                },
                {
                    "name": "Configure firewalld for Tailscale",
                    "command": "{{ item }}",
                    "loop": [
                        "firewall-cmd --permanent --new-zone=tailscale",
                        "firewall-cmd --reload",
                        "firewall-cmd --zone=tailscale --permanent --add-masquerade",
                        "firewall-cmd --zone=tailscale --permanent --set-target=ACCEPT",
                        "firewall-cmd --zone=tailscale --permanent --add-interface=tailscale0",
                        "firewall-cmd --zone=tailscale --permanent --add-port=443/tcp",
                        "firewall-cmd --zone=tailscale --permanent --add-port=41641/udp",
                        "firewall-cmd --zone=tailscale --permanent --add-port=3478/udp",
                        "firewall-cmd --reload"
                    ],
                    "ignore_errors": True  # To handle already exists
                },
                {
                    "name": "Run Tailscale container",
                    "docker_container": {
                        "name": "tailscale",
                        "image": "docker.io/tailscale/tailscale:latest",
                        "state": "started",
                        "restart_policy": "unless-stopped",
                        "network_mode": "host",
                        "capabilities": ["NET_ADMIN", "NET_RAW"],
                        "security_opts": ["no-new-privileges=true"],
                        "devices": ["/dev/net/tun:/dev/net/tun"],
                        "volumes": [
                            "tailscale-state:/var/lib/tailscale:Z",
                            "/dev/net/tun:/dev/net/tun:Z"
                        ],
                        "env": {
                            "TS_AUTHKEY": "{{ lookup('env', 'TS_AUTHKEY') }}",
                            "TS_STATE_DIR": "/var/lib/tailscale",
                            "TS_USERSPACE": "false",
                            "TS_SOCKET": "/var/run/tailscale/tailscaled.sock",
                            "TS_ROUTES": subnet,
                            "TS_EXTRA_ARGS": "--advertise-exit-node --accept-routes",
                            "TS_LOCAL_ADDR_PORT": "127.0.0.1:41234",
                            "TS_ENABLE_HEALTH_CHECK": "true",
                            "TS_ENABLE_METRICS": "true"
                        },
                        "healthcheck": {
                            "test": ["CMD", "wget", "--spider", "-q", "http://127.0.0.1:41234/healthz"],
                            "interval": "30s",
                            "timeout": "10s",
                            "retries": 3,
                            "start_period": "10s"
                        }
                    }
                }
            ]
        }
    ]

    playbook_file = Path("tailscale-playbook.yml")
    with playbook_file.open('w') as f:
        yaml.safe_dump(playbook, f, default_flow_style=False)
    logger.info(f"Ansible playbook generated at {playbook_file}")

    return playbook_file

def deploy_ansible(playbook_file):
    """Deploy Tailscale using Ansible."""
    try:
        inventory = Path("inventory.yml")
        if not inventory.exists():
            with inventory.open('w') as f:
                f.write("tailscale_hosts:\n  hosts:\n    localhost:\n      ansible_connection: local\n")
            logger.info(f"Ansible inventory generated at {inventory}")

        subprocess.run(['ansible-playbook', '-i', str(inventory), str(playbook_file)], check=True)
        logger.info("Tailscale deployed using Ansible")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to deploy Tailscale with Ansible: {e}")
        sys.exit(1)

def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(description="Deploy Tailscale container with various orchestrators")
    parser.add_argument('--orchestrator', choices=['docker', 'podman', 'kubernetes', 'ansible'],
                        default='docker', help="Orchestrator to use for deployment")
    parser.add_argument('--subnet', default='192.168.1.0/24', help="Subnet CIDR for Tailscale routes")
    parser.add_argument('--namespace', default='default', help="Kubernetes namespace (for Kubernetes only)")
    parser.add_argument('--compose-file', default='docker-compose.yml',
                        help="Docker/Podman compose file path (for Docker/Podman)")
    args = parser.parse_args()

    logger.info(f"Starting Tailscale deployment with {args.orchestrator}")

    # Check if TS_AUTHKEY is set
    if not os.getenv('TS_AUTHKEY'):
        logger.error("TS_AUTHKEY environment variable is required. Please set it and try again.")
        sys.exit(1)

    # Check prerequisites
    check_prerequisites(args.orchestrator)

    # Validate subnet
    if not validate_subnet(args.subnet):
        sys.exit(1)

    # Generate environment file
    generate_env_file(args.subnet)

    # Configure system settings
    configure_system()

    # Configure DNS
    configure_dns()

    # Configure firewall
    configure_firewall()

    # Deploy based on orchestrator
    if args.orchestrator in ['docker', 'podman']:
        compose_path = Path(args.compose_file)
        generate_compose_file(args.orchestrator, args.subnet, compose_path)
        deploy_docker_podman(args.orchestrator, str(compose_path))
    elif args.orchestrator == 'kubernetes':
        manifest_file, secret_file = generate_kubernetes_manifest(args.subnet, args.namespace)
        deploy_kubernetes(manifest_file, secret_file, args.namespace)
    elif args.orchestrator == 'ansible':
        playbook_file = generate_ansible_playbook(args.subnet)
        deploy_ansible(playbook_file)

    logger.info("Deployment completed successfully")
    logger.info("Verify the setup in the Tailscale admin console and enable exit node routes.")

if __name__ == "__main__":
    main()