# Nessus

This project deploys a secure Nessus scanner with an API Firewall (Wallarm), Nginx reverse proxy, a React-based management app, and a scan result parser, all in a single Docker Compose stack. It includes CI/CD integration and Ansible automation.

> **Warning**: Do not expose port 8834 in production. Use Nginx or API Firewall. Obtain an activation code and API keys from [Tenable](https://www.tenable.com/products/nessus/activation-code).

## Prerequisites
- [Podman](https://podman.io/getting-started/installation) or [Docker](https://docs.docker.com/get-docker/)
- [podman-compose](https://github.com/containers/podman-compose)
- [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)
- Python 3.9+ (for parser)
- Nessus activation code and API keys

### Directory Structure
---
```console
nessus/
├── certs/
│   ├── nessus.testing.io.crt
│   ├── nessus.testing.io.key
│   ├── apifw.testing.io.pem
│   ├── apifw.testing.io-key.pem
├── nginx/
│   ├── nginx.conf
│   ├── ssl-params.conf
│   ├── dhparam.pem
├── secrets/
│   ├── nessus_username.txt
│   ├── nessus_password.txt
│   ├── activation_code.txt
│   ├── apifw_config.txt
│   ├── nessus_api_keys.txt
├── nessusapi/
│   ├── nessus-api-spec.json
├── src/
│   ├── index.jsx
│   ├── index.css
├── exports/
├── plugins/
├── output/
├── Dockerfile
├── plugins.Dockerfile
├── package.json
├── tailwind.config.js
├── postcss.config.js
├── nessus-parser.py
├── entrypoint.sh
├── playbook.yml
├── Jenkinsfile
├── README.md
```

## Setup

### 1. Clone Repository
```bash
git clone https://github.com/your-repo/nessus.git
cd nessus
```

### 2. Create Secrets
```bash
mkdir -p secrets
echo "your-username" > secrets/nessus_username.txt
echo "your-password" > secrets/nessus_password.txt
echo "your-activation-code" > secrets/activation_code.txt
echo "apifw-config" > secrets/apifw_config.txt
echo "accessKey=your_access_key;secretKey=your_secret_key" > secrets/nessus_api_keys.txt
```

### 3. Run Ansible Playbook
```bash
ansible-playbook playbook.yml
```

### 4. Manual Deployment (Alternative)
```bash
# Create directories
mkdir -p certs nginx nessusapi exports plugins output

# Generate certificates
openssl req -x509 -nodes -days 730 -newkey rsa:2048 -keyout certs/nessus.testing.io.key -out certs/nessus.testing.io.crt -subj "/C=US/ST=XX/L=XXXX/O=Testing/CN=nessus.testing.io"
openssl req -x509 -nodes -days 730 -newkey rsa:2048 -keyout certs/apifw.testing.io-key.pem -out certs/apifw.testing.io.pem -subj "/C=US/ST=XX/L=XXXX/O=Testing/CN=api-fw.testing.io"
openssl dhparam -out nginx/dhparam.pem 2048
cp certs/nessus.testing.io.* nginx/

# Deploy stack
podman-compose up -d
```

### 5. Access Services
Add to `/etc/hosts`:
```bash
echo "127.0.0.1 nessus.testing.io api-fw.testing.io" | sudo tee -a /etc/hosts
```
- **Nessus UI**: `https://nessus.testing.io`
- **API Firewall**: `https://api-fw.testing.io:8088`
- **Scan Results**: In `./output/nessus_report.xlsx`

### 6. Parse Scan Results
Results are automatically parsed to `./output/nessus_report.xlsx`. To run manually:
```bash
podman run --rm -v $(pwd)/exports:/exports:z -v $(pwd)/output:/output:z python:3.9 \
  bash -c "pip install xlsxwriter dateparser ipaddress requests && \
  python /app/nessus-parser.py --api-url http://api-fw.testing.io:8088 \
  --api-keys '$(cat secrets/nessus_api_keys.txt)' --export-dir /exports --output /output/nessus_report.xlsx"
```

### 7. CI/CD Integration
- Configure Jenkins with the provided `Jenkinsfile`.
- Set up `nessus-api-keys` and `docker-credentials-id` in Jenkins credentials.
- Trigger builds on code changes to build, test, and deploy the React app and plugins.

## Troubleshooting
- **Port conflicts**: Ensure 80, 443, 8834, 8088 are free.
- **Cert errors**: Verify certs match hostnames.
- **API issues**: Check `nessus-api-spec.json` in API Firewall.
- **Podman/Docker**: Use `network_mode: bridge` for cross-host issues.

## Production Notes
- Use LetsEncrypt for certificates.
- Scan images with Trivy (`trivy image tenableofficial/nessus:10.8.4`).
- Backup `nessus_data` volume.
- Disable `AUTO_UPDATE: all` for manual updates.

## Resources
- [Tenable Nessus Docs](https://docs.tenable.com/nessus)
- [Nessus API](https://docs.tenable.com/nessus/10.8/Content/API.htm)
- [Podman](https://podman.io)
- [Ansible](https://docs.ansible.com)