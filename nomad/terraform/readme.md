# Nomad Cluster Deployment on AWS

This project deploys a multi-region HashiCorp Nomad cluster (v1.9.2) on AWS using Terraform, with Podman, Consul, Vault, and Prometheus/Grafana monitoring. It features mTLS, ACLs, gossip encryption, AWS Secrets Manager with KMS, advanced autoscaling (CPU/memory), AWS Budgets for cost monitoring, Grafana alerts (Nomad job failures, Consul leader changes, Vault seal status), and LocalStack chaos tests. A Python script (`deploy_nomad.py`) automates deployment across `us-east-1` and `us-west-2` with global load balancing via AWS Global Accelerator.

## Prerequisites
- **AWS Account**: IAM permissions for EC2, VPC, ASG, ALB, S3, DynamoDB, Secrets Manager, Lambda, CloudWatch Events, KMS, Global Accelerator, Budgets, SNS.
- **Tools**: Terraform (>=1.0.0), Packer, AWS CLI, Python (>=3.8), `zip`.
- **Python Dependencies**: Install via:
  ```bash
  pip install boto3 requests pyyaml localstack moto[ec2,secretsmanager,lambda,events,budgets]
  ```
- **AWS CLI**: Configured with credentials (`aws configure`).
- **SSH Key Pair**: Private key accessible (e.g., `~/.ssh/id_rsa`).
- **SSL Certificate**: ARN from AWS Certificate Manager.
- **Terraform State**: S3 bucket (`nomad-terraform-state`) and DynamoDB table (`nomad-terraform-locks`).
- **LocalStack**: Optional for testing.

## File Structure
```
nomad-aws-deployment/
├── .github/workflows/deploy.yml         # CI/CD workflow
├── modules/                             # Terraform modules (nomad, consul, vault, monitoring, vpc)
├── packer/nomad-podman-ami.pkr.hcl      # Packer AMI template
├── lambda/grafana_password_rotation.py  # Lambda for Grafana password rotation
├── deploy_nomad.py                      # Deployment script
├── test_deploy_nomad.py                 # Unit/chaos tests
├── config.json                          # Deployment config
├── main.tf                              # Terraform configuration
├── variables.tf                         # Variable definitions
├── variables.tfvars                     # Variable values
├── provider.tf                          # AWS provider
├── fluent-bit.nomad                     # Sample Nomad job
├── *-dashboard.json                     # Grafana dashboards (nomad, consul, vault, fluent-bit)
├── grafana-alerts.yml                   # Grafana alerts
└── README.md
```

## Deployment Steps
1. **Set Up AWS**:
   - Create S3 bucket and DynamoDB table:
     ```bash
     aws s3 mb s3://nomad-terraform-state --region us-east-1
     aws dynamodb create-table --table-name nomad-terraform-locks --attribute-definitions AttributeName=LockID,AttributeType=S --key-schema AttributeName=LockID,KeyType=HASH --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 --region us-east-1
     ```

2. **Set Up LocalStack** (optional, for testing):
   ```bash
   localstack start -d
   export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 AWS_ENDPOINT_URL=http://localhost:4566
   ```

3. **Configure**:
   Edit `config.json`:
   ```json
   {
     "aws_region": "us-east-1",
     "secondary_region": "us-west-2",
     "cluster_name": "nomad-prod",
     "ssl_cert_arn": "arn:aws:acm:us-east-1:xxxxxxxxxxxx:certificate/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
     "ssh_key_path": "~/.ssh/id_rsa",
     "tf_vars_file": "variables.tfvars",
     "project_dir": ".",
     "log_file": "/var/log/deploy_nomad.log",
     "retry_attempts": 5,
     "retry_delay": 5
   }
   ```

4. **Package Lambda**:
   ```bash
   cd lambda
   zip grafana_password_rotation.zip grafana_password_rotation.py
   cd ..
   ```

5. **Run Tests** (includes chaos tests for EC2, Secrets Manager, Lambda, CloudWatch Events):
   ```bash
   python -m unittest test_deploy_nomad.py
   ```

6. **Deploy**:
   ```bash
   python deploy_nomad.py --config config.json
   ```
   The script:
   - Validates tools, credentials, SSH key.
   - Builds Packer AMI with Nomad, Consul, Vault.
   - Deploys multi-region Nomad, Consul, Vault, monitoring with Global Accelerator.
   - Configures KMS-encrypted Secrets Manager, autoscaling, and AWS Budget ($1000/month, 80% alert).
   - Sets up Nomad federation, Consul/Vault ACLs.
   - Deploys Fluent Bit job and Grafana dashboards/alerts.
   - Cleans up on failure.

7. **Verify**:
   ```bash
   export NOMAD_ADDR=https://$(terraform output -raw nomad_global_address):443
   export NOMAD_TOKEN=$(aws secretsmanager get-secret-value --secret-id $(terraform output -raw secrets_arn) --query SecretString --output text | jq -r '.nomad_acl_token')
   nomad node status
   nomad server members
   consul members
   vault status
   nomad job status fluent-bit
   curl -k https://$(terraform output -raw grafana_lb_address_primary)/api/health
   ```
   Access Grafana at `https://<grafana_lb_address_primary>` with username `admin` and password:
   ```bash
   aws secretsmanager get-secret-value --secret-id $(terraform output -raw secrets_arn) --query SecretString --output text | jq -r '.grafana_admin_password'
   ```

8. **Clean Up**:
   ```bash
   terraform destroy -var-file=variables.tfvars
   aws ec2 deregister-image --image-id <ami-id>
   aws ec2 delete-snapshot --snapshot-id <snapshot-id>
   aws secretsmanager delete-secret --secret-id $(terraform output -raw secrets_arn) --force-delete-without-recovery
   aws kms schedule-key-deletion --key-id <kms-key-id> --pending-window-in-days 7
   ```

## Monitoring
- **Grafana Dashboards**: Nomad (jobs, CPU), Consul (services, leader), Vault (status, leases), Fluent Bit (logs).
- **Alerts**:
  - Nomad: Job failures (`nomad_nomad_job_summary_failed > 0`), high CPU (`nomad_nomad_alloc_cpu_usage > 90`).
  - Consul: Leader changes (`consul_leader_changes > 0`).
  - Vault: Sealed status (`vault_sealed == 1`).
- **Cost**: AWS Budget monitors $1000/month limit, alerts via SNS at 80%.

## Autoscaling
- Nomad clients scale up/down at 70%/20% CPU and memory in both regions.

## Security
- mTLS, ACLs, gossip encryption for Nomad, Consul, Vault.
- KMS-encrypted Secrets Manager for tokens/passwords.
- Daily Grafana password rotation via Lambda.

## Troubleshooting
- **Script Errors**: Verify Terraform, Packer, AWS CLI, `boto3`, `pyyaml`. Check AWS credentials and SSH key (`chmod 600 ~/.ssh/id_rsa`).
- **Terraform**: Inspect `terraform.tfstate` or EC2 logs (`/var/log/user-data.log`).
- **Nomad/Consul/Vault**: Check tokens in Secrets Manager, service status (`systemctl status nomad/consul/vault`).
- **Monitoring**: Verify Prometheus (`curl http://<monitoring_ip>:9090`), Grafana (`curl -k https://<grafana_lb_address>/api/health`), logs (`/var/log/prometheus/`, `/var/log/grafana/`).
- **Chaos Tests**: Ensure LocalStack is running (`localstack status`). Check `test_deploy_nomad.py` logs for failure details.
- **Budgets**: Verify SNS topic (`aws sns list-topics`) and budget (`aws budgets describe-budget`).