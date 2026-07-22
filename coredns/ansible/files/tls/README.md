# TLS material for the CoreDNS DoT listener

`deploy.yml` copies a certificate and key from this directory onto the resolver
host (`{{ tls_dir }}` → `/certs`) when `dot_listener` is true. Provide:

- `tls.crt` — server certificate (SAN must cover the name DoT clients verify)
- `tls.key` — matching private key

These are **gitignored** and never committed. For a lab, generate a self-signed
pair:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=dns.example.com" \
  -addext "subjectAltName=DNS:dns.example.com"
```

Clients then verify with e.g.
`kdig +tls +tls-ca=ca.crt +tls-hostname=dns.example.com @<host> -p 853 <name>`.
Set `dot_listener: false` in `stack.yaml` to serve classic Do53 only.
