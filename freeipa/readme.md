# FreeIPA

https://www.freeipa.org

This guide provides the minimal steps to deploy FreeIPA with its Web UI using Docker and AlmaLinux 10.

## Prerequisites
- Docker installed
- Vagrant and vagrant-libvirt installed
- nvm (Node Version Manager) installed
- Python 3.8+
- Git
- Root access on the deployment host
- Minimum 4GB RAM and 2 CPU cores

## Deployment Steps

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd <repository-dir>
   ```

2. **Configure Settings**
   Edit `config.yaml` to set your domain, realm, and secure passwords:
   ```yaml
   domain: example.test
   realm: EXAMPLE.TEST
   admin_password: YourSecurePassword
   dm_password: YourSecurePassword
   data_dir: /var/lib/ipa-data
   deploy_webui: true
   ```

3. **Secure Vault Password**
   Create `.vault_pass.txt` locally with a secure password — it is
   gitignored and must never be committed (any value that ever landed in
   git history is compromised and has to be rotated):
   ```bash
   openssl rand -base64 24 > .vault_pass.txt
   chmod 600 .vault_pass.txt
   ```
   Ansible-managed secrets (`playbook_sensitive_data.yml`) are written by
   the deploy script and are gitignored as well; encrypt them with
   `ansible-vault encrypt --vault-password-file .vault_pass.txt` if they
   need to persist.

4. **Deploy FreeIPA and Web UI**
   ```bash
   python3 deploy_freeipa.py --type docker --config config.yaml
   ```

5. **Access FreeIPA**
   - FreeIPA Web UI: `https://server.ipa.example.test/ipa/modern-ui/`
   - Default credentials: `admin` / `YourSecurePassword`

## Smoke test / UAT

```bash
./uat/run-uat.sh        # single-server install on https://ipa.uat.test:8453 (10+ min)
./uat/run-uat.sh --down # tear down
```
The UAT installs a full FreeIPA server (LDAPS published on 8636),
provisions a demo user, then proves the directory-integration path an
application uses: an **LDAPS (TLS) simple bind + search** against the
directory. The script prints the Web UI URL, admin/demo credentials, and
the LDAPS endpoint. Add `127.0.0.1 ipa.uat.test` to your hosts file for
browser access.

## Notes
- Update `/etc/hosts` with the VM's IP address after deployment (auto-added by script).
- The Web UI requires Vagrant to set up a VM with FreeIPA.
- Secure `.vault_pass.txt` and do not commit it to version control.
- Monitor logs in `/var/lib/ipa-data` for debugging.
- AlmaLinux 10 is used as the base image for stability.
## Deploy with Ansible

Single-server (container) deploy from `config.yaml`:

```bash
cd freeipa/ansible
ansible-playbook -i inventory.ini deploy.yml
```

Multi-host IPA cluster (server + replicas + clients) via the
`freeipa.ansible_freeipa` collection:

```bash
cd freeipa/playbooks
ansible-galaxy collection install -r requirements.yml
ansible-playbook -i ../inventory/hosts install-cluster.yml
```
Validate playbook syntax with ansible-lint (containerised, no host install
needed) from the repo root:

```bash
ci/ansible-lint.sh
```
