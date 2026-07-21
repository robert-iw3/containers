#!/bin/sh
# UAT / smoke test for the FreeIPA stack.
#
#   ./run-uat.sh [--down]
#
# Runs a single freeipa-server container (rootless podman, high ports),
# waits for ipa-server-install to finish (10+ minutes on first run),
# asserts the Web UI answers, provisions a demo user, then proves the
# directory-integration path an application would use: an LDAPS (TLS)
# simple bind + search against FreeIPA. The container stays up for
# manual login; --down removes it.
#
# Browser access needs a hosts entry:  127.0.0.1  ipa.uat.test
set -u

cd "$(dirname "$0")"

NAME=freeipa-uat
IMAGE=quay.io/freeipa/freeipa-server:almalinux-10
HOSTNAME_FQDN=ipa.uat.test
REALM=UAT.TEST
BASEDN="dc=uat,dc=test"
HTTPS_PORT=8453
LDAPS_PORT=8636

PASS=0
FAIL=0

say() { printf '%s\n' "$*"; }

check() { # check <expected_code> <description> [curl args...]
    _want="$1"; _desc="$2"; shift 2
    _got="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$@")"
    if [ "$_got" = "$_want" ]; then
        PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "$_desc" "$_got"
    else
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s got %s want %s\n' "$_desc" "$_got" "$_want"
    fi
}

if [ "${1:-}" = "--down" ]; then
    podman rm -f "$NAME" 2>/dev/null
    rm -rf ipa-data
    exit 0
fi

say "== freeipa UAT"

if [ ! -f .uat-password ]; then
    openssl rand -base64 15 | tr -d '/+=' > .uat-password
    chmod 600 .uat-password
fi
ADMIN_PW="$(cat .uat-password)"

if ! podman container exists "$NAME" 2>/dev/null; then
    say "-- starting freeipa-server (install takes 10+ minutes)"
    mkdir -p ipa-data
    podman run -d --name "$NAME" \
        -h "$HOSTNAME_FQDN" \
        --read-only \
        -v "$(pwd)/ipa-data:/data:Z" \
        -e PASSWORD="$ADMIN_PW" \
        -p "127.0.0.1:$HTTPS_PORT:443" \
        -p "127.0.0.1:8480:80" \
        -p "127.0.0.1:$LDAPS_PORT:636" \
        --sysctl net.ipv6.conf.all.disable_ipv6=0 \
        "$IMAGE" \
        ipa-server-install -U -r "$REALM" --no-ntp --skip-mem-check || exit 1
fi

say "-- waiting for ipa-server-install (up to 20 min)"
_i=0
while [ "$_i" -lt 1200 ]; do
    if [ "$(podman logs "$NAME" 2>&1 | grep -c 'FreeIPA server configured')" -ge 1 ]; then
        break
    fi
    if [ "$(podman inspect --format '{{.State.Running}}' "$NAME" 2>/dev/null)" != "true" ]; then
        say "!! container exited during install"
        podman logs --tail 25 "$NAME" 2>&1 | sed 's/^/     /'
        exit 1
    fi
    _i=$((_i + 15)); sleep 15
done
if [ "$_i" -ge 1200 ]; then
    say "!! install did not finish in 20 min"
    podman logs --tail 25 "$NAME" 2>&1 | sed 's/^/     /'
    exit 1
fi

# Give the services a moment to finish coming up after the marker line.
sleep 10

say "-- provisioning demo user (kinit admin; ipa user-add)"
DEMO_USER=demo
DEMO_PW="$(openssl rand -base64 12 | tr -d '/+=')Aa1!"
podman exec "$NAME" bash -c "
    echo '$ADMIN_PW' | kinit admin >/dev/null 2>&1 &&
    (ipa user-show $DEMO_USER >/dev/null 2>&1 ||
     ipa user-add $DEMO_USER --first=Demo --last=User --password <<'EOF'
$DEMO_PW
$DEMO_PW
EOF
    )
" >/dev/null 2>&1 && say "   demo user ready" || say "   (demo user step reported an issue; continuing)"

say "== checks"
check 200 "web UI login page" -k -H "Host: $HOSTNAME_FQDN" "https://127.0.0.1:$HTTPS_PORT/ipa/ui/"

# Directory integration proof: an application performs an LDAPS (TLS)
# simple bind as the admin service identity and searches for the demo
# user. This is the exact path apps use to authenticate/look up users
# against FreeIPA. Run ldapsearch from inside the server container (it
# has the tools and trusts its own CA).
say "-- LDAPS bind + search (application integration path)"
LDAP_OUT="$(podman exec "$NAME" bash -lc "
    LDAPTLS_REQCERT=demand ldapsearch -x -H ldaps://$HOSTNAME_FQDN:636 \
        -D 'uid=admin,cn=users,cn=accounts,$BASEDN' -w '$ADMIN_PW' \
        -b 'cn=users,cn=accounts,$BASEDN' '(uid=$DEMO_USER)' uid 2>&1
")"
if printf '%s' "$LDAP_OUT" | grep -q "uid: $DEMO_USER"; then
    PASS=$((PASS + 1)); printf '  PASS  %-58s %s\n' "LDAPS bind + search returns demo user" "OK"
else
    FAIL=$((FAIL + 1)); printf '  FAIL  %-58s %s\n' "LDAPS bind + search returns demo user" "see log"
    printf '%s\n' "$LDAP_OUT" | tail -5 | sed 's/^/     /'
fi

say ""
say "== result: $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
    say ""
    say "Add to /etc/hosts:  127.0.0.1  $HOSTNAME_FQDN"
    say "Web UI login:  https://$HOSTNAME_FQDN:$HTTPS_PORT/ipa/ui/"
    say "  admin:     admin / $ADMIN_PW"
    say "  demo user: $DEMO_USER / $DEMO_PW (must change password on first login)"
    say "App integration (LDAPS):  ldaps://$HOSTNAME_FQDN:$LDAPS_PORT  base $BASEDN"
    say "Tear down:  ./run-uat.sh --down"
fi
[ "$FAIL" -eq 0 ]
