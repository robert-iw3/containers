#!/bin/sh
# Select a Salt role from SALT_ROLE and write its config from the
# environment before starting the daemon(s).
#
#   SALT_ROLE=master-api  salt-master + salt-api (sharedsecret eauth, plain
#                         HTTP on 8000; traefik terminates TLS)
#   SALT_ROLE=minion      salt-minion pointed at SALT_MASTER
set -eu

mkdir -p /etc/salt/master.d /etc/salt/minion.d

if [ "${SALT_ROLE:-master-api}" = "minion" ]; then
    cat > /etc/salt/minion.d/uat.conf <<EOF
master: ${SALT_MASTER:-salt}
id: ${SALT_MINION_ID:-uat-minion}
EOF
    exec salt-minion -l info
fi

cat > /etc/salt/master.d/uat.conf <<EOF
auto_accept: true
# Salt 3008 disables netapi clients by default; enable the ones salt-api
# exposes so eauth'd callers can run execution, runner and wheel functions.
netapi_enable_clients:
  - local
  - local_async
  - local_subset
  - runner
  - runner_async
  - wheel
  - wheel_async
rest_cherrypy:
  port: 8000
  host: 0.0.0.0
  disable_ssl: true
external_auth:
  sharedsecret:
    ${SALT_API_USER}:
      - .*
      - '@wheel'
      - '@jobs'
      - '@runner'
sharedsecret: ${SALT_SHARED_SECRET}
EOF

salt-master -l info &
exec salt-api -l info
