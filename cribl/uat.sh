#!/usr/bin/env bash
# Acceptance test for the Cribl leader/worker stack.
#
#   ./uat.sh                 bring the stack up, assert, tear down
#   KEEP_UP=1 ./uat.sh       leave it running
#
# Each assertion here replaces something the stack previously could not tell
# you. A Cribl container reports healthy as soon as its API answers, which it
# does whether or not a worker ever registered, a Source ever loaded, or a
# single event ever moved. "Up (healthy)" is not a result.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

PASS=0; FAIL=0
declare -a FAILURES=()
ok()  { PASS=$((PASS+1)); printf '  ok    %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); FAILURES+=("$1"); printf '  FAIL  %s\n' "$1"; [[ -n "${2:-}" ]] && printf '          %s\n' "$2"; return 0; }
head2() { printf '\n=== %s ===\n' "$*"; }
num() { local v="${1:-}"; [[ "$v" =~ ^-?[0-9]+$ ]] && printf '%s' "$v" || printf '0'; }

cleanup() {
    if [[ "${KEEP_UP:-0}" == "1" ]]; then
        printf '\nKEEP_UP=1, stack left running. Tear down: podman compose -f %s/docker-compose.yml down -v\n' "$HERE"
        return
    fi
    podman compose down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Start from a true first boot. Cribl writes auth/ (cribl.secret and the admin
# password hash) into the mounted config directory; leaving that behind while
# `down -v` removes the state volume leaves a leader whose stored credentials
# no longer authenticate, and every API assertion below then fails for a
# reason that has nothing to do with the code under test.
podman compose down -v >/dev/null 2>&1 || true
rm -rf leader-config/auth leader-config/cribl.inited \
       leader-config/groups.yml leader-config/messages.yml \
       group-default/auth 2>/dev/null || true

# A generated token, never a default. Cribl's own is public knowledge.
if [[ ! -f .env ]]; then
    { echo "CRIBL_DIST_TOKEN=$(openssl rand -hex 24)"
      echo "LEADER_MEMORY=2g"; echo "WORKER_MEMORY=2g"
      echo "LEADER_CPUS=1";    echo "WORKER_CPUS=1"; } > .env
fi

head2 "release pins"
if ../ci/cribl-release-check.sh >/dev/null 2>&1; then
    ok "every Cribl pin resolves and the tree agrees on one version"
else
    bad "cribl release pins do not resolve or have drifted" "run ci/cribl-release-check.sh"
fi

head2 "certificate generator"
if python3 generate_cert.py --cn cribl.local --out-dir "$(mktemp -d)" --key-pass uat >/dev/null 2>&1; then
    ok "generate_cert.py runs (it is on the only documented deploy path)"
else
    bad "generate_cert.py fails" "the documented deploy aborts before Ansible runs"
fi

head2 "bring up, two workers"
podman compose up -d --scale workers=2 >/dev/null 2>&1
for _ in $(seq 1 60); do
    [[ "$(podman inspect -f '{{.State.Health.Status}}' cribl-leader 2>/dev/null)" == healthy ]] && break
    sleep 5
done
[[ "$(podman inspect -f '{{.State.Health.Status}}' cribl-leader 2>/dev/null)" == healthy ]] \
    && ok "leader healthy" || bad "leader never became healthy"

running=$(podman ps --format '{{.Names}}' | grep -c '_workers_' || true)
# Fixed host-port publishes on the worker service are what makes this fail:
# the second container cannot bind an already-allocated port.
if [[ "$(num "$running")" -eq 2 ]]; then
    ok "two workers started (the service publishes no host ports, so it scales)"
else
    bad "expected 2 workers, got ${running}" "host port bindings on the worker service prevent scaling"
fi

head2 "resource limits landed"
for c in cribl-leader; do
    mem="$(podman inspect -f '{{.HostConfig.Memory}}' "$c" 2>/dev/null || echo 0)"
    [[ "$(num "$mem")" -gt 0 ]] && ok "$c memory limit = $mem" \
        || bad "$c has NO memory limit" "deploy.resources.limits was dropped by the compose provider"
done

head2 "leader and workers actually connected"
api() { podman exec cribl-leader curl -s -H "Authorization: Bearer $TOK" "http://localhost:9000/api/v1/$1"; }
for _ in $(seq 1 30); do
    TOK=$(podman exec cribl-leader curl -s -X POST "http://localhost:9000/api/v1/auth/login" \
        -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin"}' 2>/dev/null \
        | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
    [[ -n "${TOK:-}" ]] && break
    sleep 5
done
[[ -n "${TOK:-}" ]] && ok "leader API authenticates" || bad "could not obtain a leader API token"

n=0
for _ in $(seq 1 30); do
    n=$(api "master/workers" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('count', len(d.get('items',[]))))" 2>/dev/null || echo 0)
    [[ "$(num "$n")" -ge 2 ]] && break
    sleep 10
done
if [[ "$(num "$n")" -ge 2 ]]; then
    ok "both workers registered with the leader (${n})"
else
    bad "only ${n} worker(s) registered" "healthy containers that never joined the leader look identical to working ones"
fi

head2 "seeded group config is loaded, not just present on disk"
# The group's config helper is spawned lazily and behind memory-pressure
# admission control, so on a loaded host it can be a couple of minutes behind
# the leader's API. Until it is up, every query answers with an error that
# reads exactly like invalid config. Treat "not available" and "not
# initalized" as NOT READY and keep waiting; a check that could not run is not
# a verdict. Anything else is a real config error and fails immediately.
helper_ready=0
for _ in $(seq 1 40); do
    body=$(api "m/default/system/inputs" 2>/dev/null)
    state=$(printf '%s' "$body" | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print('notready'); raise SystemExit
if d.get('status') != 'error': print('ready'); raise SystemExit
m = d.get('message','')
print('notready' if ('not available' in m or 'not initalized' in m or 'not initialized' in m) else 'invalid')
" 2>/dev/null)
    [[ "$state" == "ready" ]] && { helper_ready=1; break; }
    [[ "$state" == "invalid" ]] && break
    sleep 10
done
[[ "$helper_ready" == 1 ]] && ok "group config helper came up" \
    || bad "group config helper never became available" "it is spawned lazily; on a loaded host allow several minutes"

inputs=$(api "m/default/system/inputs" | python3 -c "
import json,sys
d=json.load(sys.stdin)
if d.get('status')=='error': print('ERROR:'+d.get('message','')[:80])
else: print(','.join(i['id'] for i in d.get('items',[]) if not i.get('disabled')))
" 2>/dev/null)
case "$inputs" in
  ERROR:*) bad "the group config helper rejected the config" "${inputs#ERROR:}" ;;
  *in_syslog*) ok "in_syslog loaded from group-default/inputs.yml" ;;
  *) bad "in_syslog is not enabled (got: ${inputs:-none})" ;;
esac

outputs=$(api "m/default/system/outputs" | python3 -c "
import json,sys
d=json.load(sys.stdin)
if d.get('status')=='error': print('ERROR:'+d.get('message','')[:80])
else: print(','.join(o['id'] for o in d.get('items',[])))
" 2>/dev/null)
case "$outputs" in
  ERROR:*) bad "the group config helper rejected outputs.yml" "${outputs#ERROR:}" ;;
  *out_fs*) ok "out_fs loaded from group-default/outputs.yml" ;;
  *) bad "out_fs is missing (got: ${outputs:-none})" ;;
esac

head2 "commit and deploy the group"
# Editing files under group-default/ is not enough: a worker receives config
# only after the leader commits and deploys it. Without this step the next
# assertion fails for a reason that has nothing to do with the stack.
COMMIT=$(podman exec cribl-leader curl -s -X POST -H "Authorization: Bearer $TOK" \
    -H 'Content-Type: application/json' -d '{"message":"uat seed","group":"default"}' \
    "http://localhost:9000/api/v1/version/commit" 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('items',[{}])[0].get('commit',''))" 2>/dev/null)
if [[ -n "${COMMIT:-}" ]]; then
    ok "group config committed (${COMMIT:0:12})"
    if podman exec cribl-leader curl -sf -X PATCH -H "Authorization: Bearer $TOK" \
        -H 'Content-Type: application/json' -d "{\"version\":\"$COMMIT\"}" \
        "http://localhost:9000/api/v1/master/groups/default/deploy" >/dev/null 2>&1; then
        ok "group config deployed to the workers"
    else
        bad "deploy rejected the commit" "PATCH /master/groups/default/deploy with $COMMIT"
    fi
else
    bad "nothing to commit" "the group config never reached the leader"
fi

# Give the workers time to pull and apply the bundle.
for _ in $(seq 1 30); do
    podman exec cribl_workers_1 sh -c 'grep -q "in_syslog" /opt/cribl/local/cribl/inputs.yml' 2>/dev/null && break
    sleep 10
done

head2 "config bundles apply on the workers"
# A worker applies a bundle by renaming state/distributed/bundles/<id>/local/cribl
# over /opt/cribl/local/cribl. A volume mounted on /opt/cribl/state makes those
# different filesystems and rename(2) fails with EXDEV, so the worker downloads
# every bundle, fails to apply AND to revert, and holds a stale config lock -
# while still reporting healthy.
exdev=$(podman logs cribl_workers_1 2>&1 | grep -c "EXDEV" || true)
if [[ "$(num "$exdev")" -eq 0 ]]; then
    ok "no EXDEV bundle failures (no volume on the worker's /opt/cribl/state)"
else
    bad "worker hit EXDEV ${exdev}x applying config bundles" \
        "remove the volume from the worker's /opt/cribl/state"
fi

if podman exec cribl_workers_1 sh -c 'grep -q "in_syslog" /opt/cribl/local/cribl/inputs.yml' 2>/dev/null; then
    ok "the leader's group config reached the worker's own inputs.yml"
else
    bad "the worker never received the group config" \
        "commit and deploy the group, then check for EXDEV in the worker log"
fi

head2 "end to end: does an event actually traverse a worker"
# KNOWN OPEN. Everything above passes and no event moves: the Source is
# present and enabled in the worker's applied config, but the worker binds no
# listener for it. Kept as a failing assertion rather than removed - the whole
# point of this file is that "healthy" is not the same as "working".
listen=$(podman exec cribl_workers_1 sh -c \
    'awk "NR>1{split(\$2,a,\":\"); print a[2]}" /proc/net/tcp /proc/net/tcp6 2>/dev/null' \
    | grep -c "141C" || true)
if [[ "$(num "$listen")" -gt 0 ]]; then
    ok "worker is listening on tcp/5140 for the syslog Source"
else
    bad "worker binds no listener on tcp/5140 despite in_syslog being enabled in its applied config" \
        "KNOWN OPEN: config distribution is proved above; Source activation is not"
fi

head2 "result"
printf 'passed %d  failed %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
    printf '\nfailures:\n'
    for f in "${FAILURES[@]}"; do printf '  - %s\n' "$f"; done
    exit 1
fi
printf 'ACCEPTANCE PASSED\n'
