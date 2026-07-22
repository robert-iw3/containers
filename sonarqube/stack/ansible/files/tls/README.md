# TLS material for the proxy VM

Place the stack's server certificate and CA here before running the
playbook (the proxy play copies them to `stack.tls_dir`):

- `tls.crt` — server certificate covering the app, auth and keycloak hosts
- `tls.key` — its private key
- `ca.crt`  — the issuing CA (tinyauth trusts this for the Keycloak backchannel)

These are deployment secrets and are gitignored.
