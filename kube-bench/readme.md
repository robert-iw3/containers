# Kube-bench Orchestration

Run kube-bench audits across Kubernetes clusters using Docker, Podman, or Kubernetes deployments. Generates reports in txt, json, xml, and html formats, with an aggregated summary.

## Prerequisites
- Python 3.8+
- Podman or Docker
- Ansible 2.9+
- kubectl (for Kubernetes deployment)
- Valid kubeconfig file
- Optional: SELinux (`selinux-policy`), AppArmor (`apparmor-profiles`), kube-bench binary signature

## Setup
1. **Clone the repository**:
   ```sh
   git clone <repository-url>
   cd kube-bench-orchestrator
   ```

2. **Build the kube-bench image**:
   ```sh
   podman build -t kube-bench:latest -f docker/Dockerfile .
   # or for FIPS-compliant version
   podman build -t kube-bench:latest -f docker/Dockerfile.ubi9-fips .
   ```

3. **Configure SELinux/AppArmor** (optional):
   ```sh
   # SELinux
   checkmodule -M -m -o docker/selinux/kube_bench.mod docker/selinux/kube_bench.te
   semodule_package -o docker/selinux/kube_bench.pp -m docker/selinux/kube_bench.mod
   semodule -i docker/selinux/kube_bench.pp
   # AppArmor
   apparmor_parser -a docker/apparmor/kube_bench_profile
   ```

4. **Edit `config/config.yaml`**:
   ```yaml
   endpoint_configs:
     - endpoint: cluster1.example.com
       timeout: 300
     - endpoint: cluster2.example.com
       timeout: 600
   reports_dir: /tmp/kube-bench-reports
   log_file: /var/log/kube_bench_scan.log
   deployment_type: podman
   max_concurrent_scans: 2
   report_formats:
     - txt
     - json
     - xml
     - html
   timeout: 300
   kubectl_path: /usr/local/bin/kubectl
   kubeconfig_path: ~/.kube/config
   extra_args:
     - --benchmark
     - cis-1.8
   ```

5. **Set up kubeconfig**:
   - Place at `~/.kube/config` or update `kubeconfig_path` in `config.yaml`.

## Run Audit
- **Using Ansible**:
  1. Create `inventory.yml`:
     ```yaml
     all:
       hosts:
         localhost:
           ansible_connection: local
     ```
  2. Run playbook:
     ```sh
     ansible-playbook -i inventory.yml templates/kube_bench_playbook.yml.j2
     ```

- **Direct Execution**:
   ```sh
   export KUBE_BENCH_CONFIG=config/config.yaml
   export KUBE_BENCH_SIGNATURE=<hmac-sha256-signature>  # optional
   python3 kube_bench_orchestrator.py
   ```

## Output
- **Reports**: In `reports_dir` (`/tmp/kube-bench-reports` by default) as txt, json, xml, html.
- **Aggregate Report**: JSON summary at `kube_bench_aggregate_<timestamp>.json`.
- **Logs**: At `log_file` (`/var/log/kube_bench_scan.log` by default).

## Troubleshooting
- **Config errors**: Check logs for YAML issues.
- **Permissions**: Ensure access to Docker/Podman, kubectl, and directories.
- **Timeouts**: Increase `timeout` in `config.yaml`.
- **Signature issues**: Verify HMAC-SHA256 signature.
- **SELinux/AppArmor**: Check profiles with `semanage module -l` or `aa-status`.