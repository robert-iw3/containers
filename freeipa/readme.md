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
   Create `.vault_pass.txt` with a secure password:
   ```bash
   echo "your_vault_password" > .vault_pass.txt
   chmod 600 .vault_pass.txt
   ```

4. **Deploy FreeIPA and Web UI**
   ```bash
   python3 deploy_freeipa.py --type docker --config config.yaml
   ```

5. **Access FreeIPA**
   - FreeIPA Web UI: `https://server.ipa.example.test/ipa/modern-ui/`
   - Default credentials: `admin` / `YourSecurePassword`

## Notes
- Update `/etc/hosts` with the VM's IP address after deployment (auto-added by script).
- The Web UI requires Vagrant to set up a VM with FreeIPA.
- Secure `.vault_pass.txt` and do not commit it to version control.
- Monitor logs in `/var/lib/ipa-data` for debugging.
- AlmaLinux 10 is used as the base image for stability.