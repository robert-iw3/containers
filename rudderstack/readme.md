# RudderStack

## Setup
1. Install Python 3.8+, Ansible 2.12+, Jinja2, PyYAML, hvac.
2. Install Docker, Podman, or Kubernetes (`kubectl`, Helm).
3. Set up HashiCorp Vault with a secret at `secret/rudderstack` containing `workspace_token`.
4. Update `inventory/hosts.ini` with host IPs and SSH credentials.
5. Configure `config/config.yaml`:
   ```yaml
   rudder_version: "1.25.0"
   image_registry: "docker.io"
   namespace: "rudderstack"
   replicas: 2
   vault:
     url: "http://vault:8200"
     secret_path: "secret/rudderstack"
   enable_logging: false
   ```
6. For Podman, run:
   ```bash
   podman unshare chown -R $UID:$UID /opt/rudderstack
   ```

## Deploy
```bash
export VAULT_TOKEN=your-vault-token
python deploy_rudderstack.py --config config/config.yaml --platform <docker|podman|kubernetes>
```

## Backup
```bash
ansible-playbook -i inventory/hosts.ini playbooks/backup.yml --extra-vars "platform=<docker|podman>"
```

## Verify
- Check containers/pods: `podman ps` or `kubectl get pods -n rudderstack`.
- Test health: `curl http://<host>:8080/health`.