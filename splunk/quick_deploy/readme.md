# Splunk Enterprise Deployment

This project automates the deployment of a production-ready Splunk Enterprise server with a Universal Forwarder on the same host, supporting bare metal or AWS environments. It includes CIM-compliant data ingestion, security hardening, self-monitoring, and auto-scaling support.

## Prerequisites
- **Bare Metal**: Debian or Red Hat Enterprise Linux with sudo access and 50 GB free disk space.
- **AWS**: AWS CLI configured, S3 bucket (`splunk-terraform-state`), DynamoDB table (`splunk-terraform-locks`), and a Secrets Manager secret (`splunk-secrets-*`) with `ami_id`, `key_name`, `subnet_id`, and `vpc_id`.
- **Tools**:
  ```bash
  pip install ansible boto3 tqdm PyYAML
  ```
  Install Terraform from [terraform.io](https://www.terraform.io/downloads.html).

## Structure

```console
.
├── ansible/
│   ├── roles/
│   │   ├── splunk_enterprise/
│   │   │   ├── tasks/
│   │   │   │   └── main.yml
│   │   │   ├── templates/
│   │   │   │   ├── server.conf.j2
│   │   │   │   ├── web.conf.j2
│   │   │   │   ├── inputs.conf.j2
│   │   │   │   ├── outputs.conf.j2
│   │   │   │   ├── props.conf.j2
│   │   │   │   ├── tags.conf.j2
│   │   │   │   ├── monitoring.conf.j2
│   │   │   │   ├── limits.conf.j2
│   │   │   │   ├── indexes.conf.j2
│   │   │   │   └── thruput.conf.j2
│   │   ├── splunk_forwarder/
│   │   │   ├── tasks/
│   │   │   │   └── main.yml
│   │   │   ├── templates/
│   │   │   │   └── outputs.conf.j2
│   ├── ansible.cfg
│   ├── inventory.yml
│   ├── splunk_deployment.yml
│   └── handlers/
│       └── main.yml
├── terraform/
│   ├── modules/
│   │   ├── splunk_instance/
│   │   │   ├── main.tf
│   │   │   └── variables.tf
│   ├── main.tf
│   └── variables.tf
├── config/
│   └── deployment_config.yaml
├── scripts/
│   ├── check_health.py
│   └── cleanup_deployment.py
├── logs/
│   └── deployment.log
├── deploy_splunk.py
├── setup_deployment.py
└── README.md
```

## Deployment Steps
1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd quick_deploy
   ```

2. **Run Setup Script**:
   ```bash
   python setup_deployment.py
   ```
   - Enter instance size (small, medium, large), indexing volume (GB), and CIDR block.
   - Provide Splunk admin, analyst, and admin passwords (minimum 8 characters, with uppercase and digits).
   - For AWS, enter AWS Secrets Manager secret details.

3. **Deploy Splunk**:
   - Bare metal:
     ```bash
     python deploy_splunk.py --type bare_metal
     ```
   - AWS:
     ```bash
     python deploy_splunk.py --type aws
     ```

4. **Verify Deployment**:
   - The deployment script runs a health check automatically.
   - Access Splunk Web at `https://<server_ip>:8000` (use `localhost` for bare metal).
   - Login with username `admin` and the password provided during setup.

## Configuration
- Edit `config/deployment_config.yaml` to add data sources or adjust settings.
- Monitor performance via Splunk’s Monitoring Console (`_internal` index).

## Troubleshooting
- **Logs**: Check `logs/deployment.log` for errors.
- **Health Check**: Run `python scripts/check_health.py <deployment_type>` to diagnose issues.
- **Cleanup**: Run `python scripts/cleanup_deployment.py <deployment_type>` to remove failed deployments.
- **Common Issues**:
  - **Network Errors**: Ensure internet access to `splunk.com` and AWS services.
  - **AWS Credentials**: Verify AWS CLI configuration with `aws configure`.
  - **Disk Space**: Ensure at least 50 GB free on bare metal servers.

## Notes
- Deployment includes CIM-compliant configurations for Cisco ASA, Palo Alto, Windows Events, and CrowdStrike.
- Backups are stored in `/opt/splunk/etc/system/local_backup` and `/opt/splunkforwarder/etc/system/local_backup`.