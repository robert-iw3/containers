import unittest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import deploy_nomad
import boto3
from moto import mock_ec2, mock_secretsmanager, mock_lambda, mock_events, mock_budgets
import botocore.exceptions
import subprocess

class TestNomadDeployer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = {
            "aws_region": "us-east-1",
            "secondary_region": "us-west-2",
            "cluster_name": "test-nomad",
            "ssl_cert_arn": "arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789012",
            "ssh_key_path": str(self.temp_dir / "id_rsa"),
            "tf_vars_file": str(self.temp_dir / "variables.tfvars"),
            "project_dir": str(self.temp_dir),
            "log_file": str(self.temp_dir / "deploy_nomad.log"),
            "retry_attempts": 3,
            "retry_delay": 1,
            "grafana_admin_password": "admin123"
        }
        with open(self.temp_dir / "config.json", "w") as f:
            json.dump(self.config, f)
        with open(self.config["ssh_key_path"], "w") as f:
            f.write("mock_ssh_key")
        os.makedirs(self.temp_dir / "packer", exist_ok=True)
        os.makedirs(self.temp_dir / "lambda", exist_ok=True)
        with open(self.temp_dir / "lambda/grafana_password_rotation.zip", "wb") as f:
            f.write(b"mock_lambda_zip")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    @patch("deploy_nomad.shutil.which")
    @patch("deploy_nomad.boto3.client")
    def test_check_prerequisites_success(self, mock_boto_client, mock_which):
        mock_which.side_effect = lambda x: "/usr/bin/" + x
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        deployer = deploy_nomad.NomadDeployer(self.config)
        deployer.check_prerequisites()
        mock_boto_client.assert_called_with("ec2", region_name="us-east-1")
        mock_ec2_client.describe_regions.assert_called_with(regions=["us-east-1", "us-west-2"])
        mock_which.assert_any_call("terraform")
        mock_which.assert_any_call("packer")
        mock_which.assert_any_call("aws")

    @patch("deploy_nomad.shutil.which")
    def test_check_prerequisites_missing_tool(self, mock_which):
        mock_which.side_effect = [None, "/usr/bin/packer", "/usr/bin/aws"]
        deployer = deploy_nomad.NomadDeployer(self.config)
        with self.assertRaisesRegex(RuntimeError, "terraform is not installed"):
            deployer.check_prerequisites()

    @patch("deploy_nomad.subprocess.run")
    def test_run_command_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="success", stderr="")
        deployer = deploy_nomad.NomadDeployer(self.config)
        result = deployer.run_command(["echo", "test"])
        mock_run.assert_called_with(["echo", "test"], cwd=self.temp_dir, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, "success")

    @patch("deploy_nomad.subprocess.run")
    def test_run_command_retry(self, mock_run):
        mock_run.side_effect = [subprocess.CalledProcessError(1, ["test"], stderr="fail"), MagicMock(stdout="success", stderr="")]
        deployer = deploy_nomad.NomadDeployer(self.config)
        result = deployer.run_command(["test"], retries=2)
        self.assertEqual(mock_run.call_count, 2)
        self.assertEqual(result.stdout, "success")

    @patch("deploy_nomad.subprocess.run")
    def test_build_packer_ami(self, mock_run):
        mock_run.return_value = MagicMock(stdout="AMIs were created:\nami-1234567890abcdef0")
        deployer = deploy_nomad.NomadDeployer(self.config)
        ami_id = deployer.build_packer_ami()
        self.assertEqual(ami_id, "ami-1234567890abcdef0")
        mock_run.assert_called_with(["packer", "build", "nomad-podman-ami.pkr.hcl"], cwd=self.temp_dir / "packer", capture_output=True, text=True, check=True)

    def test_update_tf_vars(self):
        deployer = deploy_nomad.NomadDeployer(self.config)
        deployer.ami_id = "ami-1234567890abcdef0"
        deployer.update_tf_vars()
        with open(self.config["tf_vars_file"]) as f:
            content = f.read()
        self.assertIn('nomad_ami_id        = "ami-1234567890abcdef0"', content)
        self.assertIn('cluster_name        = "test-nomad"', content)
        self.assertIn('secondary_region    = "us-west-2"', content)

    @mock_ec2
    @mock_secretsmanager
    @mock_lambda
    @mock_events
    @mock_budgets
    @patch("deploy_nomad.subprocess.run")
    def test_integration_deploy_ami_lambda_budget(self, mock_run):
        # Mock AWS services with moto
        ec2_client = boto3.client("ec2", region_name="us-east-1")
        secrets_client = boto3.client("secretsmanager", region_name="us-east-1")
        lambda_client = boto3.client("lambda", region_name="us-east-1")
        events_client = boto3.client("events", region_name="us-east-1")
        budgets_client = boto3.client("budgets", region_name="us-east-1")

        # Create mock secret
        secrets_client.create_secret(
            Name="test-nomad-secrets",
            SecretString=json.dumps({
                "nomad_acl_token": "12345678-1234-1234-1234-123456789012",
                "nomad_gossip_key": "87654321-4321-4321-4321-210987654321",
                "vault_token": "abcdef12-3456-7890-abcd-ef1234567890",
                "grafana_admin_password": "admin123"
            })
        )

        # Create mock Lambda function
        lambda_client.create_function(
            FunctionName="test-nomad-grafana-password-rotation",
            Runtime="python3.8",
            Role="arn:aws:iam::123456789012:role/test-nomad-grafana-password-rotation",
            Handler="grafana_password_rotation.lambda_handler",
            Code={"ZipFile": (self.temp_dir / "lambda/grafana_password_rotation.zip").read_bytes()}
        )

        # Create mock CloudWatch Events rule
        events_client.put_rule(
            Name="test-nomad-grafana-password-rotation-schedule",
            ScheduleExpression="rate(1 day)"
        )

        # Create mock budget
        budgets_client.create_budget(
            AccountId="123456789012",
            Budget={
                "BudgetName": "test-nomad-budget",
                "BudgetLimit": {"Amount": "1000", "Unit": "USD"},
                "CostTypes": {"IncludeTax": True, "IncludeSubscription": True},
                "TimeUnit": "MONTHLY",
                "TimePeriod": {"Start": 1577836800, "End": 1893456000}
            },
            NotificationsWithSubscribers=[{
                "Notification": {
                    "NotificationType": "ACTUAL",
                    "ComparisonOperator": "GREATER_THAN",
                    "Threshold": 80
                },
                "Subscribers": []
            }]
        )

        # Mock Packer and Terraform commands
        mock_run.side_effect = [
            MagicMock(stdout="AMIs were created:\nami-1234567890abcdef0"),  # Packer build
            MagicMock(stdout=""),  # terraform init
            MagicMock(stdout=""),  # terraform apply
            MagicMock(stdout=json.dumps({
                "nomad_global_address": {"value": "test-global.example.com"},
                "nomad_lb_address_primary": {"value": "test-lb-primary.example.com"},
                "nomad_lb_address_secondary": {"value": "test-lb-secondary.example.com"},
                "secrets_arn": {"value": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-nomad-secrets"},
                "nomad_server_ips_primary": {"value": ["10.0.0.1"]},
                "nomad_server_ips_secondary": {"value": ["10.1.0.1"]},
                "consul_instance_ips_primary": {"value": ["10.0.0.2"]},
                "vault_instance_ips_primary": {"value": ["10.0.0.3"]},
                "grafana_lb_address_primary": {"value": "grafana-primary.example.com"},
                "budget_notifications_topic_arn": {"value": "arn:aws:sns:us-east-1:123456789012:test-nomad-budget-notifications"}
            }))  # terraform output
        ]

        deployer = deploy_nomad.NomadDeployer(self.config)
        deployer.build_packer_ami()
        deployer.update_tf_vars()
        deployer.create_budget()
        deployer.terraform_init()
        deployer.terraform_apply()
        outputs = deployer.get_terraform_outputs()

        self.assertEqual(outputs["nomad_global_address"]["value"], "test-global.example.com")
        self.assertEqual(outputs["secrets_arn"]["value"], "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-nomad-secrets")
        self.assertEqual(deployer.ami_id, "ami-1234567890abcdef0")

        # Verify Lambda, CloudWatch Events, and Budget
        lambda_response = lambda_client.get_function(FunctionName="test-nomad-grafana-password-rotation")
        self.assertEqual(lambda_response["Configuration"]["Handler"], "grafana_password_rotation.lambda_handler")
        rule_response = events_client.describe_rule(Name="test-nomad-grafana-password-rotation-schedule")
        self.assertEqual(rule_response["ScheduleExpression"], "rate(1 day)")
        budget_response = budgets_client.describe_budget(AccountId="123456789012", BudgetName="test-nomad-budget")
        self.assertEqual(budget_response["Budget"]["BudgetLimit"]["Amount"], "1000")

    @mock_ec2
    @mock_secretsmanager
    @patch("deploy_nomad.subprocess.run")
    def test_chaos_ec2_termination(self, mock_run):
        ec2_client = boto3.client("ec2", region_name="us-east-1")
        secrets_client = boto3.client("secretsmanager", region_name="us-east-1")

        # Create mock secret
        secrets_client.create_secret(
            Name="test-nomad-secrets",
            SecretString=json.dumps({
                "nomad_acl_token": "12345678-1234-1234-1234-123456789012",
                "nomad_gossip_key": "87654321-4321-4321-4321-210987654321",
                "vault_token": "abcdef12-3456-7890-abcd-ef1234567890",
                "grafana_admin_password": "admin123"
            })
        )

        # Create mock image and instance
        image_response = ec2_client.create_image(InstanceId="i-1234567890abcdef0", Name="test-ami")
        instance_response = ec2_client.run_instances(ImageId=image_response["ImageId"], MinCount=1, MaxCount=1)
        instance_id = instance_response["Instances"][0]["InstanceId"]

        # Mock Packer and Terraform
        mock_run.side_effect = [
            MagicMock(stdout="AMIs were created:\n" + image_response["ImageId"]),  # Packer build
            MagicMock(stdout=""),  # terraform init
            MagicMock(stdout=""),  # terraform apply
            MagicMock(stdout=json.dumps({
                "nomad_global_address": {"value": "test-global.example.com"},
                "secrets_arn": {"value": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-nomad-secrets"}
            }))  # terraform output
        ]

        deployer = deploy_nomad.NomadDeployer(self.config)
        deployer.build_packer_ami()
        deployer.update_tf_vars()
        deployer.terraform_init()
        deployer.terraform_apply()

        # Simulate EC2 instance termination
        ec2_client.terminate_instances(InstanceIds=[instance_id])

        # Verify cleanup
        deployer.cleanup()
        with self.assertRaises(botocore.exceptions.ClientError):
            ec2_client.describe_instances(InstanceIds=[instance_id])

    @mock_secretsmanager
    @patch("deploy_nomad.subprocess.run")
    def test_chaos_secrets_manager_failure(self, mock_run):
        secrets_client = boto3.client("secretsmanager", region_name="us-east-1")

        # Mock Packer and Terraform
        mock_run.side_effect = [
            MagicMock(stdout="AMIs were created:\nami-1234567890abcdef0"),  # Packer build
            MagicMock(stdout=""),  # terraform init
            MagicMock(stdout=""),  # terraform apply
            MagicMock(stdout=json.dumps({
                "nomad_global_address": {"value": "test-global.example.com"},
                "secrets_arn": {"value": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-nomad-secrets"}
            }))  # terraform output
        ]

        deployer = deploy_nomad.NomadDeployer(self.config)
        deployer.build_packer_ami()
        deployer.update_tf_vars()
        deployer.terraform_init()
        deployer.terraform_apply()

        # Simulate Secrets Manager failure
        with patch.object(deployer.secrets_client, "get_secret_value", side_effect=botocore.exceptions.ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Secret not found"}}, "get_secret_value"
        )):
            with self.assertRaises(botocore.exceptions.ClientError):
                deployer.retrieve_secrets("arn:aws:secretsmanager:us-east-1:123456789012:secret:test-nomad-secrets")

    @mock_lambda
    @patch("deploy_nomad.subprocess.run")
    def test_chaos_lambda_timeout(self, mock_run):
        lambda_client = boto3.client("lambda", region_name="us-east-1")

        # Create mock Lambda function
        lambda_client.create_function(
            FunctionName="test-nomad-grafana-password-rotation",
            Runtime="python3.8",
            Role="arn:aws:iam::123456789012:role/test-nomad-grafana-password-rotation",
            Handler="grafana_password_rotation.lambda_handler",
            Code={"ZipFile": (self.temp_dir / "lambda/grafana_password_rotation.zip").read_bytes()},
            Timeout=1
        )

        # Mock Packer and Terraform
        mock_run.side_effect = [
            MagicMock(stdout="AMIs were created:\nami-1234567890abcdef0"),  # Packer build
            MagicMock(stdout=""),  # terraform init
            MagicMock(stdout=""),  # terraform apply
            MagicMock(stdout=json.dumps({
                "nomad_global_address": {"value": "test-global.example.com"},
                "secrets_arn": {"value": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-nomad-secrets"}
            }))  # terraform output
        ]

        deployer = deploy_nomad.NomadDeployer(self.config)
        deployer.build_packer_ami()
        deployer.terraform_init()
        deployer.terraform_apply()

        # Simulate Lambda timeout
        with patch.object(lambda_client, "invoke", side_effect=botocore.exceptions.ClientError(
            {"Error": {"Code": "RequestTimeout", "Message": "Function timed out"}}, "invoke"
        )):
            with self.assertRaises(botocore.exceptions.ClientError):
                lambda_client.invoke(FunctionName="test-nomad-grafana-password-rotation")

    @mock_events
    @patch("deploy_nomad.subprocess.run")
    def test_chaos_events_failure(self, mock_run):
        events_client = boto3.client("events", region_name="us-east-1")

        # Create mock CloudWatch Events rule
        events_client.put_rule(
            Name="test-nomad-grafana-password-rotation-schedule",
            ScheduleExpression="rate(1 day)"
        )

        # Mock Packer and Terraform
        mock_run.side_effect = [
            MagicMock(stdout="AMIs were created:\nami-1234567890abcdef0"),  # Packer build
            MagicMock(stdout=""),  # terraform init
            MagicMock(stdout=""),  # terraform apply
            MagicMock(stdout=json.dumps({
                "nomad_global_address": {"value": "test-global.example.com"},
                "secrets_arn": {"value": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-nomad-secrets"}
            }))  # terraform output
        ]

        deployer = deploy_nomad.NomadDeployer(self.config)
        deployer.build_packer_ami()
        deployer.terraform_init()
        deployer.terraform_apply()

        # Simulate CloudWatch Events failure
        with patch.object(events_client, "put_targets", side_effect=botocore.exceptions.ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid target"}}, "put_targets"
        )):
            with self.assertRaises(botocore.exceptions.ClientError):
                events_client.put_targets(
                    Rule="test-nomad-grafana-password-rotation-schedule",
                    Targets=[{"Id": "1", "Arn": "arn:aws:lambda:us-east-1:123456789012:function:test-nomad-grafana-password-rotation"}]
                )

if __name__ == "__main__":
    unittest.main()