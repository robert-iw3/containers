# Authelia SSO (owncloud `sso` profile)

Authelia acts as an **OpenID Connect provider** for ownCloud (real SSO for the
web UI via the `openidconnect` app; desktop/mobile/DAV clients keep working with
app passwords) and as **forward-auth** protecting the Traefik dashboard.

## Files

| File | Purpose |
|---|---|
| `configuration.yml` | Main config (4.38). Domains/URLs come from env; secrets are injected via `AUTHELIA_*_FILE`. Committed, secret-free. |
| `users_database.example.yml` | Template for the file auth backend. Copy to `secrets/users_database.yml` and set a real argon2id hash. |
| `secrets/` | Git-ignored. Holds `users_database.yml` and one file per secret (see below). |

## Bootstrap (also see ../owncloud-configure-oidc.sh)

```sh
cd owncloud/authelia && mkdir -p secrets

# One-off secrets
for s in session.secret storage.key jwt.secret oidc.hmac; do
  openssl rand -hex 32 > "secrets/$s"
done
# Redis password must match REDIS_PASSWORD in ../.env
printf '%s' "$REDIS_PASSWORD" > secrets/redis.password

# OIDC signing key
openssl genrsa -out secrets/oidc.issuer.pem 4096

# OIDC client secret: keep the plaintext for ownCloud, store only the hash here
CLIENT_SECRET="$(openssl rand -hex 32)"
docker run --rm authelia/authelia:4.38 \
  authelia crypto hash generate pbkdf2 --variant sha512 --password "$CLIENT_SECRET"
# -> put the plaintext in ../.env as OIDC_NEXTCLOUD_CLIENT_SECRET and the
#    printed $pbkdf2-sha512$... digest as OIDC_NEXTCLOUD_CLIENT_SECRET_HASH

# The login user
cp users_database.example.yml secrets/users_database.yml
docker run --rm authelia/authelia:4.38 \
  authelia crypto hash generate argon2 --password 'yourpassword'   # paste into secrets/users_database.yml
```

Then bring the stack up with the `sso` profile and register the provider in
ownCloud — `../owncloud-configure-oidc.sh` automates the ownCloud side.
