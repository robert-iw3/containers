#!/usr/bin/env bash
# One-command bring-up of the dev portal stack: build, start, provision
# (Vault, Boundary, Gitea), then run the full UAT battery.
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE="${COMPOSE:-podman-compose}"

if [ ! -s .env ]; then
  echo "==> generating .env with random secrets"
  cat > .env <<EOF
PG_SUPER_PASSWORD=$(openssl rand -hex 24)
BOOTSTRAP_DB_PASSWORD=$(openssl rand -hex 24)
BOUNDARY_PG_PASSWORD=$(openssl rand -hex 24)
PORTAL_KMS_ROOT_KEY=$(openssl rand -base64 32)
PORTAL_KMS_WORKER_KEY=$(openssl rand -base64 32)
PORTAL_KMS_RECOVERY_KEY=$(openssl rand -base64 32)
PORTAL_PUBLIC_ADDR=boundary:9202
UAT_STATIC_TOKEN=$(openssl rand -hex 32)
PORTAL_SESSION_SECRET=$(openssl rand -hex 32)
GITEA_ADMIN_USER=portal-admin
GITEA_ADMIN_PASSWORD=$(openssl rand -hex 16)
KC_ADMIN_PASSWORD=$(openssl rand -hex 16)
KC_DB_PASSWORD=$(openssl rand -hex 24)
PORTAL_DEV_PASSWORD=$(openssl rand -hex 12)
EOF
  chmod 600 .env
fi

# podman-compose's dependency engine races service_completed_successfully
# conditions and can even create a dependency container with corrupted env
# interpolation. Bring the stack up in explicit stages instead, so every
# container is created exactly once from its direct service listing.
# --no-recreate: a compose-file edit must never let podman-compose tear
# down dependent chains mid-run; converge stopped containers explicitly
up() { $COMPOSE up -d --no-recreate "$@" 2>&1 | grep -vE 'already in use|^$' || true; }

# podman-compose cannot adopt containers from a previous partial run and
# rootless restart policies don't always fire — force each stage's
# containers into a running state so reruns converge.
ensure_running() { # ensure_running <container...>
  for c in "$@"; do
    [ "$(podman inspect --format '{{.State.Status}}' "$c" 2>/dev/null)" = "running" ] \
      || podman start "$c" >/dev/null
  done
}

rerun_failed_oneshot() { # rerun a one-shot only if it never succeeded
  for c in "$@"; do
    state=$(podman inspect --format '{{.State.Status}} {{.State.ExitCode}}' "$c" 2>/dev/null || echo missing)
    case "$state" in
      "exited 0") ;;
      running*) ;;
      *) podman start "$c" >/dev/null 2>&1 || true ;;
    esac
  done
}

wait_exit() { podman wait "$@" >/dev/null; }

wait_healthy() { # wait_healthy <container...>
  for c in "$@"; do
    for _ in $(seq 1 90); do
      [ "$(podman inspect --format '{{.State.Health.Status}}' "$c" 2>/dev/null)" = "healthy" ] && continue 2
      sleep 4
    done
    echo "FAIL: $c never became healthy"; podman logs --tail 20 "$c"; exit 1
  done
}

echo "==> building images (portal + consul/vault/boundary contexts)"
$COMPOSE build

echo "==> stage 1: stack CA + Vault certs"
up portal-certs-init vault-certs-init
wait_exit backstage-portal-certs-init backstage-vault-certs-init

echo "==> stage 2: core services (consul, databases, gitea, vault, keycloak)"
up consul postgres boundary-db gitea vault keycloak
ensure_running backstage-consul backstage-postgres backstage-boundary-db \
  backstage-gitea backstage-vault backstage-keycloak
wait_healthy backstage-consul backstage-postgres backstage-boundary-db \
  backstage-gitea backstage-vault backstage-keycloak

echo "==> stage 3: sidecars, backup, secrets + identity provisioning, boundary"
up postgres-sidecar gitea-sidecar backstage-sidecar pgbackup vault-setup boundary keycloak-setup
ensure_running backstage-postgres-sidecar backstage-gitea-sidecar \
  backstage-portal-sidecar backstage-pgbackup backstage-boundary
rerun_failed_oneshot backstage-vault-setup backstage-keycloak-setup
wait_healthy backstage-boundary
for c in backstage-vault-setup backstage-keycloak-setup; do
  rc=$(podman wait "$c")
  [ "$rc" = "0" ] || { echo "FAIL: $c exited $rc"; podman logs --tail 15 "$c"; exit 1; }
done

# the portal blocks at boot until every secret it needs is in Vault, so all
# provisioning must land before stage 4
echo "==> provisioning Gitea (admin, org, seed dev project -> Vault kv)"
./scripts/gitea-setup.sh

echo "==> provisioning identity (Keycloak client secret -> Vault kv)"
./scripts/idp-setup.sh

echo "==> stage 4: boundary provisioning + portal deployment A"
up boundary-setup backstage-a
rerun_failed_oneshot backstage-boundary-setup
ensure_running backstage-portal-a
wait_healthy backstage-portal-a

echo "==> stage 5: portal deployment B + routing proxy"
up backstage-b portal-proxy
ensure_running backstage-portal-b backstage-portal-proxy
wait_healthy backstage-portal-b backstage-portal-proxy

echo "==> running UAT battery"
./scripts/smoke-test.sh

echo "==> opening the end-user portal session"
./scripts/portal-session.sh

cat <<'EOF'

Portal is up. TLS everywhere (stack CA: ./.portal-ca.crt).

End users:  https://127.0.0.1:27007  (Boundary-brokered session — the portal
            itself publishes no port; SSO login: portal-dev, password in .env)

Operator entry points:
  Consul UI    https://localhost:28500/ui      (catalog, mesh, intentions)
  Vault UI     https://localhost:28200/ui      (root token: /portal-state/vault-init.json)
  Boundary     https://localhost:29200         (admin creds: printed by UAT)
  Keycloak     https://localhost:28443         (admin / KC_ADMIN_PASSWORD)
  Gitea        https://localhost:23000         (dev project storage; creds in .env)

DBA flow (short-lived Vault credentials, brokered by Boundary):
  boundary connect postgres -addr https://localhost:29200 \
      -target-id <db ttcp_...> -dbname backstage_plugin_catalog
(the UAT battery prints all IDs)
EOF
