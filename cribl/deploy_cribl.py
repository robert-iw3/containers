#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os
import re

def validate_host(host):
    """Validate host:port format."""
    if not re.match(r'^[a-zA-Z0-9.-]+:[0-9]{1,5}$', host):
        raise argparse.ArgumentTypeError(f"Invalid host:port format: {host}")
    return host

def main():
    parser = argparse.ArgumentParser(description="Deploy Cribl with Ansible, supporting Kubernetes, Docker, or Podman. Focus on Splunk/Elastic integrations.")
    parser.add_argument('--platform', required=True, choices=['kubernetes', 'docker', 'podman'], help="Deployment platform.")
    parser.add_argument('--replicas', type=int, default=2, help="Worker replicas (default: 2).")
    parser.add_argument('--namespace', default='default', help="Kubernetes namespace.")
    parser.add_argument('--splunk_host', type=validate_host, default='splunk:9997', help="Splunk host:port.")
    parser.add_argument('--elastic_host', type=validate_host, default='elastic:9200', help="Elastic host:port.")
    parser.add_argument('--splunk_hec_token', help="Splunk HEC token for authentication.")
    parser.add_argument('--elastic_api_key', help="Elastic API key for authentication.")
    parser.add_argument('--dry-run', action='store_true', help="Ansible check mode.")
    parser.add_argument('--verbose', action='store_true', help="Verbose output.")
    parser.add_argument('--data-volume', type=int, default=1000, help="Expected data volume in GB/day (default: 1000).")
    parser.add_argument('--reduction-factor', type=float, default=0.5, help="Data reduction factor (0-1, default: 0.5).")
    parser.add_argument('--cpus-per-worker', type=int, default=4, help="CPUs per worker (default: 4).")
    args = parser.parse_args()

    # Calculate replicas based on sizing: 200 GB/day per vCPU, in+out = volume * (1 + (1-reduction))
    effective_volume = args.data_volume * (1 + (1 - args.reduction_factor))
    required_vcpus = effective_volume / 200
    calculated_replicas = max(args.replicas, int(required_vcpus / args.cpus_per_worker) + 1)
    print(f"Calculated replicas: {calculated_replicas}")

    if args.platform in ['docker', 'podman'] and calculated_replicas > 1:
        print("Warning: Scaling on single-host Docker/Podman requires port offsets; consider cluster mode.")

    extra_vars = {
        'platform': args.platform,
        'replicas': calculated_replicas,
        'k8s_namespace': args.namespace,
        'splunk_host': args.splunk_host,
        'elastic_host': args.elastic_host,
        'splunk_hec_token': args.splunk_hec_token or '',
        'elastic_api_key': args.elastic_api_key or '',
        'data_volume': args.data_volume,
        'reduction_factor': args.reduction_factor,
        'cpus_per_worker': args.cpus_per_worker,
    }
    extra_vars_str = ' '.join([f"{k}={v}" for k, v in extra_vars.items()])

    ansible_cmd = ["ansible-playbook", "deploy_cribl.yml", "-e", extra_vars_str]
    if args.dry_run:
        ansible_cmd.append("--check")
    if args.verbose:
        ansible_cmd.append("-v")

    required_files = ['deploy_cribl.yml', 'Dockerfile', 'docker-compose.yml', 'cribl-k8s.yaml']
    for f in required_files:
        if not os.path.exists(f):
            print(f"Error: Missing file {f}")
            sys.exit(1)

    # Integrate cert gen if certs not exist
    if not os.path.exists('./certs/server.crt'):
        print("Generating certs...")
        cert_cmd = ["python3", "generate_cert.py", "--key-pass", "defaultpass"]  # Use vault in prod
        subprocess.check_call(cert_cmd)

    try:
        subprocess.check_call(ansible_cmd)
    except subprocess.CalledProcessError as e:
        print(f"Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()