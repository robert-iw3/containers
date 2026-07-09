# hyperdx

[![hyperdx](https://img.youtube.com/vi/JQd2Mol6kqA/0.jpg)](https://www.youtube.com/watch?v=JQd2Mol6kqA)

## Quick Start

1. Create directory `hyperdx-deploy` with the following structure:
   ```
   hyperdx-deploy/
   ├── config.yaml                  # Main config
   ├── .env.j2                      # Env template
   ├── docker-compose.yml.j2        # Docker Compose template
   ├── docker/
   │   ├── clickhouse/
   │   │   └── local/
   │   │       ├── config.xml       # ClickHouse config
   │   │       └── users.xml        # ClickHouse users
   │   └── nginx/
   │       ├── nginx.conf.j2        # Nginx template
   │       └── ssl/                 # Generated certs
   ├── helm/
   │   └── values.yaml.j2           # Helm values template
   ├── deploy.py                    # Python orchestration
   ├── deploy_docker.yml            # Ansible Docker playbook
   ├── deploy_podman.yml            # Ansible Podman playbook
   ├── deploy_kubernetes.yml        # Ansible Kubernetes playbook
   ├── certs.sh                     # Cert generation script
   ├── ca.cnf                       # OpenSSL CA config
   ├── csr.cnf                      # OpenSSL CSR config
   ├── backup.sh                    # Volume backup script
   ├── renew_certs.sh               # Cert renewal script
   ├── inventory.yml                # Ansible inventory
   ```
2. Install dependencies:
   ```bash
   pip install pyyaml ansible
   ansible-galaxy collection install community.docker kubernetes.core containers.podman
   sudo apt install certbot  # For letsencrypt
   ```
3. Edit `config.yaml`:
   - Set `deployment_type` (docker, podman, kubernetes).
   - Set `domain` (e.g., example.com) and `cert_type` (self-signed, letsencrypt, csr).
   - Set `email` for Let's Encrypt.
   - Set `use_all_in_one: true` for local single-container mode (Docker/Podman only).
4. Run deployment:
   ```bash
   python deploy.py
   ```
5. Access HyperDX at `https://<domain>:8080` (or `https://localhost:8080` for local).

## Notes
- For Kubernetes, ensure `kubectl` and `helm` are configured.
- For Let's Encrypt, ensure port 80 is open.
- Use `--type <type>` with `deploy.py` to override deployment type.
- Run `backup.sh` for volume backups; schedule `renew_certs.sh` for cert renewal.
- Check logs in `.volumes/` (Docker/Podman) or Kubernetes pods for issues.