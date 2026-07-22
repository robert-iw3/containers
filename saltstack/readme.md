# SaltStack

## SSO deployment (`sso/`)

`sso/docker-compose.yml` runs a Salt 3008 master + salt-api and a minion
behind traefik TLS with a tinyauth single sign-on gate. The image is built
from [`sso/Dockerfile`](sso/Dockerfile) (Salt 3008 from the Salt Project
package repo); one image serves every role via `SALT_ROLE`. tinyauth gates
browser access to salt-api, while programmatic callers — the `/login` token
exchange and any request carrying a salt auth token — bypass the gate and
authenticate with salt's own `sharedsecret` eauth. The ZeroMQ minion
transport (`4505`/`4506`) is published directly, entirely outside the gate.

tinyauth verifies local users by default, or any OIDC provider via
`sso/tinyauth.env` (see
[`../ci/sso/tinyauth-oidc.env.example`](../ci/sso/tinyauth-oidc.env.example)).

```sh
cd uat && ./run-uat.sh          # builds the 3008 image; TLS + SSO + eauth + minion ping
cd uat && ./run-uat.sh --down   # tear down
cd ansible && ansible-playbook -i inventory.ini deploy.yml   # deploy (builds the image)
```

The shared pattern is documented in [`../ci/sso/README.md`](../ci/sso/README.md).

## Setup
1. Install Python 3.8+, Ansible 2.12+, Jinja2, PyYAML, hvac.
2. Install Docker, Podman, or Kubernetes (`kubectl`).
3. Set up HashiCorp Vault with a secret at `secret/saltstack` containing `master_key`.
4. Update `inventory/hosts.ini` with host IPs and SSH credentials.
5. Configure `config/config.yaml`:
   ```yaml
   salt_version: "3006.8"
   image_registry: "docker.io"
   namespace: "saltstack"
   replicas: 2
   minion_count: 2
   vault:
     url: "http://vault:8200"
     secret_path: "secret/saltstack"
   enable_logging: false
   ```
6. For Podman, run:
   ```bash
   podman unshare chown -R $UID:$UID /opt/saltstack
   ```

## Deploy
```bash
export VAULT_TOKEN=your-vault-token
python deploy_saltstack.py --config config/config.yaml --platform <docker|podman|kubernetes>
```

## Backup
```bash
ansible-playbook -i inventory/hosts.ini playbooks/backup.yml --extra-vars "platform=<docker|podman>"
```

## Verify
- Check containers/pods: `podman ps` or `kubectl get pods -n saltstack`.
- Test Salt: `podman exec salt-master salt '*' test.ping` or `kubectl exec -n saltstack <pod> -- salt '*' test.ping`.