import argparse
import os
import subprocess
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import hvac
import time
import shutil
import tempfile
import git

def load_vault_secrets(vault_addr, vault_token, path='secret/hanko'):
    client = hvac.Client(url=vault_addr, token=vault_token)
    try:
        secrets = client.secrets.kv.v2.read_secret_version(path=path)['data']['data']
        return secrets
    except Exception as e:
        print(f"Error loading Vault secrets: {e}")
        exit(1)

def clone_hanko_repo(temp_dir):
    repo_url = "https://github.com/teamhanko/hanko.git"
    try:
        print(f"Cloning Hanko repository from {repo_url} to {temp_dir}")
        git.Repo.clone_from(repo_url, temp_dir)
        return temp_dir
    except Exception as e:
        print(f"Error cloning Hanko repository: {e}")
        exit(1)

def build_and_push_images(registry, tag='latest'):
    # Create temporary directory for cloning the repository
    temp_dir = tempfile.mkdtemp()

    try:
        # Clone the Hanko repository
        repo_dir = clone_hanko_repo(temp_dir)

        images = [
            {'name': 'hanko-backend', 'context': 'backend', 'dockerfile': 'backend/Dockerfile'},
            {'name': 'hanko-frontend', 'context': 'frontend', 'dockerfile': 'frontend/Dockerfile'}
        ]

        for image in images:
            image_name = f"{registry}/{image['name']}:{tag}"
            dockerfile_path = os.path.join(repo_dir, image['dockerfile'])
            context_path = os.path.join(repo_dir, image['context'])

            print(f"Building image {image_name} from {context_path}")
            try:
                subprocess.run([
                    'docker', 'build', '-t', image_name,
                    '-f', dockerfile_path, context_path
                ], check=True)
                print(f"Pushing image {image_name}")
                subprocess.run(['docker', 'push', image_name], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error building/pushing {image_name}: {e}")
                exit(1)
    finally:
        # Clean up the temporary directory
        print(f"Cleaning up temporary directory {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)

def apply_k8s_manifests(namespace, registry, tag='latest'):
    config.load_kube_config()
    v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()
    networking_v1 = client.NetworkingV1Api()

    manifests = [
        'k8s/namespace.yml',
        'k8s/network-policy.yml',
        'k8s/postgres.yml',
        'k8s/hanko.yml',
        'k8s/elements.yml',
        'k8s/mailslurper.yml'
    ]

    for manifest in manifests:
        with open(manifest) as f:
            manifest_data = yaml.safe_load(f)
            if 'metadata' in manifest_data:
                manifest_data['metadata']['namespace'] = namespace
            if 'spec' in manifest_data and 'template' in manifest_data['spec']:
                for container in manifest_data['spec']['template']['spec']['containers']:
                    if 'image' in container:
                        container['image'] = container['image'].replace('${CONTAINER_REGISTRY}', registry).replace('${TAG}', tag)

        with open(f"/tmp/{os.path.basename(manifest)}", 'w') as f:
            yaml.dump(manifest_data, f)

        try:
            subprocess.run(['kubectl', 'apply', '-f', f"/tmp/{os.path.basename(manifest)}"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error applying {manifest}: {e}")
            exit(1)

def wait_for_deployment(namespace, deployment, timeout=300):
    config.load_kube_config()
    apps_v1 = client.AppsV1Api()
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            dep = apps_v1.read_namespaced_deployment(deployment, namespace)
            if dep.status.ready_replicas == dep.spec.replicas:
                print(f"Deployment {deployment} is ready")
                return True
        except ApiException as e:
            print(f"Error checking deployment {deployment}: {e}")
        time.sleep(5)
    print(f"Timeout waiting for deployment {deployment}")
    return False

def main():
    parser = argparse.ArgumentParser(description='Hanko Deployment Script')
    parser.add_argument('--namespace', default='hanko', help='Kubernetes namespace')
    parser.add_argument('--registry', required=True, help='Container registry')
    parser.add_argument('--tag', default='latest', help='Image tag')
    args = parser.parse_args()

    # Load secrets
    vault_addr = os.getenv('VAULT_ADDR')
    vault_token = os.getenv('VAULT_TOKEN')
    if not vault_addr or not vault_token:
        print("VAULT_ADDR and VAULT_TOKEN must be set")
        exit(1)
    secrets = load_vault_secrets(vault_addr, vault_token)

    # Build and push images
    build_and_push_images(args.registry, args.tag)

    # Apply Kubernetes manifests
    apply_k8s_manifests(args.namespace, args.registry, args.tag)

    # Wait for deployments
    deployments = ['hanko', 'elements', 'postgresql', 'mailslurper']
    for dep in deployments:
        if not wait_for_deployment(args.namespace, dep):
            exit(1)

    print("Deployment completed successfully")

if __name__ == '__main__':
    main()