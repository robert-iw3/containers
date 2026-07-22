echo "PG_USER=authentik" >> .env
echo "PG_DB=authentik" >> .env
echo "PG_PASS=$(openssl rand -base64 36 | tr -d '\n')" >> .env
echo "AUTHENTIK_SECRET_KEY=$(openssl rand -base64 60 | tr -d '\n')" >> .env
echo "AUTHENTIK_ERROR_REPORTING__ENABLED=true" >> .env
echo "GATEWAY=$(ip route | grep default | awk '{print $3}')" >> .env
echo "TS_AUTH_PORT=443" >> .env
echo "TS_AUTH_SCHEME=https" >> .env
