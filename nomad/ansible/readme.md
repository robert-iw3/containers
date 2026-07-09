# Nomad Deployment with Ansible

This Ansible role deploys a secure, production-ready minmal HashiCorp Nomad cluster with Podman as the primary container runtime, supporting both server and client configurations on Debian or Red Hat-based systems. It includes TLS, ACLs, Vault integration, and system optimizations for robust operation.

## Prerequisites

- Ansible 2.9 or higher
- Target hosts running Debian/Ubuntu or RHEL/CentOS
- SSH access to target hosts
- Ansible Vault for secure token storage (optional for Vault integration)

## Structure

```console
ansible/
├── roles/
│   └── nomad/
│       ├── defaults/main.yml             # Default variables for the role
│       ├── handlers/main.yml             # Restart Nomad handler
│       ├── tasks/
│       │   ├── main.yml                  # Install, configure, bootstrap ACLs, validate
│       │   ├── prepare_host.yml          # Podman, kernel/firewall, ulimits, subuid/subgid
│       │   ├── certificates.yml          # Shared-CA mTLS generation and distribution
│       │   └── vault.yml                 # Vault client install/config
│       └── templates/
│           ├── nomad.hcl.j2              # Main agent configuration
│           ├── nomad.service.j2          # Systemd unit
│           ├── nomad-acl.hcl.j2          # ACL enablement stanza
│           ├── nomad-acl-policy.hcl.j2   # Default ACL policy
│           ├── nomad-sentinel.hcl.j2     # Sentinel policy
│           ├── nomad-vault-policy.hcl.j2 # Vault policy for Nomad's own token
│           └── logrotate.nomad.j2        # Log rotation config
├── playbooks/nomad.yml                   # Applies the role to nomad_servers/nomad_clients
├── .gitlab-ci.yml                        # ansible-lint + syntax-check pipeline
└── readme.md
```

## Usage Steps

1. **Supply required secrets (no defaults are shipped)**:
   - `nomad_gossip_key` is mandatory whenever `nomad_gossip_encryption_enabled` (default `true`); generate one with `nomad operator gossip keyring generate` or `openssl rand -base64 32` and every server must use the same value.
   - `nomad_vault_token` is mandatory whenever `nomad_vault_enabled` is `true`.
   - Store both with ansible-vault:
     ```bash
     ansible-vault encrypt_string 'value' --name nomad_gossip_key
     ```

2. **Set Up Inventory**:
   - Create an Ansible inventory file (e.g., `inventory.yml`):
     ```yaml
     all:
       children:
         nomad_servers:
           hosts:
             server1.example.com:
             server2.example.com:
             server3.example.com:
         nomad_clients:
           hosts:
             client1.example.com:
             client2.example.com:
     ```

3. **Run the Playbook**:
   - Deploy the Nomad cluster:
     ```bash
     ansible-playbook playbooks/nomad.yml --vault-password-file vault_pass.txt
     ```

4. **Verify Deployment**:
   - Check Nomad service status:
     ```bash
     systemctl status nomad
     ```
   - Access the Nomad UI at `https://<server-ip>:4646`.
   - Verify cluster status:
     ```bash
     nomad node status
     nomad server members
     ```

5. **Validate Podman Integration**:
   - Ensure Podman is detected:
     ```bash
     nomad node status | grep podman
     ```

## Configuration Options

Customize the deployment by overriding variables in `roles/nomad/defaults/main.yml`:

- `nomad_version`: Nomad version (default: `2.0.3`)
- `nomad_server_enabled`: Enable server mode (default: `false`)
- `nomad_client_enabled`: Enable client mode (default: `false`)
- `nomad_bootstrap_expect`: Number of expected servers for bootstrap (default: `3`)
- `nomad_tls_enabled`: Enable TLS (default: `true`)
- `nomad_tls_generate`: Generate self-signed TLS certificates (default: `true`)
- `nomad_acl_enabled`: Enable ACLs (default: `true`)
- `nomad_vault_enabled`: Enable Vault integration (default: `false`)
- `nomad_podman_enabled`: Enable Podman task driver (default: `true`)
- `nomad_consul_enabled`: Enable Consul integration (default: `false`)
- `nomad_telemetry_enabled`: Enable telemetry (default: `true`)

## Security Notes

- **TLS**: Enabled by default with self-signed certificates. For production, replace with CA-issued certificates.
- **ACLs**: Enabled by default to restrict access to Nomad resources.
- **Vault**: Secure token storage using Ansible Vault.
- **Firewall**: Configured to allow only necessary ports (4646-4648).
- **Rootless Podman**: Runs containers as the `nomad` user for enhanced security.

## CI/CD Integration

- Store the role and playbook in a Git repository.
- Configure a GitLab runner with `vault_pass.txt` as a CI/CD secret.
- Run the pipeline using `.gitlab-ci.yml` to automate deployment and validation.

## Troubleshooting

- **Podman Not Detected**: Ensure `podman` is installed and the `nomad` user has proper `subuid`/`subgid` mappings.
- **TLS Errors**: Verify certificate files in `/etc/nomad.d/` and `NOMAD_CACERT` environment variable.
- **ACL Issues**: Run `nomad acl bootstrap` to generate a management token if needed.

## Monitoring

- Access Prometheus metrics at `/v1/metrics` on port 4646.
- Monitor cluster health via the Nomad UI or CLI commands.