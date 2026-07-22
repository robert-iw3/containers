import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Optional

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False
    print("Warning: Kubernetes client not installed. Install with 'pip install kubernetes' for K8S support.")

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with 'pip install pyyaml'")
    sys.exit(1)

# Templates for additional files
K8S_DEPLOYMENT_TEMPLATE = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: coredns-deployment
  labels:
    app: coredns
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: coredns
  template:
    metadata:
      labels:
        app: coredns
    spec:
      containers:
      - name: coredns
        image: docker.io/coredns/coredns:latest
        command:
        - -conf
        - /root/coredns/Corefile
        volumeMounts:
        - name: config-volume
          mountPath: /root/coredns/Corefile
          subPath: Corefile
        - name: zones-volume
          mountPath: /root/coredns/zones
        ports:
        - containerPort: 53
          protocol: UDP
        securityContext:
          runAsNonRoot: true
          capabilities:
            drop:
            - ALL
            add:
            - NET_BIND_SERVICE
      volumes:
      - name: config-volume
        configMap:
          name: coredns-config
      - name: zones-volume
        configMap:
          name: coredns-zones
---
apiVersion: v1
kind: Service
metadata:
  name: coredns-service
spec:
  selector:
    app: coredns
  ports:
    - protocol: UDP
      port: 53
      targetPort: 53
  type: ClusterIP  # Change to LoadBalancer for external access if needed
"""

ANSIBLE_PLAYBOOK_TEMPLATE = """
---
- hosts: all
  become: yes
  tasks:
    - name: Install Docker
      package:
        name: docker.io
        state: present

    - name: Start Docker service
      service:
        name: docker
        state: started

    - name: Create CoreDNS directories
      file:
        path: /root/coredns/zones
        state: directory

    - name: Copy Corefile
      copy:
        src: ./Corefile
        dest: /root/coredns/Corefile

    - name: Copy zones
      copy:
        src: ./zones/
        dest: /root/coredns/zones/

    - name: Run CoreDNS container
      docker_container:
        name: dns
        image: docker.io/coredns/coredns:latest
        state: started
        restart_policy: always
        command: -conf /root/coredns/Corefile
        volumes:
          - /root/coredns/zones/:/root/coredns/zones/:ro
          - /root/coredns/Corefile:/root/coredns/Corefile:ro
        ports:
          - "53:53/udp"
"""

def check_tool_installed(tool_name: str) -> bool:
    """Check if a command-line tool is installed."""
    try:
        subprocess.check_output([tool_name, '--version'])
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def validate_config(config_path: str, use_podman: bool = False) -> None:
    """Validate CoreDNS config by attempting to parse it in a temporary container."""
    container_tool = 'podman' if use_podman else 'docker'
    if not check_tool_installed(container_tool):
        raise EnvironmentError(f"{container_tool} is not installed or not in PATH.")

    abs_config_path = os.path.abspath(config_path)
    try:
        subprocess.check_call([
            container_tool, 'run', '--rm',
            '-v', f'{abs_config_path}:/Corefile:Z' if use_podman else f'{abs_config_path}:/Corefile',
            'docker.io/coredns/coredns:latest',
            '-conf', '/Corefile', '-print'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("CoreDNS configuration validated successfully.")
    except subprocess.CalledProcessError:
        raise ValueError("CoreDNS configuration validation failed. Please check the Corefile syntax.")

def prepare_deployment_dir(config_path: str, zones_path: str) -> str:
    """Prepare a temporary deployment directory with configs."""
    temp_dir = tempfile.mkdtemp()
    shutil.copy(config_path, os.path.join(temp_dir, 'Corefile'))
    shutil.copytree(zones_path, os.path.join(temp_dir, 'zones'))
    return temp_dir

def cleanup_deployment_dir(temp_dir: str) -> None:
    """Cleanup temporary deployment directory."""
    shutil.rmtree(temp_dir)

def deploy_docker(config_path: str, zones_path: str, scale: int = 1) -> None:
    """Deploy CoreDNS using Docker (multiple instances on different ports for scaling simulation)."""
    if not check_tool_installed('docker'):
        raise EnvironmentError("Docker is not installed or not in PATH.")

    validate_config(config_path)

    temp_dir = prepare_deployment_dir(config_path, zones_path)
    os.chdir(temp_dir)

    try:
        for i in range(scale):
            container_name = f'dns-{i}'
            port = 53 + i
            subprocess.check_call([
                'docker', 'run', '-d', '--name', container_name,
                '-p', f'{port}:53/udp',
                '-v', './zones/:/root/coredns/zones/:ro',
                '-v', './Corefile:/root/coredns/Corefile:ro',
                'docker.io/coredns/coredns:latest',
                '-conf', '/root/coredns/Corefile'
            ])
        print(f"Deployed {scale} CoreDNS instance(s) with Docker on ports 53 to {52 + scale}.")
        print("Note: For true production scaling and load balancing, use Docker Swarm or Kubernetes.")
    finally:
        os.chdir('..')
        # cleanup_deployment_dir(temp_dir)  # Uncomment to cleanup; keep for inspection

def deploy_podman(config_path: str, zones_path: str, scale: int = 1) -> None:
    """Deploy CoreDNS using Podman (multiple instances on different ports)."""
    if not check_tool_installed('podman'):
        raise EnvironmentError("Podman is not installed or not in PATH.")

    validate_config(config_path, use_podman=True)

    temp_dir = prepare_deployment_dir(config_path, zones_path)
    os.chdir(temp_dir)

    try:
        for i in range(scale):
            container_name = f'dns-{i}'
            port = 53 + i
            subprocess.check_call([
                'podman', 'run', '-d', '--name', container_name,
                '-p', f'{port}:53/udp',
                '-v', './zones/:/root/coredns/zones/:ro,Z',
                '-v', './Corefile:/root/coredns/Corefile:ro,Z',
                'docker.io/coredns/coredns:latest',
                '-conf', '/root/coredns/Corefile'
            ])
        print(f"Deployed {scale} CoreDNS instance(s) with Podman on ports 53 to {52 + scale}.")
        print("Note: Each instance on different ports for local testing; use LB for production scaling.")
    finally:
        os.chdir('..')
        # cleanup_deployment_dir(temp_dir)

def deploy_kubernetes(config_path: str, zones_path: str, replicas: int = 3, namespace: str = 'default') -> None:
    """Deploy scalable CoreDNS on Kubernetes."""
    if not K8S_AVAILABLE:
        raise EnvironmentError("Kubernetes Python client not installed.")
    if not check_tool_installed('kubectl'):
        raise EnvironmentError("kubectl is not installed or not in PATH.")

    validate_config(config_path)

    try:
        config.load_kube_config()  # Or load_incluster_config() for in-cluster
    except config.ConfigException:
        raise EnvironmentError("Failed to load Kubernetes config.")

    v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()

    # Create ConfigMap for Corefile
    config_data = {'Corefile': open(config_path, 'r').read()}
    configmap = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name='coredns-config'),
        data=config_data
    )
    try:
        v1.create_namespaced_config_map(namespace, configmap)
    except ApiException as e:
        if e.status != 409:
            raise

    # Create ConfigMap for zones (assuming zones are small files)
    zones_data = {}
    for file in os.listdir(zones_path):
        if file.endswith('.zone'):
            zones_data[file] = open(os.path.join(zones_path, file), 'r').read()
    zones_configmap = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name='coredns-zones'),
        data=zones_data
    )
    try:
        v1.create_namespaced_config_map(namespace, zones_configmap)
    except ApiException as e:
        if e.status != 409:
            raise

    # Generate and apply deployment YAML
    k8s_yaml = K8S_DEPLOYMENT_TEMPLATE.format(replicas=replicas)
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
        tmp.write(k8s_yaml)
        tmp_path = tmp.name

    try:
        subprocess.check_call(['kubectl', 'apply', '-f', tmp_path, '-n', namespace])
        print(f"Deployed CoreDNS with {replicas} replicas on Kubernetes in namespace {namespace}.")
    finally:
        os.unlink(tmp_path)

def deploy_ansible(config_path: str, zones_path: str, inventory: Optional[str] = None) -> None:
    """Deploy CoreDNS using Ansible (on remote hosts)."""
    if not check_tool_installed('ansible-playbook'):
        raise EnvironmentError("Ansible is not installed or not in PATH.")

    validate_config(config_path)

    temp_dir = prepare_deployment_dir(config_path, zones_path)
    os.chdir(temp_dir)

    with open('playbook.yml', 'w') as f:
        f.write(ANSIBLE_PLAYBOOK_TEMPLATE)

    inventory_flag = ['-i', inventory] if inventory else []

    try:
        subprocess.check_call(['ansible-playbook'] + inventory_flag + ['playbook.yml'])
        print("Deployed CoreDNS with Ansible.")
        print("Note: For scalability, run on multiple hosts and use a load balancer.")
    finally:
        os.chdir('..')
        # cleanup_deployment_dir(temp_dir)

def main():
    parser = argparse.ArgumentParser(description="Automate deployment of scalable CoreDNS for DNS services.")
    parser.add_argument('method', choices=['docker', 'podman', 'kubernetes', 'ansible'], help="Deployment method.")
    parser.add_argument('--config', default='./Corefile', help="Path to Corefile.")
    parser.add_argument('--zones', default='./zones', help="Path to zones directory.")
    parser.add_argument('--scale', type=int, default=1, help="Scale factor (replicas for K8S, instances for others).")
    parser.add_argument('--namespace', default='default', help="Kubernetes namespace.")
    parser.add_argument('--inventory', help="Ansible inventory file.")

    args = parser.parse_args()

    if not os.path.exists(args.config):
        raise FileNotFoundError(f"Corefile not found at {args.config}")
    if not os.path.isdir(args.zones):
        raise FileNotFoundError(f"Zones directory not found at {args.zones}")

    try:
        if args.method == 'docker':
            deploy_docker(args.config, args.zones, args.scale)
        elif args.method == 'podman':
            deploy_podman(args.config, args.zones, args.scale)
        elif args.method == 'kubernetes':
            deploy_kubernetes(args.config, args.zones, args.scale, args.namespace)
        elif args.method == 'ansible':
            deploy_ansible(args.config, args.zones, args.inventory)
    except Exception as e:
        print(f"Deployment failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()