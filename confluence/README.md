## Confluence, Postgres & backup db, with Traefik.

Confluence - https://www.atlassian.com/software/confluence

Postgres - https://www.postgresql.org/

Traefik - https://traefik.io/

```sh

cd ~/_tooling/compose_up/confluence

#create .env to pass variables to compose

tee ./.env<<\EOF
#initial psql container need's password set or will fail to initialize
POSTGRES_PASSWORD=
#update after creating user
CONFLUENCE_DB_PASS=
#podman user id to use podman socket for traefik
UID=
BACKUP_PSQL_PASS=
EOF

```

Additional steps (configure confluence db user and password, create confluence db):

```sh
podman-compose -f docker-compose-psql.yml up -d
podman exec -it postgres /bin/bash
```

```console
1001@704fa0524868:/$ psql -U postgres -W
Password:
#enter password from .env for ${POSTGRES_PASS}

    create user confluence with encrypted password '_enter a password here_';
    create database confluence with owner confluence encoding 'UTF8';
    \q

exit
```

Update .env with confluence db user password

Update "docker-compose-confluence.yml":

```yaml
      # Email for Let's Encrypt (replace with yours)
      - "--certificatesresolvers.letsencrypt.acme.email=enter_email@here"

      # Passwords must be encoded using MD5, SHA1, or BCrypt
      - "traefik.http.middlewares.authtraefik.basicauth.users=traefikadmin:$$enter$$hashed$$passhere"
```

```sh
podman-compose -f docker-compose-confluence.yml up -d
```
