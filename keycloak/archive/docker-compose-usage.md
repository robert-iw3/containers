## Keycloak, Postgres & backup db, with Traefik.

Keycloak - https://www.keycloak.org/
Postgres - https://www.postgresql.org/
Traefik - https://traefik.io/

```sh

cd ~/apps/keycloak

#create .env to pass variables to compose

tee ./.env<<\EOF
#keycloak and postgres cred's
POSTGRESQL_USER=
POSTGRESQL_PASSWORD=
POSTGRESQL_DATABASE=
POSTGRESQL_REPLICATION_USER=
POSTGRESQL_REPLICATION_PASSWORD=
DB_VENDOR=
DB_ADDR=
DB_PORT=
KEYCLOAK_USER=
KEYCLOAK_PASSWORD=
JGROUPS_DISCOVERY_PROTOCOL=
JGROUPS_DISCOVERY_PROPERTIES=
KEYCLOAK_LOGLEVEL=
EOF

```

Update "docker-compose-keycloak.yml":

```yaml
      # Email for Let's Encrypt (replace with yours)
      - "--certificatesresolvers.letsencrypt.acme.email=enter_email@here"

      # Passwords must be encoded using MD5, SHA1, or BCrypt
      - "traefik.http.middlewares.authtraefik.basicauth.users=traefikadmin:$$enter$$hashed$$passhere"
```

```sh
podman-compose -f docker-compose-keycloak.yml up -d
```
