# Hashicorp Vault Agent Tutorial: Generating `.env` from Vault Secrets

In this tutorial, we will set up Vault Agent to generate a `.env` file with secrets from HashiCorp Vault. We’ll use the AppRole authentication method to securely authenticate and retrieve secrets, then write them to an environment file for use in your application.


⚠️ **Important Note:** This tutorial uses Vault in development mode (`-dev`) for simplicity. Development mode is **not secure** and should only be used for testing and learning purposes. In a production environment:
- Use a properly initialized and unsealed Vault server.
- Secure the Vault server with TLS certificates and access control.

## Prerequisites

- Vault server running (in development mode for testing)
- Vault Agent installed and configured
- Basic knowledge of Vault and its authentication methods


## Step 1: Start Vault Server in Development Mode

We’ll start Vault in development mode for testing purposes. This will make Vault accessible via `127.0.0.1:8200` with a root token.

Run the following command:

```bash
vault server -dev -dev-root-token-id=root -dev-tls
```

Access Vault’s UI by navigating to [https://127.0.0.1:8200](https://127.0.0.1:8200) and logging in with the `root` token.

## Step 2: Set Up the AppRole Authentication Method

We will use AppRole for authentication. First, enable the AppRole authentication method:

```bash
vault auth enable approle
```

Next, create a new AppRole and attach a policy that allows reading from the `secret/data/dbinfo` path:

1. **Create the Vault policy (`agent-policy.hcl`)**:
    ```hcl
    path "secret/data/dbinfo" {
      capabilities = ["read"]
    }
    ```

2. **Write the policy**:
    ```bash
    vault policy write agent-policy agent-policy.hcl
    ```

3. **Create the AppRole and attach the policy**:
    ```bash
    vault write auth/approle/role/vault-agent-role policies="agent-policy"
    ```

4. **Generate the `role_id` and `secret_id`**:
    ```bash
    vault read auth/approle/role/vault-agent-role/role-id
    vault write -f auth/approle/role/vault-agent-role/secret-id
    ```

The `role_id` and `secret_id` are required to authenticate via AppRole. Save these values to the files `role_id` and `secret_id`.

## Step 3: Configure Vault Agent

The Vault Agent configuration file (`vault-agent.hcl`) will authenticate with Vault using the AppRole and generate a `.env` file with the secret values. Here’s an example configuration:

```hcl
# Vault Agent configuration
vault {
  address = "https://127.0.0.1:8200"
  token = "<client_token>"
}

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path = "./role_id"
      secret_id_file_path = "./secret_id"
    }
  }

  sink "file" {
    path = "./vault-agent-token"
  }
}

template {
  source      = "./env-template.tmpl"
  destination = "./.env"
}
```

**Explanation**:
- The `role_id_file_path` and `secret_id_file_path` point to the files containing the AppRole credentials.
- The `template` block specifies the path to the `env-template.tmpl` file and the destination for the generated `.env` file.

## Step 4: Create the Template File (`env-template.tmpl`)

Create a template file (`env-template.tmpl`) that Vault Agent will use to generate the `.env` file. Here’s an example template:

```plaintext
DB_USER={{ with secret "secret/data/dbinfo" }}{{ .Data.data.user }}{{ end }}
DB_PASS={{ with secret "secret/data/dbinfo" }}{{ .Data.data.pass }}{{ end }}
```

This template will insert the `user` and `pass` from the Vault secrets into the `.env` file.

## Step 5: Start Vault Agent

Now, we will start the Vault Agent to authenticate and generate the `.env` file:

```bash
vault agent -config=./vault-agent.hcl
```

Vault Agent will authenticate using AppRole, retrieve the secret from `secret/data/dbinfo`, and generate the `.env` file at the specified location.

## Step 6: Check the Generated `.env` File

After Vault Agent runs, the `.env` file will be populated with the secrets from Vault:

```plaintext
DB_USER=root
DB_PASS=test123
```

This file can now be used to set environment variables for your application.

Your final files should be like this:

```plaintext
agent-policy.hcl
env-template.tmpl
role_id
secret_id
vault-agent.hcl
vault-agent.pid
vault-agent-token
```

## Conclusion

In this tutorial, we’ve configured Vault Agent to authenticate with Vault using AppRole, retrieve secrets, and generate a `.env` file. This is a simple and secure way to manage sensitive configuration data in your application.

I hope this tutorial helps you get Vault Agent running smoothly. Happy coding! 🚀
