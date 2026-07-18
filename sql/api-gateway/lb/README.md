# Load balancer (nginx or haproxy)

Put either load balancer in front of the gateway replicas. Both balance across
`api-gateway`, `gateway-b`, `gateway-c` and publish on `127.0.0.1:8088`.

```sh
# from api-gateway/
docker compose -f docker-compose.yml -f lb/docker-compose.lb.yml --profile lb-nginx   up -d --build
docker compose -f docker-compose.yml -f lb/docker-compose.lb.yml --profile lb-haproxy up -d --build   # + stats on :8404
```

| File | Role |
| --- | --- |
| [`nginx.conf`](nginx.conf) | nginx upstream (least-conn) + optional TLS block |
| [`haproxy.cfg`](haproxy.cfg) | haproxy backend (round-robin, health checks, runtime DNS) + stats |
| [`docker-compose.lb.yml`](docker-compose.lb.yml) | overlay: 3 gateway replicas + the chosen LB |
| [`init-certs.sh`](init-certs.sh) | certbot DNS-01 issuance/renewal for nginx TLS |

Verify routing + tuning + data flow end to end with
`../uat/final-uat.sh nginx` or `../uat/final-uat.sh haproxy`.

---

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

This directory is a compose **overlay** for the main stack: nginx terminates
TLS and load-balances across every `api-gateway` replica.

#### Usage Steps
1. **Update Files**: Replace placeholders in `nginx.conf`, `init-certs.sh`, and
   the provider credentials (`certbot/conf/<provider>.ini`) with your domains,
   email, and API token.
2. **DNS Setup**: For wildcard/multi-domain, the DNS-01 challenge adds TXT
   records via your provider (Certbot handles propagation).
3. **Run** (from the `api-gateway/` directory):
   ```sh
   docker compose -f docker-compose.yml -f nginx/docker-compose.yml --profile certbot up -d
   ```
   The certbot container auto-issues if no certs exist.
4. **Test**: `curl -H "Authorization: Bearer <token>" \
   https://yourdomain.com/v1/op/get_user -d '{"params":{"id":1}}'`.
   HTTP redirects to HTTPS.
5. **Renewal**: Auto every 12h; the deploy hook reloads nginx without downtime.
6. **Customization**: For other DNS providers, change the certbot image to
   `certbot/dns-route53`, `certbot/dns-google`, etc. and supply that provider's
   credentials/env.
7. **Scaling**: `docker compose up -d --scale api-gateway=N` — nginx balances
   across replicas automatically via the `least_conn` upstream.