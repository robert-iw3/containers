#!/usr/bin/env python3
"""
Deploy the Flink session cluster to Compose, Kubernetes, or multi-host Ansible.

Thin wrapper around the deployment assets in this directory:
  * compose     -> docker-compose.yml            (docker compose / podman-compose)
  * kubernetes  -> k8s-flink-cluster.yaml        (kubectl apply)
  * ansible     -> ansible/deploy-flink.yml      (ansible-playbook)

    python3 deploy_flink.py                      # uses flink_config.yaml
    python3 deploy_flink.py --action cleanup
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("deploy_flink")


class FlinkDeployer:
    def __init__(self, config_path: str = "flink_config.yaml"):
        with open(config_path) as f:
            self.cfg = yaml.safe_load(f)
        self.method = self.cfg.get("deployment", {}).get("method", "compose")
        self.engine = self.cfg.get("container_engine", "podman")
        self.namespace = self.cfg.get("namespace", "flink")
        self.tls = self.cfg.get("security", {}).get("enable_tls", False)
        self.replicas = self.cfg.get("cluster", {}).get("taskmanager_replicas", 3)

    def _run(self, cmd: list[str]) -> None:
        log.info("running: %s", " ".join(cmd))
        subprocess.run(cmd, check=True)

    def _compose(self) -> list[str]:
        if self.engine == "docker":
            return ["docker", "compose", "-f", "docker-compose.yml"]
        return ["podman-compose", "-f", "docker-compose.yml"]

    def ensure_tls(self) -> None:
        if self.tls:
            self._run(["bash", "tls/gen_flink_tls.sh"])

    def deploy(self) -> None:
        if self.method == "compose":
            self.ensure_tls()
            self._run([*self._compose(), "up", "-d", "--scale", f"taskmanager={self.replicas}"])
        elif self.method == "kubernetes":
            if self.tls:
                log.info("create the flink-tls secret first (see k8s-flink-cluster.yaml header)")
            self._run(["kubectl", "apply", "-f", "k8s-flink-cluster.yaml"])
        elif self.method == "ansible":
            self._run(["ansible-playbook", "-i", "ansible/inventory.ini", "ansible/deploy-flink.yml"])
        else:
            sys.exit(f"unknown deployment method: {self.method}")
        log.info("Flink deploy (%s) submitted", self.method)

    def cleanup(self) -> None:
        if self.method == "compose":
            self._run([*self._compose(), "down", "-v"])
        elif self.method == "kubernetes":
            self._run(["kubectl", "delete", "-f", "k8s-flink-cluster.yaml"])
        else:
            log.info("no automated cleanup for method '%s'", self.method)


def main() -> None:
    p = argparse.ArgumentParser(description="Deploy Apache Flink")
    p.add_argument("--config", default="flink_config.yaml")
    p.add_argument("--action", choices=["deploy", "cleanup"], default="deploy")
    args = p.parse_args()
    d = FlinkDeployer(args.config)
    d.deploy() if args.action == "deploy" else d.cleanup()


if __name__ == "__main__":
    main()
