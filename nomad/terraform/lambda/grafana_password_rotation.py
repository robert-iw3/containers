import json
import boto3
import string
import random
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def generate_password(length=16):
    """Generate a secure random password."""
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for _ in range(length))

def lambda_handler(event, context):
    """Rotate Grafana admin password and update Secrets Manager."""
    secrets_client = boto3.client('secretsmanager')
    secret_arn = event.get('secret_arn', '')  # Expect ARN from EventBridge or config
    if not secret_arn:
        logger.error("No secret ARN provided")
        raise ValueError("Secret ARN is required")

    try:
        # Retrieve current secret
        current_secret = secrets_client.get_secret_value(SecretId=secret_arn)
        secret_dict = json.loads(current_secret['SecretString'])

        # Generate new password
        new_password = generate_password()
        secret_dict['grafana_admin_password'] = new_password

        # Update secret
        secrets_client.put_secret_value(
            SecretId=secret_arn,
            SecretString=json.dumps(secret_dict)
        )
        logger.info(f"Successfully rotated Grafana admin password for secret {secret_arn}")
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Password rotated successfully'})
        }
    except Exception as e:
        logger.error(f"Failed to rotate password: {str(e)}")
        raise