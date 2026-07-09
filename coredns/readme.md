# CoreDNS Deployment Automation

This script deploys a scalable CoreDNS DNS server using Docker, Podman, Kubernetes, or Ansible. Focus: functionality, scalability, error handling, config validation, security.

## Prerequisites
- Python 3.x with `pyyaml` (`pip install pyyaml`).
- For Kubernetes: `kubernetes` Python lib (`pip install kubernetes`) and `kubectl` with kubeconfig.
- Tools: Docker, Podman, kubectl, or ansible-playbook installed based on method.
- Files: `Corefile` (config), `zones/` dir (with .zone files like example).
- Privileges: Run with sudo if binding port 53.

## Usage
```
python deploy.py <method> [--config PATH_TO_COREFILE] [--zones PATH_TO_ZONES] [--scale N] [--namespace NS] [--inventory INV]
```
- **method**: docker, podman, kubernetes, ansible.
- **--scale**: Instances/replicas (default 1).
- **--namespace**: K8S namespace (default 'default').
- **--inventory**: Ansible inventory file.

## Examples
- Docker (local, multi-port): `python deploy.py docker --scale 3`
- Podman: `python deploy.py podman`
- Kubernetes: `python deploy.py kubernetes --scale 5 --namespace dns`
- Ansible: `python deploy.py ansible --inventory hosts.ini`

## Post-Deployment
- Test: `dig @127.0.0.1 example1.com` (adjust port/IP as needed).
- Configure host DNS: For systemd, `sudo cp resolved.conf /etc/systemd/resolved.conf && sudo systemctl restart systemd-resolved` to use local DNS.
- Scaling: Local uses multi-ports; production: Use LB, Swarm (Docker), or K8S.
- Security: Config restricts queries (ACL); add DNSSEC to Corefile if needed.
- Cleanup: Stop/remove containers manually (e.g., `docker rm -f dns-*`).

For issues, check logs (e.g., `docker logs dns-0`).