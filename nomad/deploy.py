import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


class ConfigError(Exception):
    pass


def load_config(path):
    with open(path) as f:
        config = yaml.safe_load(f)
    validate_config(config)
    return config


def _require_odd_quorum(count, label):
    if count < 1:
        raise ConfigError(f"{label} must be at least 1")
    if count % 2 == 0:
        raise ConfigError(
            f"{label} is {count}; Raft quorum requires an odd number (1, 3, 5, ...) "
            f"to tolerate failures without a split-brain"
        )


def validate_config(config):
    if not config:
        raise ConfigError("cluster.yml is empty")
    if "avenue" not in config:
        raise ConfigError("cluster.yml must set 'avenue' to 'ansible' or 'terraform'")
    if config["avenue"] not in ("ansible", "terraform"):
        raise ConfigError(f"unknown avenue '{config['avenue']}', expected 'ansible' or 'terraform'")

    features = config.get("features", {})
    bootstrap_expect = features.get("bootstrap_expect", 3)

    if config["avenue"] == "ansible":
        ansible_cfg = config.get("ansible")
        if not ansible_cfg:
            raise ConfigError("avenue is 'ansible' but no 'ansible:' section was provided")
        servers = ansible_cfg.get("servers", [])
        if not servers:
            raise ConfigError("ansible.servers must list at least one host")
        if len(servers) != bootstrap_expect:
            raise ConfigError(
                f"features.bootstrap_expect is {bootstrap_expect} but {len(servers)} servers "
                f"were listed under ansible.servers; these must match for the server quorum "
                f"to actually form"
            )
        _require_odd_quorum(len(servers), "the number of servers listed")
        for role in ("servers", "clients", "monitoring"):
            for host in ansible_cfg.get(role, []):
                if "name" not in host or "address" not in host:
                    raise ConfigError(f"each host in ansible.{role} needs a 'name' and an 'address'")

    if config["avenue"] == "terraform":
        tf_cfg = config.get("terraform")
        if not tf_cfg:
            raise ConfigError("avenue is 'terraform' but no 'terraform:' section was provided")
        if not tf_cfg.get("region"):
            raise ConfigError("terraform.region is required")
        _require_odd_quorum(tf_cfg.get("server_count", bootstrap_expect), "terraform.server_count")
        if not tf_cfg.get("ssl_cert_arn"):
            raise ConfigError("terraform.ssl_cert_arn is required (used for the Grafana HTTPS listener)")


def render_inventory(config):
    ansible_cfg = config["ansible"]
    lines = ["[nomad_servers]"]
    for host in ansible_cfg["servers"]:
        lines.append(f"{host['name']} ansible_host={host['address']}")
    lines.append("")
    lines.append("[nomad_clients]")
    for host in ansible_cfg.get("clients", []):
        lines.append(f"{host['name']} ansible_host={host['address']}")
    lines.append("")
    lines.append("[nomad_monitoring]")
    for host in ansible_cfg.get("monitoring", []):
        lines.append(f"{host['name']} ansible_host={host['address']}")
    lines.append("")
    lines.append("[nomad_cluster:children]")
    lines.append("nomad_servers")
    lines.append("nomad_clients")
    lines.append("nomad_monitoring")
    lines.append("")
    lines.append("[nomad_cluster:vars]")
    lines.append(f"ansible_user={ansible_cfg.get('ssh_user', 'ansible')}")
    lines.append(f"ansible_ssh_private_key_file={ansible_cfg.get('ssh_private_key', '~/.ssh/id_rsa')}")
    return "\n".join(lines) + "\n"


def render_group_vars(config):
    features = config.get("features", {})
    return {
        "nomad_tls_enabled": features.get("tls_enabled", True),
        "nomad_acl_enabled": features.get("acl_enabled", True),
        "nomad_gossip_encryption_enabled": features.get("gossip_encryption_enabled", True),
        "nomad_vault_enabled": features.get("vault_enabled", False),
        "nomad_consul_enabled": features.get("consul_enabled", False),
        "nomad_podman_enabled": features.get("podman_enabled", True),
        "nomad_telemetry_enabled": features.get("telemetry_enabled", True),
        "nomad_bootstrap_expect": features.get("bootstrap_expect", 3),
        "nomad_allowed_ips": config.get("admin_cidr_blocks", ["127.0.0.1"]),
    }


def deploy_ansible(config, work_dir, dry_run, extra_args):
    inventory_path = work_dir / "inventory.ini"
    inventory_path.write_text(render_inventory(config))

    group_vars_path = work_dir / "group_vars_all.yml"
    with open(group_vars_path, "w") as f:
        yaml.safe_dump(render_group_vars(config), f, default_flow_style=False)

    cmd = [
        "ansible-playbook",
        "-i", str(inventory_path.resolve()),
        str(ROOT / "ansible" / "playbooks" / "nomad.yml"),
        "-e", f"@{group_vars_path.resolve()}",
    ] + extra_args

    print(f"generated inventory: {inventory_path}")
    print(f"generated group_vars: {group_vars_path}")
    print("command:", " ".join(cmd))
    if dry_run:
        return 0
    return subprocess.run(cmd, cwd=ROOT / "ansible").returncode


def render_tfvars(config):
    tf_cfg = config["terraform"]
    features = config.get("features", {})
    return {
        "aws_region": tf_cfg["region"],
        "secondary_region": tf_cfg.get("secondary_region", tf_cfg["region"]),
        "cluster_name": config.get("cluster_name", "nomad"),
        "num_nomad_servers": tf_cfg.get("server_count", features.get("bootstrap_expect", 3)),
        "num_nomad_clients": tf_cfg.get("client_count", 3),
        "ssl_certificate_arn": tf_cfg.get("ssl_cert_arn", ""),
        "vault_enabled": features.get("vault_enabled", True),
        "consul_enabled": features.get("consul_enabled", True),
        "admin_cidr_blocks": config.get("admin_cidr_blocks", []),
    }


def deploy_terraform(config, work_dir, dry_run, extra_args):
    tfvars_path = work_dir / "generated.auto.tfvars.json"
    with open(tfvars_path, "w") as f:
        json.dump(render_tfvars(config), f, indent=2)

    terraform_dir = ROOT / "terraform"
    shutil.copy(tfvars_path, terraform_dir / tfvars_path.name)

    init_cmd = ["terraform", "init"]
    apply_cmd = ["terraform", "apply"] + extra_args

    print(f"generated tfvars: {tfvars_path}")
    print("command:", " ".join(init_cmd))
    print("command:", " ".join(apply_cmd))
    if dry_run:
        return 0
    result = subprocess.run(init_cmd, cwd=terraform_dir)
    if result.returncode != 0:
        return result.returncode
    return subprocess.run(apply_cmd, cwd=terraform_dir).returncode


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Single entry point for deploying a Nomad cluster across any supported avenue"
    )
    parser.add_argument("--config", default="cluster.yml", help="Path to cluster.yml (see cluster.yml.example)")
    parser.add_argument("--validate-only", action="store_true", help="Validate cluster.yml and exit")
    parser.add_argument("--dry-run", action="store_true", help="Render inventory/tfvars and print the commands without running them")
    parser.add_argument("--work-dir", default=".nomad-deploy", help="Directory to write generated inventory/tfvars into")
    parser.add_argument("extra_args", nargs=argparse.REMAINDER, help="Extra arguments passed through to ansible-playbook or terraform")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"invalid cluster.yml: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"config file not found: {args.config}", file=sys.stderr)
        print("copy cluster.yml.example to cluster.yml and edit it first", file=sys.stderr)
        return 1

    if args.validate_only:
        print("cluster.yml is valid")
        return 0

    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    extra_args = args.extra_args
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]

    if config["avenue"] == "ansible":
        return deploy_ansible(config, work_dir, args.dry_run, extra_args)
    return deploy_terraform(config, work_dir, args.dry_run, extra_args)


if __name__ == "__main__":
    sys.exit(main())
