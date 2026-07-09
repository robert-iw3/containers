import argparse
import os
import shutil
import asyncio
import subprocess
from datetime import datetime
from typing import List, Dict
import aiofiles
import psutil
import yaml
from tenacity import retry, stop_after_attempt, wait_exponential

async def validate_resources():
    cpu_count = psutil.cpu_count()
    mem_total = psutil.virtual_memory().total // (1024 ** 3)  # GB
    disk_free = psutil.disk_usage("/").free // (1024 ** 3)  # GB
    if cpu_count < 2:
        print("Warning: Less than 2 CPU cores available")
    if mem_total < 2:
        print("Warning: Less than 2GB memory available")
    if disk_free < 2:
        print("Warning: Less than 2GB disk space available")

async def backup_files(config_files: List[str], backup_dir: str):
    await aiofiles.os.makedirs(backup_dir, exist_ok=True)
    for src in config_files:
        if await aiofiles.os.path.exists(src):
            dst = os.path.join(backup_dir, os.path.basename(src))
            async with aiofiles.open(src, "rb") as s, aiofiles.open(dst, "wb") as d:
                await d.write(await s.read())

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=0.1, max=5))
async def deploy_docker(config: Dict, use_podman: bool) -> None:
    compose_cmd = "podman-compose" if use_podman else "docker-compose"
    try:
        subprocess.run([compose_cmd, "--version"], check=True)
    except subprocess.CalledProcessError:
        raise Exception(f"{compose_cmd} not found")

    env = os.environ.copy()
    env.update({
        "SCHEMAS_FILE": config["sql_connectors"]["schemas_file"],
        "STATE_PATH": config["sql_connectors"]["state_path"],
        "SPLUNK_ENABLED": str(config["splunk"]["enabled"]),
        "SPLUNK_HEC_URL": config["splunk"]["hec_url"],
        "SPLUNK_TOKEN": config["splunk"]["hec_token"],
        "DB_TYPE": config["database"]["db_type"],
        "DB_CONN_STR": config["database"]["conn_str"],
        "BATCH_SIZE": str(config["batch_size"]),
        "BUFFER_TIMEOUT": str(config["buffer_timeout"]),
        "WORKER_COUNT": str(config["worker_count"]),
        "POLL_INTERVAL": str(config["poll_interval"]),
        "CDC_ENABLED": str(config["cdc_enabled"]),
        "MAX_CONNECTIONS_PER_TABLE": str(config["max_connections_per_table"]),
        "METRICS_PORT": str(config["metrics_port"]),
        "PYTHON_LOGGING_LEVEL": "INFO",
        "SQLCIPHER_KEY": config.get("sqlcipher_key", ""),
    })
    subprocess.run([compose_cmd, "up", "-d", "--build"], env=env, check=True)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=0.1, max=5))
async def deploy_kubernetes(config: Dict) -> None:
    try:
        subprocess.run(["kubectl", "--version"], check=True)
    except subprocess.CalledProcessError:
        raise Exception("kubectl not found")

    manifests = ["sql-splunk-deployment.yaml"]
    for manifest in manifests:
        async with aiofiles.open(manifest, "r") as f:
            content = await f.read()
        content = content.replace("{{namespace}}", config["deployment"]["namespace"])
        content = content.replace("{{replicas}}", str(config["deployment"]["kubernetes"]["replicas"]))
        content = content.replace("{{splunk_hec_url}}", config["splunk"]["hec_url"])
        content = content.replace("{{splunk_token}}", config["splunk"]["hec_token"])
        content = content.replace("{{batch_size}}", str(config["batch_size"]))
        content = content.replace("{{buffer_timeout}}", str(config["buffer_timeout"]))
        content = content.replace("{{worker_count}}", str(config["worker_count"]))
        content = content.replace("{{poll_interval}}", str(config["poll_interval"]))
        content = content.replace("{{db_type}}", config["database"]["db_type"])
        content = content.replace("{{db_conn_str}}", config["database"]["conn_str"])
        content = content.replace("{{cdc_enabled}}", str(config["cdc_enabled"]))
        content = content.replace("{{max_connections_per_table}}", str(config["max_connections_per_table"]))
        content = content.replace("{{metrics_port}}", str(config["metrics_port"]))

        temp_file = f"temp_{manifest}"
        async with aiofiles.open(temp_file, "w") as f:
            await f.write(content)
        subprocess.run(["kubectl", "apply", "-f", temp_file, "--dry-run=client"], check=True)
        subprocess.run(["kubectl", "apply", "-f", temp_file], check=True)
        await aiofiles.os.remove(temp_file)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=0.1, max=5))
async def deploy_ansible(config: Dict) -> None:
    try:
        subprocess.run(["ansible-playbook", "--version"], check=True)
    except subprocess.CalledProcessError:
        raise Exception("ansible-playbook not found")

    subprocess.run(["ansible-playbook", "deploy_sql_connectors.yml", "-e", f"config_file=deploy_config.yaml"], check=True)

async def cleanup_docker(use_podman: bool) -> None:
    compose_cmd = "podman-compose" if use_podman else "docker-compose"
    if subprocess.run([compose_cmd, "--version"]).returncode == 0:
        subprocess.run([compose_cmd, "down", "-v"], check=True)

async def cleanup_kubernetes(config: Dict) -> None:
    if subprocess.run(["kubectl", "--version"]).returncode == 0:
        manifests = ["sql-splunk-deployment.yaml"]
        for manifest in manifests:
            subprocess.run(["kubectl", "delete", "-f", manifest, "-n", config["deployment"]["namespace"]], check=False)

async def load_config(config_file: str) -> Dict:
    try:
        async with aiofiles.open(config_file, "r") as f:
            return yaml.safe_load(await f.read())
    except Exception as e:
        raise Exception(f"Failed to load config: {e}")

async def main():
    parser = argparse.ArgumentParser(description="Deploy SQL Connectors")
    parser.add_argument("--config", default="deploy_config.yaml", help="Path to configuration file")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup deployment")
    args = parser.parse_args()

    config_files = [
        "deploy_config.yaml",
        "docker-compose.yml",
        "Dockerfile",
        "schemas.yaml",
        "sql-splunk-deployment.yaml",
        "deploy_sql_connectors.yml",
    ]

    config = await load_config(args.config)
    if args.cleanup:
        print("Cleaning up SQL connectors deployment...")
        if config["deployment"]["method"] == "docker":
            await cleanup_docker(False)
        elif config["deployment"]["method"] == "podman":
            await cleanup_docker(True)
        elif config["deployment"]["method"] == "kubernetes":
            await cleanup_kubernetes(config)
        elif config["deployment"]["method"] == "ansible":
            await deploy_ansible(config)
        else:
            raise Exception(f"Unsupported deployment method: {config['deployment']['method']}")
        return

    await validate_resources()
    backup_dir = f"backup/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    await backup_files(config_files, backup_dir)

    if config["deployment"]["method"] == "docker":
        await deploy_docker(config, False)
    elif config["deployment"]["method"] == "podman":
        await deploy_docker(config, True)
    elif config["deployment"]["method"] == "kubernetes":
        await deploy_kubernetes(config)
    elif config["deployment"]["method"] == "ansible":
        await deploy_ansible(config)
    else:
        raise Exception(f"Unsupported deployment method: {config['deployment']['method']}")

    print("SQL connectors deployed")

if __name__ == "__main__":
    asyncio.run(main())