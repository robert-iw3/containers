## Authentication and Configuration — IAM Identity Center (SSO) Users

Requirements:

AWS Organization with multiple AWS Accounts

IAM Identity Center Setup with Access portal url (https://my-organization.awsapps.com/start#)

IAM Identity Center Group & User

IAM Identity Permission Set named “Terraform“

Assign the IAM Identity Center PowerUserAccess Permission Set named “Terraform“ with the Group where your user is assigned to any of the Target AWS Accounts (Dev, Test, Prod)

You don’t need any entry on the ~/.aws/credentials or ~/.aws/config

<p align="center">
  <img src="https://miro.medium.com/v2/resize:fit:1100/format:webp/1*yOm0_8WOZBo_w0R2AqFoaA.png" width="800" />
</p>

<p align="center">
  <img src="https://miro.medium.com/v2/resize:fit:1100/format:webp/1*k_dbMgbzH6tDU8Fk3gT7Jg.png" width="800" />
</p>

<p align="center">
  <img src="https://miro.medium.com/v2/resize:fit:640/format:webp/1*KdCJgKTuJogBnvF3lUR5SA.png" width="640" />
</p>

<p align="center">
  <img src="https://miro.medium.com/v2/resize:fit:1100/format:webp/1*uvJ7w7iv0LNWZkWqvbykVw.png" width="800" />
</p>

<p align="center">
  <img src="https://miro.medium.com/v2/resize:fit:640/format:webp/1*lC4uPAESIpAyZQtCPy7zaw.png" width="640" />
</p>

<p align="center">
  <img src="https://miro.medium.com/v2/resize:fit:608/format:webp/1*qj8LlgMUG3HlFLcfs2geuQ.png" width="600" />
</p>

```sh

$ aws configure sso
SSO session name (Recommended): my-sso
SSO start URL [None]: https://my-organization.awsapps.com/start#
SSO region [None]: us-west-1
SSO registration scopes [sso:account:access]:
Attempting to automatically open the SSO authorization page in your default browser.
If the browser does not open or you wish to use a different device to authorize this request, open the following URL:

https://device.sso.us-west-1.amazonaws.com/

Then enter the code:

TJDF-ZXWL
There are 9 AWS accounts available to you.
Using the account ID 222222222222
There are 3 roles available to you.
Using the role name "Terraform"
CLI default client Region [None]: us-west-1
CLI default output format [None]: json
CLI profile name [dev]:

aws s3 ls --profile dev

```