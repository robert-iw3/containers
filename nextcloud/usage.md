## Nextcloud, Postgres & backup db, with Traefik.

Nextcloud - https://nextcloud.com/

Postgres - https://www.postgresql.org/

Traefik - https://traefik.io/

```sh

#create .env to pass variables to compose

tee ./.env<<\EOF
#nextcloud and postgres cred's
#initial psql container need's password set or will fail to initialize
POSTGRES_PASSWORD=
#update after creating user
NEXTCLOUD_DB_PASS=
#set admin cred's, trusted domain's
NEXTCLOUD_ADMIN_USER=
NEXTCLOUD_ADMIN_PASSWORD=
NEXTCLOUD_TRUSTED_DOMAINS=
#podman user id to use podman socket for traefik
UID=
BACKUP_PSQL_PASS=
EOF

```

Additional steps (configure nextcloud db user and password, create nextcloud db):

```sh
podman-compose -f docker-compose-psql.yml up -d
podman exec -it postgres /bin/bash
```

```console
1001@704fa0524868:/$ psql -U postgres -W
Password:
#enter password from .env for ${POSTGRES_PASS}

    create user nextcloud with encrypted password '_enter a password here_';
    create database nextcloud with owner nextcloud encoding 'UTF8';
    \q

exit
```

Update .env with nexcloud db user password

Update "docker-compose-nextcloud.yml":

```yaml
      # Email for Let's Encrypt (replace with yours)
      - "--certificatesresolvers.letsencrypt.acme.email=enter_email@here"

      # Passwords must be encoded using MD5, SHA1, or BCrypt
      - "traefik.http.middlewares.authtraefik.basicauth.users=traefikadmin:$$enter$$hashed$$passhere"
```

```sh
podman-compose -f docker-compose-nextcloud.yml up -d
```
