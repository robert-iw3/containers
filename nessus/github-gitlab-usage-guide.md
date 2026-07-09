# Usage Guide: Setting Up Secrets and Variables for GitHub Actions and GitLab CI/CD

This guide explains how to configure secrets and variables for the GitHub Actions workflow and GitLab CI/CD pipeline used to build, test, and deploy the Nessus stack, including the React app for plugin management. The configurations are based on the workflows defined in `.github/workflows/ci-cd.yml` and `.gitlab-ci.yml`, which deploy a Dockerized Nessus stack with Node 24, Tailwind CSS, and Nginx, interacting with the Nessus API via `https://api-fw.testing.io:8088`.

## Overview
The Nessus stack requires the following sensitive data:
- **Nessus API Keys**: For accessing the Nessus API (`accessKey` and `secretKey`).
- **Docker Registry Credentials**: For pushing images to GitHub Container Registry (`ghcr.io`) or GitLab Container Registry (`registry.gitlab.com`).
- **SSH Private Key**: For deploying to a remote VM or server via SSH.
- **Deployment Host**: The target server’s hostname or IP for deployment.

These are managed as **secrets** (sensitive data) or **variables** (non-sensitive data) in GitHub and GitLab to ensure security and prevent hardcoding in source code.

## Prerequisites
- **Repository**: A GitHub or GitLab repository containing the Nessus stack files:
  ```
  nessus-stack/
  ├── src/
  │   ├── index.jsx
  │   ├── index.css
  ├── nginx/
  │   ├── nginx.conf
  │   ├── ssl-params.conf
  ├── plugins.Dockerfile
  ├── package.json
  ├── tailwind.config.js
  ├── postcss.config.js
  ├── docker-compose.yml
  ├── .github/workflows/ci-cd.yml
  ├── .gitlab-ci.yml
  ```
- **Nessus API Keys**: Generated from the Nessus UI (`Settings > API Keys`) in the format `accessKey=your_access_key;secretKey=your_secret_key`.
- **Docker Registry Access**:
  - GitHub: A Personal Access Token (PAT) with `write:packages` scope for GitHub Container Registry.
  - GitLab: A deploy token or personal access token for GitLab Container Registry.
- **Deployment Server**: A VM or server with SSH access, Podman or Docker installed, and `podman-compose` or `docker-compose` configured.
- **Local Testing**: Ensure `/etc/hosts` includes:
  ```
  127.0.0.1 nessus.testing.io api-fw.testing.io
  ```

## GitHub Actions Secrets and Variables

### Secrets
Secrets are stored in the GitHub repository under `Settings > Secrets and variables > Actions > Secrets`. These are encrypted and only accessible to workflows.

1. **DOCKER_REGISTRY_TOKEN**
   - **Purpose**: Authenticates with GitHub Container Registry (`ghcr.io`) to push Docker images.
   - **How to Create**:
     1. Go to your GitHub profile > `Settings > Developer settings > Personal access tokens > Tokens (classic)`.
     2. Generate a new token with `write:packages` scope.
     3. Copy the token (e.g., `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`).
   - **Add to Repository**:
     1. Navigate to your repository > `Settings > Secrets and variables > Actions > Secrets`.
     2. Click `New repository secret`.
     3. Name: `DOCKER_REGISTRY_TOKEN`.
     4. Value: Paste the PAT.
   - **Usage in Workflow**: Referenced in `.github/workflows/ci-cd.yml`:
     ```yaml
     with:
       registry: ${{ env.REGISTRY }}
       username: ${{ github.actor }}
       password: ${{ secrets.DOCKER_REGISTRY_TOKEN }}
     ```

2. **NESSUS_API_KEYS**
   - **Purpose**: Authenticates API calls to the Nessus API (`https://api-fw.testing.io:8088`).
   - **How to Obtain**:
     1. Log in to Nessus (`https://nessus.testing.io:8834`).
     2. Go to `Settings > API Keys`.
     3. Generate or copy the `accessKey` and `secretKey` in the format: `accessKey=your_access_key;secretKey=your_secret_key`.
   - **Add to Repository**:
     1. Go to `Settings > Secrets and variables > Actions > Secrets`.
     2. Click `New repository secret`.
     3. Name: `NESSUS_API_KEYS`.
     4. Value: Paste the API keys string (e.g., `accessKey=abc123;secretKey=xyz789`).
   - **Usage in Workflow**: Used in the `validate-plugin` job:
     ```yaml
     env:
       NESSUS_API_KEYS: ${{ secrets.NESSUS_API_KEYS }}
     run: |
       curl -X POST -H "X-ApiKeys: $NESSUS_API_KEYS" -F "plugin=@dist/plugin.nasl" ...
     ```

3. **SSH_PRIVATE_KEY**
   - **Purpose**: Enables SSH access to the deployment server for running `podman-compose up -d`.
   - **How to Create**:
     1. Generate an SSH key pair on your local machine:
        ```bash
        ssh-keygen -t ed25519 -C "nessus-deployment" -f ~/.ssh/nessus-deploy
        ```
     2. Copy the public key (`~/.ssh/nessus-deploy.pub`) to the deployment server’s `~/.ssh/authorized_keys`:
        ```bash
        ssh-copy-id -i ~/.ssh/nessus-deploy.pub user@your-vm-host
        ```
     3. Copy the private key (`~/.ssh/nessus-deploy`).
   - **Add to Repository**:
     1. Go to `Settings > Secrets and variables > Actions > Secrets`.
     2. Click `New repository secret`.
     3. Name: `SSH_PRIVATE_KEY`.
     4. Value: Paste the contents of the private key (e.g., `-----BEGIN OPENSSH PRIVATE KEY-----...`).
   - **Usage in Workflow**: Used in the `deploy` job:
     ```yaml
     uses: webfactory/ssh-agent@v0.9.0
     with:
       ssh-private-key: ${{ secrets.SSH_PRIVATE_KEY }}
     ```

### Variables
Variables are non-sensitive and stored under `Settings > Secrets and variables > Actions > Variables`.

1. **REGISTRY**
   - **Purpose**: Specifies the Docker registry URL.
   - **Value**: `ghcr.io`
   - **Add to Repository**:
     1. Go to `Settings > Secrets and variables > Actions > Variables`.
     2. Click `New repository variable`.
     3. Name: `REGISTRY`.
     4. Value: `ghcr.io`.
   - **Usage in Workflow**:
     ```yaml
     env:
       REGISTRY: ghcr.io
       IMAGE_NAME: ${{ github.repository }}/nessus-plugin-management
     ```

2. **NESSUS_API_URL**
   - **Purpose**: Defines the Nessus API endpoint.
   - **Value**: `https://api-fw.testing.io:8088`
   - **Add to Repository**:
     1. Go to `Settings > Secrets and variables > Actions > Variables`.
     2. Click `New repository variable`.
     3. Name: `NESSUS_API_URL`.
     4. Value: `https://api-fw.testing.io:8088`.
   - **Usage in Workflow**:
     ```yaml
     env:
       NESSUS_API_URL: https://api-fw.testing.io:8088
     ```

3. **DEPLOY_HOST**
   - **Purpose**: Specifies the target server for deployment.
   - **Value**: Your VM’s hostname or IP (e.g., `192.168.1.100` or `deploy.example.com`).
   - **Add to Repository**:
     1. Go to `Settings > Secrets and variables > Actions > Variables`.
     2. Click `New repository variable`.
     3. Name: `DEPLOY_HOST`.
     4. Value: Your VM’s hostname or IP.
   - **Usage in Workflow**:
     ```yaml
     env:
       DEPLOY_HOST: your-vm-host
     ```

### GitLab CI/CD Variables

GitLab uses CI/CD variables for both sensitive and non-sensitive data, stored under `Settings > CI/CD > Variables`. Sensitive variables should be marked as **protected** and **masked** to prevent exposure.

1. **CI_REGISTRY_USER**
   - **Purpose**: Username for GitLab Container Registry authentication.
   - **How to Create**:
     1. Go to your GitLab profile > `Access Tokens`.
     2. Create a personal access token or deploy token with `read_registry` and `write_registry` scopes.
     3. Copy the username (e.g., your GitLab username or deploy token name).
   - **Add to Project**:
     1. Navigate to your GitLab project > `Settings > CI/CD > Variables`.
     2. Click `Add variable`.
     3. Key: `CI_REGISTRY_USER`.
     4. Value: Your username or deploy token name.
     5. Check `Protect variable` and `Mask variable`.
   - **Usage in Pipeline**:
     ```yaml
     script:
       - echo "$CI_REGISTRY_PASSWORD" | docker login $CI_REGISTRY -u $CI_REGISTRY_USER --password-stdin
     ```

2. **CI_REGISTRY_PASSWORD**
   - **Purpose**: Password or token for GitLab Container Registry.
   - **How to Obtain**: Use the token generated with `CI_REGISTRY_USER`.
   - **Add to Project**:
     1. Go to `Settings > CI/CD > Variables`.
     2. Click `Add variable`.
     3. Key: `CI_REGISTRY_PASSWORD`.
     4. Value: Paste the token.
     5. Check `Protect variable` and `Mask variable`.
   - **Usage in Pipeline**:
     ```yaml
     script:
       - echo "$CI_REGISTRY_PASSWORD" | docker login $CI_REGISTRY -u $CI_REGISTRY_USER --password-stdin
     ```

3. **NESSUS_API_KEYS**
   - **Purpose**: Authenticates API calls to the Nessus API.
   - **How to Obtain**: Same as for GitHub (from Nessus UI: `accessKey=your_access_key;secretKey=your_secret_key`).
   - **Add to Project**:
     1. Go to `Settings > CI/CD > Variables`.
     2. Click `Add variable`.
     3. Key: `NESSUS_API_KEYS`.
     4. Value: Paste the API keys string.
     5. Check `Protect variable` and `Mask variable`.
   - **Usage in Pipeline**:
     ```yaml
     variables:
       NESSUS_API_KEYS: $NESSUS_API_KEYS
     script:
       - curl -X POST -H "X-ApiKeys: $NESSUS_API_KEYS" -F "plugin=@dist/plugin.nasl" ...
     ```

4. **SSH_PRIVATE_KEY**
   - **Purpose**: Enables SSH access to the deployment server.
   - **How to Create**: Same as for GitHub (generate with `ssh-keygen`, add public key to server’s `authorized_keys`).
   - **Add to Project**:
     1. Go to `Settings > CI/CD > Variables`.
     2. Click `Add variable`.
     3. Key: `SSH_PRIVATE_KEY`.
     4. Value: Paste the private key contents.
     5. Check `Protect variable` and `Mask variable` (note: masking may fail if the key format doesn’t meet GitLab’s requirements; ensure `Protect variable` is set).
   - **Usage in Pipeline**:
     ```yaml
     script:
       - echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_rsa
       - chmod 600 ~/.ssh/id_rsa
     ```

5. **DEPLOY_HOST**
   - **Purpose**: Specifies the deployment server’s hostname or IP.
   - **Value**: Your VM’s hostname or IP (e.g., `192.168.1.100`).
   - **Add to Project**:
     1. Go to `Settings > CI/CD > Variables`.
     2. Click `Add variable`.
     3. Key: `DEPLOY_HOST`.
     4. Value: Your VM’s hostname or IP.
     5. Uncheck `Protect variable` (not sensitive).
   - **Usage in Pipeline**:
     ```yaml
     variables:
       DEPLOY_HOST: your-vm-host
     ```

6. **CI_REGISTRY**
   - **Purpose**: Defines the GitLab Container Registry URL.
   - **Value**: `registry.gitlab.com`
   - **Add to Project**:
     1. Go to `Settings > CI/CD > Variables`.
     2. Click `Add variable`.
     3. Key: `CI_REGISTRY`.
     4. Value: `registry.gitlab.com`.
     5. Uncheck `Protect variable`.
   - **Usage in Pipeline**:
     ```yaml
     variables:
       CI_REGISTRY: registry.gitlab.com
       CI_REGISTRY_IMAGE: $CI_REGISTRY/$CI_PROJECT_PATH
     ```

### Additional Setup for Deployment Server
1. **Install Podman/Docker**:
   - On the deployment server, install Podman or Docker:
     ```bash
     sudo apt update && sudo apt install -y podman podman-compose
     # OR
     sudo apt update && sudo apt install -y docker.io docker-compose
     ```
2. **Configure SSH**:
   - Ensure the server’s `~/.ssh/authorized_keys` includes the public key from the SSH key pair.
   - Test SSH access:
     ```bash
     ssh -i ~/.ssh/nessus-deploy user@your-vm-host
     ```
3. **Network Configuration**:
   - Add to the server’s `/etc/hosts`:
     ```bash
     127.0.0.1 nessus.testing.io api-fw.testing.io
     ```
4. **Secrets File**:
   - The workflows create `~/nessus-stack/secrets/nessus_api_keys.txt` on the deployment server with the contents of `NESSUS_API_KEYS`.
   - Ensure the directory `~/nessus-stack/secrets/` exists or is created by the workflow.

### Testing the Setup
1. **Local Testing**:
   - Create a local `secrets/nessus_api_keys.txt` with the Nessus API keys.
   - Run the stack locally:
     ```bash
     podman-compose -f docker-compose.yml up -d
     ```
   - Access the React app at `https://nessus.testing.io/app`.
2. **Pipeline Testing**:
   - **GitHub**: Push to `main` or create a pull request to trigger `.github/workflows/ci-cd.yml`. Check the Actions tab for logs.
   - **GitLab**: Push to `main` or create a merge request to trigger `.gitlab-ci.yml`. Check the CI/CD > Pipelines tab for logs.
   - For GitLab, manually trigger the `deploy_production` job in the UI after verifying the build and test stages.
3. **Verify Deployment**:
   - SSH into the deployment server and check:
     ```bash
     podman ps
     # OR
     docker ps
     ```
   - Ensure the `react-app`, `nessus`, `api-firewall`, and `nginx` containers are running.
   - Access `https://nessus.testing.io/app` to verify the React app.

### Security Best Practices
- **Mask Sensitive Data**: Ensure all secrets (e.g., `NESSUS_API_KEYS`, `CI_REGISTRY_PASSWORD`) are masked in GitLab and not logged in GitHub Actions.
- **Protect Variables**: Use protected variables in GitLab for `main` branch only to prevent exposure in forks or unprotected branches.
- **Rotate Keys**: Regularly rotate Nessus API keys and SSH keys, updating them in GitHub/GitLab secrets.
- **Secure SSH**: Consider adding `known_hosts` verification instead of `StrictHostKeyChecking=no` for production.
- **Registry Access**: Limit registry tokens to minimal scopes (`write:packages` for GitHub, `read_registry`/`write_registry` for GitLab).

### Troubleshooting
- **GitHub Actions**:
  - **Error**: `Permission denied` for Docker registry.
    - **Fix**: Verify `DOCKER_REGISTRY_TOKEN` has `write:packages` scope and is correctly set.
  - **Error**: `SSH connection failed`.
    - **Fix**: Ensure `SSH_PRIVATE_KEY` is valid and the public key is in the deployment server’s `authorized_keys`.
- **GitLab CI/CD**:
  - **Error**: `Masking failed` for `SSH_PRIVATE_KEY`.
    - **Fix**: Ensure the key format is compatible with GitLab’s masking rules (avoid special characters in the key).
  - **Error**: `Pipeline skipped due to rules`.
    - **Fix**: Check `workflow:rules` in `.gitlab-ci.yml` and ensure the branch or trigger matches.
- **General**:
  - **Error**: Nessus API calls fail with `401 Unauthorized`.
    - **Fix**: Verify `NESSUS_API_KEYS` format and ensure the keys are valid in Nessus.
  - **Error**: `https://nessus.testing.io/app` inaccessible.
    - **Fix**: Check `/etc/hosts` on the deployment server and ensure Nginx is running (`podman logs nginx`).

### Notes
- **Nessus API Keys**: Must be in the format `accessKey=your_access_key;secretKey=your_secret_key` with no extra whitespace.
- **Plugin Validation**: The workflows assume a `dist/plugin.nasl` file exists for testing. Replace with an actual plugin file or adjust the `curl` command.
- **Deployment Host**: Replace `your-vm-host` with your actual server’s IP or hostname in both workflows and variables.
- **Node 24**: Both workflows use `node:24` to match the React app’s requirements. If Node 26 is released by September 2025, update to `node:26`.

