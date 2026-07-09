import os
import yaml
import subprocess
import argparse
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import time
import shutil

def check_command_exists(command):
    return shutil.which(command) is not None

def load_yaml(file_path):
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def create_namespace(api_instance, namespace):
    try:
        api_instance.create_namespace(client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace)))
        print(f"Namespace {namespace} created")
    except ApiException as e:
        if e.status != 409:
            raise

def create_consul_secret(namespace, encrypt_key):
    config.load_kube_config()
    v1 = client.CoreV1Api()

    secret = client.V1Secret(
        metadata=client.V1ObjectMeta(name="consul-gossip-key"),
        string_data={"gossip-encryption-key": encrypt_key}
    )

    try:
        v1.create_namespaced_secret(namespace, secret)
        print("Consul gossip secret created")
    except ApiException as e:
        if e.status != 409:
            raise

def wait_for_kubernetes_pods(namespace, timeout=300):
    config.load_kube_config()
    v1 = client.CoreV1Api()
    start_time = time.time()

    while time.time() - start_time < timeout:
        pods = v1.list_namespaced_pod(namespace, label_selector="app=consul")
        if all(pod.status.phase == "Running" for pod in pods.items):
            print("All Consul pods are running")
            return
        time.sleep(5)
    raise TimeoutError("Consul pods failed to reach Running state")

def wait_for_container_runtime(compose_file, timeout=300):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            output = subprocess.check_output(["docker", "compose", "-f", compose_file, "ps", "-q"], text=True)
            if output.strip():
                print("Consul containers are running")
                return
        except subprocess.CalledProcessError:
            pass
        time.sleep(5)
    raise TimeoutError("Consul containers failed to start")

def deploy_docker_podman(compose_file, runtime="docker"):
    try:
        if runtime == "podman":
            subprocess.run([runtime, "compose", "-f", compose_file, "up", "-d"], check=True)
        else:
            subprocess.run([runtime, "compose", "-f", compose_file, "up", "-d"], check=True)
        print(f"Consul deployed using {runtime}")
        wait_for_container_runtime(compose_file)
    except subprocess.CalledProcessError as e:
        print(f"Failed to deploy with {runtime}: {e}")
        raise

def deploy_kubernetes(manifest_path, namespace, encrypt_key):
    config.load_kube_config()
    v1 = client.CoreV1Api()

    create_namespace(v1, namespace)
    create_consul_secret(namespace, encrypt_key)

    subprocess.run(["kubectl", "apply", "-f", manifest_path], check=True)
    print(f"Applied Kubernetes manifest: {manifest_path}")

    wait_for_kubernetes_pods(namespace)
    print("Consul cluster deployed successfully on Kubernetes")

def main():
    parser = argparse.ArgumentParser(description="Deploy Consul cluster")
    parser.add_argument("--runtime", choices=["docker", "podman", "kubernetes"],
                       default="kubernetes", help="Container runtime to use")
    args = parser.parse_args()

    # Configuration
    namespace = "consul"
    compose_file = "docker-compose.yml"
    kubernetes_manifest = "consul-deployment.yaml"
    encrypt_key = "aPuGh+5UDskRAbkLaXRzFoSOcSM+5vAK+NEYOWHJH7w="

    # Check available runtimes
    if args.runtime == "docker" and not check_command_exists("docker"):
        raise RuntimeError("Docker is not installed")
    if args.runtime == "podman" and not check_command_exists("podman"):
        raise RuntimeError("Podman is not installed")
    if args.runtime == "kubernetes" and not check_command_exists("kubectl"):
        raise RuntimeError("kubectl is not installed")

    # Deploy based on runtime
    if args.runtime in ["docker", "podman"]:
        deploy_docker_podman(compose_file, args.runtime)
    else:
        deploy_kubernetes(kubernetes_manifest, namespace, encrypt_key)

if __name__ == "__main__":
    main()