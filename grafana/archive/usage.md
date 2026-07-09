## Grafana, Postgres & backup db, with Traefik.

Grafana - https://grafana.com/
Postgres - https://www.postgresql.org/
Traefik - https://traefik.io/

```sh

cd ~/apps/grafana

#create .env to pass variables to compose

tee ./.env<<\EOF
POSTGRESQL_USER=
POSTGRESQL_PASSWORD=
POSTGRESQL_DATABASE=grafana
POSTGRESQL_REPLICATION_USER=
POSTGRESQL_REPLICATION_PASSWORD=
GF_SERVER_DOMAIN=
GF_SERVER_ROOT_URL=
GF_SECURITY_ADMIN_USER=
GF_SECURITY_ADMIN_PASSWORD=
GF_SMTP_HOST=
GF_SMTP_USER=
GF_SMTP_PASSWORD=
GF_SMTP_FROM_ADDRESS=
PSQL_BACKUP_PASS=
# Wallarm API settings
WALLARM_API_HOST=us1.api.wallarm.com
WALLARM_API_TOKEN=
# Set to False when connect to dev environment
WALLARM_API_CA_VERIFY=True
WALLARM_MODE=safe_blocking
NGINX_PORT='80'
WALLARM_LABELS="group=grafana"
NGINX_BACKEND=grafana.io
EOF

```

Update "docker-compose-grafana.yml":

```yaml
      # Email for Let's Encrypt (replace with yours)
      - "--certificatesresolvers.letsencrypt.acme.email=enter_email@here"

      # Passwords must be encoded using MD5, SHA1, or BCrypt
      - "traefik.http.middlewares.authtraefik.basicauth.users=traefikadmin:$$enter$$hashed$$passhere"
```

```sh
podman-compose -f docker-compose-grafana.yml up -d
```
