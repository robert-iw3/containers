#!/bin/sh
# init-certs.sh: Auto-issue initial certs and renew

DOMAINS="-d yourdomain.com -d www.yourdomain.com -d anotherdomain.com"  # Add multiples
WILDCARD="-d *.yourdomain.com"  # Separate if wildcard (requires DNS-01)

# Combined domains (customize)
ALL_DOMAINS="$DOMAINS $WILDCARD"

# Check if cert exists
if [ ! -f "/etc/letsencrypt/live/yourdomain.com/fullchain.pem" ]; then
  echo "Issuing initial certificate..."
  certbot certonly \
    --non-interactive \
    --agree-tos \
    --email your@email.com \
    --dns-cloudflare \
    --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \  # Auto-created from env (Certbot handles)
    $ALL_DOMAINS \
    --preferred-challenges dns-01  # For wildcard/multi
  # Add --test-cert for staging/testing
fi

# Renewal loop
trap exit TERM
while :; do
  sleep 12h & wait ${!}
  certbot renew --quiet --deploy-hook "nginx -s reload" || true
done