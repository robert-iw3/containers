# Defguard Deployment Instructions

This document provides step-by-step instructions to deploy the Defguard infrastructure (Core, Proxy, and Gateway) on AWS using Terraform and a unified Python deployment script.

## File Structure
- `./core/`: Terraform files and setup script for Defguard Core.
- `./gateway/`: Terraform files and setup script for Defguard Gateway.
- `./proxy/`: Terraform files and setup script for Defguard Proxy.
- `./main.tf.example`, `secrets.tfvars.example`, `deploy.py`, `requirements.txt`, `README.md`: Root configuration and deployment files.

## Prerequisites
- Terraform >= 1.5.0
- AWS CLI configured with appropriate credentials
- Python 3.8+ (for setup and deployment scripts)
- An AWS account with permissions to create:
  - EC2 instances
  - VPCs
  - RDS databases
  - Secrets Manager secrets
  - IAM roles/policies

## Deployment Instructions

Follow these steps to deploy the Defguard infrastructure:

1. **Clone the Repository**
   Clone the repository and navigate to the project directory:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Create a `.gitignore` File**
   Create a `.gitignore` file to exclude sensitive and temporary files:
   ```bash
   echo -e "secrets.tfvars\n*.tfstate\n*.tfstate.backup\n.terraform/\n.terraform.lock.hcl" > .gitignore
   ```

3. **Create a `secrets.tfvars` File**
   Copy the example secrets file and fill in your AWS credentials, database password, and admin password:
   ```bash
   cp secrets.tfvars.example secrets.tfvars
   ```
   Edit `secrets.tfvars` to include:
   - `aws_access_key`: Your AWS access key
   - `aws_secret_key`: Your AWS secret key
   - `db_password`: Database password for Defguard Core
   - `default_admin_password`: Default admin password for Defguard Core

4. **Install Python Dependencies**
   Install the required Python dependencies for the deployment and setup scripts:
   ```bash
   pip install -r requirements.txt
   pip install -r core/requirements.txt
   pip install -r gateway/requirements.txt
   pip install -r proxy/requirements.txt
   ```

5. **Create IAM Role**
   Create an IAM role for EC2 instances with the following policy to allow access to AWS Secrets Manager:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": "secretsmanager:GetSecretValue",
         "Resource": "*"
       }
     ]
   }
   ```
   Attach this role to the EC2 instances for Core, Gateway, and Proxy.

6. **Deploy the Infrastructure**
   Deploy the infrastructure using either Terraform directly or the unified deployment script:
   - **Option 1: Terraform Directly**
     ```bash
     terraform init
     terraform apply -var-file=secrets.tfvars
     ```
   - **Option 2: Unified Deployment Script**
     ```bash
     python deploy.py --secrets-file secrets.tfvars
     ```
   The `deploy.py` script applies the Terraform configuration, waits for instances to be running, and verifies service status.

7. **Verify Deployment**
   - Check the Terraform outputs for instance IDs, public/private IP addresses, and the Secrets Manager ARN:
     ```bash
     terraform output
     ```
   - Access the Defguard Core web UI at `https://defguard.example.com:8000`.
   - Log in with the `default_admin_password` from `secrets.tfvars`.
   - Verify Gateway and Proxy connectivity via the Core UI or check logs at `/var/log/defguard.log` on each instance.

8. **Cleanup**
   To destroy the infrastructure:
   - **Using Terraform**:
     ```bash
     terraform destroy -var-file=secrets.tfvars
     ```
   - **Using the Deployment Script**:
     ```bash
     python deploy.py --secrets-file secrets.tfvars --destroy
     ```

## Security Best Practices
- **Secrets Management**: Store sensitive data in AWS Secrets Manager. Do not hardcode secrets in Terraform files.
- **Network Security**: Security groups restrict access to necessary ports. Consider replacing `0.0.0.0/0` with specific CIDR blocks for Proxy and Gateway ingress.
- **File Permissions**: Setup scripts set secure permissions (0600) on configuration files.
- **Input Validation**: Scripts validate inputs to prevent injection attacks.
- **Version Control**: Ensure `secrets.tfvars` is not committed to version control.

## Troubleshooting
- Check logs at `/var/log/defguard.log` on EC2 instances for setup errors.
- Verify the IAM role has access to Secrets Manager.
- Ensure security group rules allow necessary traffic (e.g., Core HTTP port 8000, Proxy HTTP port 8000, Gateway UDP port 51820).
- If using `deploy.py`, review console output for detailed error messages.
- Confirm that the AWS region in `main.tf.example` matches your AWS CLI configuration.