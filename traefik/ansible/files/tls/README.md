# TLS material for the Traefik proxy

`deploy.yml` copies a server certificate and key from this directory onto the
proxy host (`{{ tls_dir }}` → `/etc/traefik/tls`). Provide:

- `tls.crt` — server certificate (full chain for production)
- `tls.key` — matching private key

These are **gitignored** and never committed. For a lab, generate a self-signed
pair covering your route hosts:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=app.example.com" \
  -addext "subjectAltName=DNS:app.example.com"
```

For production, drop in the certificate issued for your route hostnames (or
front the proxy with your ACME workflow).
