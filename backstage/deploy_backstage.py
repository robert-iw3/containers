import os
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import base64

def load_env_vars(env_file=".env"):
    """Load environment variables from .env file."""
    env_vars = {}
    with open(env_file, "r") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                env_vars[key] = value
    return env_vars

def create_secret(namespace, env_vars):
    """Create Kubernetes Secret for sensitive data."""
    v1 = client.CoreV1Api()
    secret = client.V1Secret(
        metadata=client.V1ObjectMeta(name="backstage-secrets", namespace=namespace),
        type="Opaque",
        string_data={
            "POSTGRESQL_USERNAME": env_vars.get("POSTGRESQL_USERNAME", ""),
            "POSTGRESQL_PASSWORD": env_vars.get("POSTGRESQL_PASSWORD", ""),
            "POSTGRESQL_DATABASE": env_vars.get("POSTGRESQL_DATABASE", ""),
            "POSTGRESQL_REPLICATION_USER": env_vars.get("POSTGRESQL_REPLICATION_USER", ""),
            "POSTGRESQL_REPLICATION_PASSWORD": env_vars.get("POSTGRESQL_REPLICATION_PASSWORD", ""),
            "GITHUB_TOKEN": env_vars.get("GITHUB_TOKEN", ""),
            "AUTH_GITHUB_CLIENT_ID": env_vars.get("AUTH_GITHUB_CLIENT_ID", ""),
            "AUTH_GITHUB_CLIENT_SECRET": env_vars.get("AUTH_GITHUB_CLIENT_SECRET", ""),
            "AUTH_GITHUB_ENTERPRISE_INSTANCE_URL": env_vars.get("AUTH_GITHUB_ENTERPRISE_INSTANCE_URL", "")
        }
    )
    try:
        v1.create_namespaced_secret(namespace=namespace, body=secret)
        print("Secret created successfully.")
    except ApiException as e:
        if e.status == 409:
            print("Secret already exists, updating...")
            v1.replace_namespaced_secret(name="backstage-secrets", namespace=namespace, body=secret)
        else:
            raise

def apply_k8s_manifest(manifest_file, namespace):
    """Apply Kubernetes manifest file."""
    with open(manifest_file, "r") as f:
        manifest = yaml.safe_load(f)

    api_instance = client.ApiClient()
    for resource in manifest if isinstance(manifest, list) else [manifest]:
        kind = resource.get("kind")
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "")

        if kind == "Namespace":
            v1 = client.CoreV1Api()
            try:
                v1.create_namespace(body=resource)
                print(f"Namespace {name} created.")
            except ApiException as e:
                if e.status != 409:
                    raise
                print(f"Namespace {name} already exists.")

        elif kind == "Deployment":
            apps_v1 = client.AppsV1Api()
            try:
                apps_v1.create_namespaced_deployment(namespace=namespace, body=resource)
                print(f"Deployment {name} created.")
            except ApiException as e:
                if e.status == 409:
                    apps_v1.replace_namespaced_deployment(name=name, namespace=namespace, body=resource)
                    print(f"Deployment {name} updated.")
                else:
                    raise

        elif kind == "Service":
            v1 = client.CoreV1Api()
            try:
                v1.create_namespaced_service(namespace=namespace, body=resource)
                print(f"Service {name} created.")
            except ApiException as e:
                if e.status == 409:
                    v1.replace_namespaced_service(name=name, namespace=namespace, body=resource)
                    print(f"Service {name} updated.")
                else:
                    raise

        elif kind == "NetworkPolicy":
            net_v1 = client.NetworkingV1Api()
            try:
                net_v1.create_namespaced_network_policy(namespace=namespace, body=resource)
                print(f"NetworkPolicy {name} created.")
            except ApiException as e:
                if e.status == 409:
                    net_v1.replace_namespaced_network_policy(name=name, namespace=namespace, body=resource)
                    print(f"NetworkPolicy {name} updated.")
                else:
                    raise

        elif kind == "CronJob":
            batch_v1 = client.BatchV1Api()
            try:
                batch_v1.create_namespaced_cron_job(namespace=namespace, body=resource)
                print(f"CronJob {name} created.")
            except ApiException as e:
                if e.status == 409:
                    batch_v1.replace_namespaced_cron_job(name=name, namespace=namespace, body=resource)
                    print(f"CronJob {name} updated.")
                else:
                    raise

def main():
    """Main function to deploy Backstage on Kubernetes."""
    try:
        # Load Kubernetes configuration
        config.load_kube_config()

        # Load environment variables
        env_vars = load_env_vars()

        # Create namespace
        namespace = "backstage"
        v1 = client.CoreV1Api()
        try:
            v1.create_namespace(body=client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace)))
            print(f"Namespace {namespace} created.")
        except ApiException as e:
            if e.status != 409:
                raise
            print(f"Namespace {namespace} already exists.")

        # Create Secret
        create_secret(namespace, env_vars)

        # Build Docker image
        os.system("docker build -t backstage:latest .")

        # Apply Kubernetes manifest
        apply_k8s_manifest("backstage-deployment.yaml", namespace)

        print("Backstage deployment completed successfully.")

    except Exception as e:
        print(f"Error during deployment: {str(e)}")
        raise

if __name__ == "__main__":
    main()