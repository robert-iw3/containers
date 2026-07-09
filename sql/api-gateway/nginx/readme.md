### NGINX HTTPS Setup with Wildcard, Multiple Domains, and Auto-Initial Issuance
---

- **Wildcard**: Uses DNS-01 challenge via Certbot (webroot won't work for wildcards). Assume Cloudflare as DNS provider (common; replace with your provider's plugin, e.g., `--dns-route53` for AWS). Provide API credentials via env.
- **Multiple Domains**: Expand `server_name` and Certbot `-d` flags.
- **Auto-Initial Issuance**: Add a bash script (`init-certs.sh`) as Certbot entrypoint. It checks if certs exist; if not, issues them, then starts renewal loop.
- **Security/Prod Notes**: Use strong API tokens; restrict to needed scopes (e.g., Cloudflare: Zone DNS Edit). Test on staging (`--test-cert`) first. For multi-domain/wildcard, ensure DNS points to your IP.

#### Cloudflare Credentials File
Create `certbot/conf/cloudflare.ini` (mounted as volume; Certbot reads env to generate if needed, but pre-create for safety):

```ini
# cloudflare.ini
dns_cloudflare_email = your@cloudflare.email
dns_cloudflare_api_token = your_cloudflare_api_token
```

#### Usage Steps
1. **Update Files**: Replace placeholders (domains, email, tokens).
2. **DNS Setup**: For wildcard/multi, add TXT records via DNS provider for validation (Certbot handles propagation).
3. **Run**: `docker compose up -d`. Script auto-issues if no certs.
4. **Test**: Access `https://yourdomain.com/query`. HTTP redirects to HTTPS.
5. **Renewal**: Auto every 12h; hook reloads NGINX without downtime.
6. **Customization**: For other DNS (e.g., AWS), change image to `certbot/dns-route53` and env (e.g., `AWS_ACCESS_KEY_ID`).