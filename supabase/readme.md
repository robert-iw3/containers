![image](https://user-images.githubusercontent.com/8291514/213727225-56186826-bee8-43b5-9b15-86e839d89393.png#gh-dark-mode-only)

Supabase is an open source Firebase alternative.
Start your project with a Postgres database, Authentication, instant APIs, Edge Functions, Realtime subscriptions, Storage, and Vector embeddings.

- Documentation - https://supabase.com/docs
- Blog - https://supabase.com/blog
- Website - https://supabase.com/

#

```zsh
# modify .env.example
# generate new passwords
openssl rand -base64 48
# replace with new values
POSTGRES_PASSWORD=
DASHBOARD_PASSWORD=
SECRET_KEY_BASE=
VAULT_ENC_KEY=

# go to Generate API keys @ https://supabase.com/docs/guides/self-hosting/docker
# replace with new JWT
openssl rand -base64 40
JWT_SECRET=
ANON_KEY=
SERVICE_ROLE_KEY=
# replace username and password for initial login
DASHBOARD_USERNAME=
DASHBOARD_PASSWORD=

mv .env.example .env

podman-compose up -d

```

Create more users, modify volumes/api/kong.yml

```yaml
###
### Dashboard credentials
###
basicauth_credentials:
  - consumer: DASHBOARD
    username: $DASHBOARD_USERNAME
    password: $DASHBOARD_PASSWORD
  - consumer: DASHBOARD
    username: some_user_1
    password: somepass
  - consumer: DASHBOARD
    username: some_user_2
    password: somepass
```

```zsh
# Stop and remove the containers
podman compose down

# Recreate and start the containers
podman compose up -d
```

http://localhost:8000

username: "DASHBOARD_USERNAME="

password: "DASHBOARD_PASSWORD="
