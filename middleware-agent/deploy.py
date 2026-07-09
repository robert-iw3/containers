import argparse
import os
import subprocess
import sys
from pathlib import Path

try:
    import docker
    import podman
    from kubernetes import client, config
    from ansible_runner import Runner
except ImportError as e:
    print(f"Error: Missing dependency {e}. Install with: pip install docker podman kubernetes ansible-runner")
    sys.exit(1)

def build_docker_image(dockerfile_path, image_name="mw-agent:1.3.0"):
    """Build Docker image from Dockerfile."""
    try:
        client = docker.from_env()
        print(f"Building Docker image {image_name}...")
        client.images.build(path=str(Path(dockerfile_path).parent), dockerfile=dockerfile_path, tag=image_name)
        print("Build successful.")
    except docker.errors.BuildError as e:
        print(f"Build failed: {e}")
        sys.exit(1)

def deploy_docker(image_name, env_vars):
    """Deploy with Docker."""
    client = docker.from_env()
    try:
        print("Deploying with Docker...")
        client.containers.run(
            image_name,
            name="mw-agent",
            detach=True,
            restart_policy={"Name": "always"},
            environment=env_vars,
            volumes={
                "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "ro"},
                "/var/log": {"bind": "/var/log", "mode": "ro"},
                "/proc": {"bind": "/host/proc", "mode": "ro"},
                "/sys": {"bind": "/host/sys", "mode": "ro"},
                "/": {"bind": "/host/root", "mode": "ro"},
            },
            network_mode="host",
            pid_mode="host",
            cap_drop=["ALL"],
            read_only=True,
            tmpfs={"/tmp": ""}
        )
        print("Docker deployment successful.")
    except docker.errors.APIError as e:
        print(f"Docker deployment failed: {e}")
        sys.exit(1)

def deploy_podman(image_name, env_vars):
    """Deploy with Podman."""
    try:
        client = podman.PodmanClient()
        print("Deploying with Podman...")
        client.containers.run(
            image_name,
            name="mw-agent",
            detach=True,
            restart_policy="always",
            environment=env_vars,
            volumes={
                "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "ro"},
                "/var/log": {"bind": "/var/log", "mode": "ro"},
                "/proc": {"bind": "/host/proc", "mode": "ro"},
                "/sys": {"bind": "/host/sys", "mode": "ro"},
                "/": {"bind": "/host/root", "mode": "ro"},
            },
            network_mode="host",
            pid_mode="host",
            cap_drop=["ALL"],
            read_only=True,
            tmpfs=["/tmp"]
        )
        print("Podman deployment successful.")
    except Exception as e:
        print(f"Podman deployment failed: {e}")
        sys.exit(1)

def deploy_kubernetes(image_name, env_vars):
    """Deploy with Kubernetes."""
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()
        apps_v1 = client.AppsV1Api()
        namespace = "monitoring"

        print(f"Creating namespace {namespace}...")
        try:
            v1.create_namespace(client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace)))
        except client.ApiException as e:
            if e.status != 409:  # Namespace already exists
                raise

        print("Applying Kubernetes manifests...")
        manifests = ["mw-agent-secret.yaml", "mw-agent-configmap.yaml", "mw-agent-daemonset.yaml"]
        for manifest in manifests:
            subprocess.run(["kubectl", "apply", "-f", manifest], check=True)
        print("Kubernetes deployment successful.")
    except Exception as e:
        print(f"Kubernetes deployment failed: {e}")
        sys.exit(1)

def deploy_ansible(playbook_path, env_vars):
    """Deploy with Ansible."""
    try:
        print("Deploying with Ansible...")
        Runner(
            playbook=playbook_path,
            envvars=env_vars,
            quiet=False
        ).run()
        print("Ansible deployment successful.")
    except Exception as e:
        print(f"Ansible deployment failed: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Deploy Middleware Agent")
    parser.add_argument("--method", choices=["docker", "podman", "kubernetes", "ansible"], required=True,
                        help="Deployment method")
    parser.add_argument("--dockerfile", default="Dockerfile", help="Path to Dockerfile")
    parser.add_argument("--image", default="mw-agent:1.3.0", help="Docker image name")
    parser.add_argument("--api-key", required=True, help="Middleware API key")
    parser.add_argument("--target", default="https://ingest.middleware.io", help="Middleware ingest endpoint")
    parser.add_argument("--tags", default="env:prod,team:ops", help="Host tags")
    parser.add_argument("--playbook", default="mw-agent-deploy.yaml", help="Ansible playbook path")
    args = parser.parse_args()

    env_vars = {
        "MW_API_KEY": args.api_key,
        "MW_TARGET": args.target,
        "MW_HOST_TAGS": args.tags
    }

    # Build image (except for Kubernetes, which assumes pre-built)
    if args.method != "kubernetes":
        build_docker_image(args.dockerfile, args.image)

    # Deploy based on method
    if args.method == "docker":
        deploy_docker(args.image, env_vars)
    elif args.method == "podman":
        deploy_podman(args.image, env_vars)
    elif args.method == "kubernetes":
        deploy_kubernetes(args.image, env_vars)
    elif args.method == "ansible":
        deploy_ansible(args.playbook, env_vars)

if __name__ == "__main__":
    main()