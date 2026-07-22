# TLS material for the HAProxy proxy

`deploy.yml` copies a combined PEM from this directory onto the proxy host
(`{{ tls_dir }}` → `/etc/haproxy/tls`). HAProxy reads the certificate and key
from a single file:

- `haproxy.pem` — server certificate **and** private key concatenated
  (full chain for production)

This file is **gitignored** and never committed. For a lab, generate one:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout key.pem -out cert.pem \
  -subj "/CN=app.example.com" \
  -addext "subjectAltName=DNS:app.example.com"
cat cert.pem key.pem > haproxy.pem
```

For production, concatenate the issued certificate chain and key into
`haproxy.pem`.
