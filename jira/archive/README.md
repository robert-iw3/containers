## Jira, Postgres & backup db, with Traefik.

Jira - https://www.atlassian.com/software/jira

Postgres - https://www.postgresql.org/

Traefik - https://traefik.io/

```sh

cd ~/_tooling/compose_up/jira

#create .env to pass variables to compose

tee ./.env<<\EOF
#initial psql container need's password set or will fail to initialize
POSTGRES_PASSWORD=
#update after creating user
JIRA_DB_PASS=
#podman user id to use podman socket for traefik
UID=
BACKUP_PSQL_PASS=
EOF

```

Additional steps (configure jira db user and password, create jira db):

```sh
podman-compose -f docker-compose-psql.yml up -d
podman exec -it postgres /bin/bash
```

```console
1001@704fa0524868:/$ psql -U postgres -W
Password:
#enter password from .env for ${POSTGRES_PASS}

    create user jira with encrypted password '_enter a password here_';
    create database jira with owner jira encoding 'UTF8';
    \q

exit
```

Update .env with jira db user password

Update "docker-compose-jira.yml":

```yaml
      # Email for Let's Encrypt (replace with yours)
      - "--certificatesresolvers.letsencrypt.acme.email=enter_email@here"

      # Passwords must be encoded using MD5, SHA1, or BCrypt
      - "traefik.http.middlewares.authtraefik.basicauth.users=traefikadmin:$$enter$$hashed$$passhere"
```

```sh
podman-compose -f docker-compose-jira.yml up -d
```
