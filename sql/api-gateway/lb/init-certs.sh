#!/bin/sh
# Issue initial Let's Encrypt certificates (DNS-01) and renew on a loop.
# Fill in the domains, email, and provider credentials before use.
set -eu

PRIMARY_DOMAIN="yourdomain.com"
DOMAINS="-d yourdomain.com -d www.yourdomain.com -d *.yourdomain.com"
EMAIL="you@yourdomain.com"
CREDENTIALS="/etc/letsencrypt/cloudflare.ini"   # dns_cloudflare_api_token = ...

if [ ! -f "/etc/letsencrypt/live/${PRIMARY_DOMAIN}/fullchain.pem" ]; then
    echo "Issuing initial certificate for ${PRIMARY_DOMAIN}..."
    # Add --test-cert first to validate against the staging CA.
    certbot certonly \
        --non-interactive \
        --agree-tos \
        --email "${EMAIL}" \
        --dns-cloudflare \
        --dns-cloudflare-credentials "${CREDENTIALS}" \
        --preferred-challenges dns-01 \
        ${DOMAINS}
fi

# Renew every 12h; reload nginx in the sibling container on success.
trap exit TERM
while :; do
    certbot renew --quiet --deploy-hook "nginx -s reload" || true
    sleep 12h & wait ${!}
done
