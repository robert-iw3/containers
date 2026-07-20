#!/usr/bin/env bash
# Deploy one role to one host over SSH (root or passwordless-sudo user):
#
#   ./deploy.sh <mesh|data|scm|secrets|identity|access|portal> <ssh-host> [--prep]
#
# Renders the role's templates against hosts.env, installs quadlet units to
# /etc/containers/systemd, config to /etc/backstage-portal, reloads systemd,
# and starts the units. --prep runs host-prep/prep-host.sh first.
#
# Prereqs on your side: hosts.env filled in; per-host TLS material staged at
# /etc/backstage-portal/tls on each target (ca.crt + <service>.crt/.key from
# your PKI — see README for required SANs); images pushed to ${REGISTRY}.
set -euo pipefail

cd "$(dirname "$0")"

ROLE=${1:?usage: deploy.sh <role> <ssh-host> [--prep]}
HOST=${2:?usage: deploy.sh <role> <ssh-host> [--prep]}
PREP=${3:-}

[ -d "quadlet/$ROLE" ] || { echo "unknown role: $ROLE"; exit 1; }
[ -s hosts.env ] || { echo "hosts.env missing (cp hosts.env.example hosts.env)"; exit 1; }

set -a; . ./hosts.env; set +a

# deploy-time variables; anything else in a template (e.g. Backstage's
# runtime ${POSTGRES_USER}) must survive rendering untouched
RENDER_VARS='$REGISTRY $MESH_HOST $MESH_ADVERTISE_IP $DATA_HOST $DATA_ADVERTISE_IP
$SCM_HOST $SCM_ADVERTISE_IP $PORTAL_HOST $PORTAL_ADVERTISE_IP $SECRETS_HOST
$IDENTITY_HOST $ACCESS_HOST $BOUNDARY_PUBLIC_ADDR $KEYCLOAK_PUBLIC_URL
$PORTAL_PUBLIC_URL $PG_SUPER_PASSWORD $BOOTSTRAP_DB_PASSWORD
$BOUNDARY_PG_PASSWORD $KC_DB_PASSWORD $KC_ADMIN_PASSWORD $PORTAL_KMS_ROOT_KEY
$PORTAL_KMS_WORKER_KEY $PORTAL_KMS_RECOVERY_KEY $BACKSTAGE_API_TOKEN
$AUTH_SESSION_SECRET'

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/systemd" "$STAGE/config"

echo "==> rendering role '$ROLE'"
cp quadlet/portal.network "$STAGE/systemd/"
for f in quadlet/"$ROLE"/*; do
  base=$(basename "$f")
  case "$base" in
    config) ;;
    *.env.template)
      envsubst "$RENDER_VARS" < "$f" > "$STAGE/config/${base%.template}" ;;
    *.container|*.volume|*.network)
      sed "s|__REGISTRY__|$REGISTRY|g" "$f" > "$STAGE/systemd/$base" ;;
  esac
done
if [ -d "quadlet/$ROLE/config" ]; then
  mkdir -p "$STAGE/config/$ROLE-config"
  for f in quadlet/"$ROLE"/config/*; do
    base=$(basename "$f")
    case "$base" in
      *.template) envsubst "$RENDER_VARS" < "$f" > "$STAGE/config/$ROLE-config/${base%.template}" ;;
      *)          cp "$f" "$STAGE/config/$ROLE-config/$base" ;;
    esac
  done
fi
# shared source-of-truth files some roles need
case "$ROLE" in
  data)   cp ../postgres/pg_hba.conf "$STAGE/config/$ROLE-config/" ;;
  portal) cp ../proxy/nginx.conf "$STAGE/config/$ROLE-config/" ;;
esac

if [ "$PREP" = "--prep" ]; then
  echo "==> host prep on $HOST"
  rsync -a host-prep/ "$HOST":/tmp/portal-host-prep/
  ssh "$HOST" "bash /tmp/portal-host-prep/prep-host.sh $ROLE"
fi

echo "==> installing on $HOST"
rsync -a "$STAGE/systemd/" "$HOST":/etc/containers/systemd/
rsync -a "$STAGE/config/" "$HOST":/tmp/portal-config-stage/
ssh "$HOST" bash -s "$ROLE" <<'REMOTE'
set -euo pipefail
ROLE=$1
mkdir -p /etc/backstage-portal
# env files
find /tmp/portal-config-stage -maxdepth 1 -name '*.env' -exec install -m 0600 {} /etc/backstage-portal/ \;
# role config tree
if [ -d "/tmp/portal-config-stage/$ROLE-config" ]; then
  case "$ROLE" in
    mesh)    dest=consul ;;
    data)    dest=postgres ;;
    scm)     dest=consul-agent ;;
    secrets) dest=vault ;;
    access)  dest=boundary ;;
    portal)  dest="" ;;   # split below
    *)       dest=$ROLE ;;
  esac
  if [ "$ROLE" = "portal" ]; then
    mkdir -p /etc/backstage-portal/{consul-agent,backstage,proxy}
    for f in agent.json services.json; do
      [ -f "/tmp/portal-config-stage/portal-config/$f" ] && install -m 0644 "/tmp/portal-config-stage/portal-config/$f" /etc/backstage-portal/consul-agent/
    done
    [ -f /tmp/portal-config-stage/portal-config/app-config.production.yaml ] \
      && install -m 0640 /tmp/portal-config-stage/portal-config/app-config.production.yaml /etc/backstage-portal/backstage/app-config.yaml
    [ -f /tmp/portal-config-stage/portal-config/nginx.conf ] \
      && install -m 0644 /tmp/portal-config-stage/portal-config/nginx.conf /etc/backstage-portal/proxy/
    mkdir -p /etc/backstage-portal/state
  elif [ "$ROLE" = "data" ]; then
    mkdir -p /etc/backstage-portal/postgres /etc/backstage-portal/consul-agent
    for f in init-portal-db.sh pg_hba.conf; do
      install -m 0644 "/tmp/portal-config-stage/data-config/$f" /etc/backstage-portal/postgres/
    done
    for f in agent.json services.json; do
      [ -f "/tmp/portal-config-stage/data-config/$f" ] && install -m 0644 "/tmp/portal-config-stage/data-config/$f" /etc/backstage-portal/consul-agent/
    done
  else
    mkdir -p "/etc/backstage-portal/$dest"
    cp -r /tmp/portal-config-stage/"$ROLE"-config/. "/etc/backstage-portal/$dest/"
  fi
fi
rm -rf /tmp/portal-config-stage /tmp/portal-host-prep
[ -d /etc/backstage-portal/tls ] && [ -s /etc/backstage-portal/tls/ca.crt ] \
  || echo "WARNING: /etc/backstage-portal/tls is not populated — stage your PKI material before starting"
systemctl daemon-reload
# start every unit this role installed
for u in /etc/containers/systemd/*.container; do
  svc=$(basename "$u" .container).service
  systemctl start "$svc" || true
done
systemctl --no-pager --type=service --state=running list-units 'portal-*' || true
REMOTE

echo "deploy: DONE ($ROLE -> $HOST)"
