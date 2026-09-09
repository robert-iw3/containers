#!/usr/bin/env bash
# Windows endpoints -> Cribl -> Splunk, end to end, with assertions.
#
#   ./run-lab.sh                 bring it up, drive traffic, assert, tear down
#   KEEP_UP=1 ./run-lab.sh       leave it running
#
# What this proves that "Up (healthy)" does not: that events from every mock
# endpoint reached a Splunk index, that the pipeline dropped the noise it is
# supposed to drop, that it redacted what it is supposed to redact, and that
# the rare event a volume-based sampler would lose survived.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

SOURCES="${LAB_SOURCES:-15}"
COUNT="${LAB_COUNT:-30000}"
WORK="${HERE}/work"

PASS=0; FAIL=0
declare -a FAILURES=()
ok()  { PASS=$((PASS+1)); printf '  ok    %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); FAILURES+=("$1"); printf '  FAIL  %s\n' "$1"; [[ -n "${2:-}" ]] && printf '          %s\n' "$2"; return 0; }
skip() { printf '  skip  %s\n' "$1"; }
head2() { printf '\n=== %s ===\n' "$*"; }
num() { local v="${1:-}"; [[ "$v" =~ ^-?[0-9]+$ ]] && printf '%s' "$v" || printf '0'; }

cleanup() {
    if [[ "${KEEP_UP:-0}" == "1" ]]; then
        printf '\nKEEP_UP=1, lab left running.\n  Splunk  https://127.0.0.1:%s (admin)\n  Cribl   https://127.0.0.1:%s (admin/admin)\n  down:   podman compose -f %s/compose.yaml down -v\n' \
            "${LAB_SPLUNK_WEB:-18000}" "${LAB_CRIBL_WEB:-19010}" "$HERE"
        return
    fi
    podman compose down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

mkdir -p "$WORK"

# --- credentials, generated, never defaulted ---------------------------------
if [[ ! -f .env ]]; then
    { echo "LAB_CRIBL_TOKEN=$(openssl rand -hex 24)"
      echo "LAB_SPLUNK_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)Aa1"
    } > .env
    chmod 600 .env
fi
set -a; . ./.env; set +a

# A true first boot: Cribl writes auth material into the mounted config dirs,
# and leaving it behind while the state volume is removed produces a leader
# whose stored credentials no longer authenticate.
podman compose down -v >/dev/null 2>&1 || true
rm -rf cribl-config/leader cribl-config/groups/default/auth
mkdir -p cribl-config/leader
# The leader's own settings, which enable TLS on its API and UI. Rendered
# rather than tracked: the leader writes back into this directory.
cp cribl-config/leader-cribl.yml.template cribl-config/leader/cribl.yml

# Certificates and hardened Splunk configuration, both before bring-up.
./make-certs.sh >/dev/null 2>&1 || true
../../splunk/conf/render.sh "$HERE/splunk-conf" \
    --certs /opt/splunk/etc/auth/mycerts \
    --server-name lab-splunk \
    --accept-from "127.0.0.1,10.0.0.0/8" \
    --web-port 8000 \
    --allowed-domains "example.com" >/dev/null 2>&1 || true
# The rendered names must match what make-certs.sh produced, or Splunk starts
# with SSL enabled and no usable certificate.
sed -i 's|splunk-cert-web\.pem|splunk-bundle.pem|; s|splunk-cert\.pem|splunk-bundle.pem|; s|splunk-cert\.key|splunk.key|' \
    "$HERE/splunk-conf"/*.conf 2>/dev/null || true
# requireClientCert on [splunktcp-ssl://9997] validates the forwarder's and the
# Cribl worker's certificates against sslRootCAPath. The shipped value is the
# host CA bundle, which does not contain the lab CA, so every sender would be
# refused at the handshake - and from the sending side that reads as a network
# fault rather than as a trust problem.
sed -i 's|^sslRootCAPath = .*|sslRootCAPath = /opt/splunk/etc/auth/mycerts/ca.crt|' \
    "$HERE/splunk-conf/server.conf" 2>/dev/null || true

# Render the Sources BEFORE bring-up. The leader reads its mounted config at
# start, so a file created after `compose up` is not seen and the Source is
# absent from the group - which reads as "the Source is not in the group
# config" rather than as an ordering mistake.
cp cribl-config/groups/default/inputs.yml.template \
   cribl-config/groups/default/inputs.yml

head2 "images"
if ! podman image exists "${LAB_SPLUNK_IMAGE:-localhost/splunk-lab:10.4.2}"; then
    bad "splunk image ${LAB_SPLUNK_IMAGE:-localhost/splunk-lab:10.4.2} is missing" \
        "build it: podman build -t localhost/splunk-lab:10.4.2 ../../splunk/enterprise"
    printf '\npassed %d  failed %d\n' "$PASS" "$FAIL"
    exit 1
fi
ok "splunk image present"
podman image exists "${LAB_CRIBL_IMAGE:-docker.io/cribl/cribl:4.19.2}" \
    && ok "cribl image present" || bad "cribl image missing"
# --- bring up everything except the traffic generator ------------------------
head2 "bring up splunk and cribl"
podman compose up -d splunk cribl-leader cribl-worker >/dev/null 2>&1

wait_healthy() { # wait_healthy <container> <tries>
    local c="$1" tries="${2:-60}"
    for _ in $(seq 1 "$tries"); do
        [[ "$(podman inspect -f '{{.State.Health.Status}}' "$c" 2>/dev/null)" == healthy ]] && return 0
        sleep 5
    done
    return 1
}
wait_healthy lab-splunk 90 && ok "splunk healthy" || bad "splunk never became healthy"
wait_healthy lab-cribl-leader 60 && ok "cribl leader healthy" || bad "cribl leader never became healthy"
WORKER=$(podman ps --format '{{.Names}}' | grep 'cribl-worker' | head -1)
[[ -n "$WORKER" ]] && wait_healthy "$WORKER" 60 && ok "cribl worker healthy" \
    || bad "cribl worker never became healthy"

# --- Splunk: index + HEC token ----------------------------------------------
head2 "hardened splunk configuration"
# Nothing to apply here: the entrypoint stages splunk-conf/ into system/local
# and certs/ into etc/auth/mycerts, owned by splunk, before splunkd starts.
# These assert that it happened, from splunkd's own resolved configuration.
#
# grep -c, never grep -q, on a pipe. `grep -q` exits at the first match and
# SIGPIPEs the writer; `set -o pipefail` then reports 141 and the assertion
# INVERTS - it fails precisely when the thing it looks for is present. It is
# timing-dependent on buffering, so it passes by luck when tested by hand.
webssl=$(num "$(podman exec -u splunk lab-splunk /opt/splunk/bin/splunk btool web list settings 2>/dev/null \
    | grep -c "enableSplunkWebSSL = *\(true\|1\)")")
if [[ "$webssl" -gt 0 ]]; then
    ok "hardened configuration is in splunkd's effective config (web SSL)"
else
    bad "web SSL is not in the effective configuration" \
        "the staged files never reached system/local, or splunkd did not read them"
fi

# The control that prompted this: an empty allowedDomainList lets any user
# email search results to any domain.
domains=$(num "$(podman exec -u splunk lab-splunk /opt/splunk/bin/splunk btool alert_actions list email 2>/dev/null \
    | grep -cE "^allowedDomainList = .+")")
if [[ "$domains" -gt 0 ]]; then
    ok "allowedDomainList is set (no unrestricted alert email)"
else
    bad "allowedDomainList is still empty"
fi

# The certificates have to be readable by splunkd, which runs as splunk. A
# read-only bind mount at the final path carries the host's ownership and
# leaves 0600 keys unreadable, and Splunk Web then answers nothing at all.
if podman exec -u splunk lab-splunk sh -c \
        'head -c1 /opt/splunk/etc/auth/mycerts/splunk-bundle.pem >/dev/null 2>&1 &&
         head -c1 /opt/splunk/etc/auth/mycerts/splunk.key >/dev/null 2>&1'; then
    ok "splunkd can read its certificate and key"
else
    bad "splunkd cannot read its own certificate or key" \
        "staged certs must be copied in owned by splunk, not mounted at the final path"
fi

head2 "splunk receiving configuration"
# -u splunk on every CLI call. `podman exec` defaults to root, and the CLI
# writes as whoever runs it: one root-owned etc/system/metadata/local.meta is
# enough to stop splunkd from starting again, and until then it answers HTTP
# 500 on /storage/passwords while the container still reports (healthy).
splunk_cli() { podman exec -u splunk lab-splunk /opt/splunk/bin/splunk "$@"; }
sp() { splunk_cli "$@" -auth "admin:${LAB_SPLUNK_PASSWORD}" 2>&1; }

PIPE_INDEX="${LAB_PIPE_INDEX:-enterprise}"
if sp add index "$PIPE_INDEX" >/dev/null 2>&1 || \
   [[ "$(num "$(sp list index 2>/dev/null | grep -c "^${PIPE_INDEX}\$")")" -gt 0 ]]; then
    ok "index '${PIPE_INDEX}' exists"
else
    bad "could not create the '${PIPE_INDEX}' index"
fi

# The A/B control. The forwarder's tcpout lists BOTH groups in defaultGroup, so
# Splunk itself clones every event: one copy through Cribl, one straight to the
# indexer. Both arms travel the same transport, so the comparison is not
# confounded by how each side was sent.
RESTRICTED_INDEX="${LAB_RESTRICTED_INDEX:-enterprise_restricted}"
if sp add index "$RESTRICTED_INDEX" >/dev/null 2>&1 || \
   [[ "$(num "$(sp list index 2>/dev/null | grep -c "^${RESTRICTED_INDEX}\$")")" -gt 0 ]]; then
    ok "restricted index '${RESTRICTED_INDEX}' exists (encoded commands routed here)"
else
    bad "could not create the restricted index"
fi

RAW_INDEX="${LAB_HEC_INDEX:-enterprise_raw}"
if sp add index "$RAW_INDEX" >/dev/null 2>&1 || \
   [[ "$(num "$(sp list index 2>/dev/null | grep -c "^${RAW_INDEX}\$")")" -gt 0 ]]; then
    ok "control index '${RAW_INDEX}' exists (unfiltered baseline)"
else
    bad "could not create the '${RAW_INDEX}' control index"
fi

# curl is not in the Splunk image (no wget or nc either), so every HEC step goes
# through the bundled CLI. `podman exec lab-splunk curl ...` fails with
# "executable file `curl` not found", which presents as an API error.
splunk_cli http-event-collector create cribl \
    -index "$PIPE_INDEX" -uri https://127.0.0.1:8089 \
    -auth "admin:${LAB_SPLUNK_PASSWORD}" >/dev/null 2>&1 || true

HEC_TOKEN=$(splunk_cli http-event-collector list cribl \
    -uri https://127.0.0.1:8089 -auth "admin:${LAB_SPLUNK_PASSWORD}" 2>/dev/null \
    | sed -n 's/.*token=\([0-9a-fA-F-]\{36\}\).*/\1/p' | head -1)
[[ -n "$HEC_TOKEN" ]] && ok "HEC token created (${HEC_TOKEN:0:8}...)" \
    || bad "could not create a HEC token"

splunk_cli http-event-collector enable \
    -uri https://127.0.0.1:8089 -auth "admin:${LAB_SPLUNK_PASSWORD}" >/dev/null 2>&1 \
    && ok "HEC endpoint enabled" || bad "could not enable the HEC endpoint"

head2 "cribl configuration"
# Copy the template to the (gitignored) outputs.yml the leader mounts. The
# Destination authenticates with a client certificate, so there is no token to
# render into it. The HEC token above is for the CONTROL arm only, which the
# emitter uses to send an unfiltered copy straight to Splunk.
cp cribl-config/groups/default/outputs.yml.template \
   cribl-config/groups/default/outputs.yml
if grep -qE "type: *splunk_lb" cribl-config/groups/default/outputs.yml; then
    ok "Destination is splunk_lb (cooked S2S, client-certificate auth)"
else
    bad "the Destination did not render as splunk_lb"
fi

# Splunk has to be receiving on 9997 with TLS before the Destination connects.
# The receiver comes from the staged inputs.conf, not from `splunk enable
# listen` - which writes a PLAINTEXT [splunktcp://9997] into the search app
# that the TLS stanza does not override.
recv=$(num "$(podman exec -u splunk lab-splunk sh -c \
    "grep -c 'Acceptor for IPv4 port 9997 with SSL' /opt/splunk/var/log/splunk/splunkd.log" 2>/dev/null)")
if [[ "$recv" -gt 0 ]]; then
    ok "Splunk receives on tcp/9997 with SSL and a required client certificate"
else
    bad "Splunk opened no SSL acceptor on 9997" \
        "the staged inputs.conf [splunktcp-ssl://9997] did not take effect"
fi

# Validate the rendered Destinations against the image's own schema BEFORE
# deploying. Cribl reports a bad key only as "Output config validation failed
# during startup", names nothing, and one invalid key disables EVERY output in
# the file - which surfaces downstream as "nothing reached the index" and sends
# you hunting the wrong leg.
if podman cp lab-cribl-leader:/opt/cribl/default/ui/static/swagger/openapi.json.gz \
        "$WORK/openapi.json.gz" 2>/dev/null && gunzip -f "$WORK/openapi.json.gz"; then
    if python3 - "$WORK/openapi.json" cribl-config/groups/default/outputs.yml \
            cribl-config/groups/default/inputs.yml <<'PYIN'
import json, sys, yaml
schemas = json.load(open(sys.argv[1]))["components"]["schemas"]
docs = [yaml.safe_load(open(p)) or {} for p in sys.argv[2:]]
kind = {"splunk_hec": "OutputSplunkHec", "filesystem": "OutputFilesystem",
        "splunk": "OutputSplunk", "splunk_lb": "OutputSplunkLb", "devnull": None}
# Sources are checked with the same code and the same schema. The enum defect
# that cost a run was in a Source, which this check did not look at at all.
in_kind = {"splunk": "InputSplunk", "syslog": "InputSyslog", "tcpjson": "InputTcpjson",
           "splunk_hec": "InputSplunkHec", "tcp": "InputTcp", "http": "InputHttp"}
bad = []
entries = []
for doc in docs:
    for name, o in (doc.get("outputs") or {}).items():
        entries.append((name, o, kind))
    for name, o in (doc.get("inputs") or {}).items():
        entries.append((name, o, in_kind))
for name, o, kindmap in entries:
    s = schemas.get(kindmap.get(o.get("type")) or "")
    if not s:
        continue
    props = s.get("properties", {})
    bad += [f"{name}.{k} is not a key of {o['type']}" for k in o if k not in props]
    bad += [f"{name} is missing required {k}" for k in s.get("required", []) if k not in o]
    # A key can exist and still hold a value the schema forbids. Cribl reports
    # that as "should be equal to one of the allowed values" with no key name,
    # and the Source silently binds no listener.
    for k, v in o.items():
        spec = props.get(k) or {}
        ref = (spec.get("$ref") or "").split("/")[-1]
        spec = schemas.get(ref, spec) if ref else spec
        allowed = spec.get("enum")
        if allowed and not isinstance(v, (dict, list)) and v not in allowed:
            bad.append(f"{name}.{k} = {v!r} is not one of {allowed}")
    # Key existence is not enough: `urls` is read only when loadBalanced is
    # true, so a Destination carrying `urls` with the default false has no URL
    # at all and dies with "URL must start with http or https".
    # splunk_hec needs a URL; splunk_lb needs hosts. `urls` is read only when
    # loadBalanced is true, so a HEC Destination carrying `urls` with the
    # default false has no URL at all and dies with "URL must start with http".
    if kindmap is kind:
        if o.get("type") == "splunk_hec":
            if not o.get("url") and not (o.get("loadBalanced") and o.get("urls")):
                bad.append(f"{name} has no usable URL: set `url`, or `loadBalanced: true` with `urls`")
        if o.get("type") in ("splunk_lb", "splunk") and not o.get("hosts"):
            bad.append(f"{name} has no hosts")
for b in bad:
    print(b)
sys.exit(1 if bad else 0)
PYIN
    then
        ok "Destinations validate against the image's own schema"
    else
        bad "a Source or Destination fails the image schema (listed above)" \
            "one bad key disables every output in the file"
    fi
else
    skip "schema validation (could not read the image's OpenAPI)"
fi

TOK=""
for _ in $(seq 1 60); do
    TOK=$(podman exec lab-cribl-leader curl -sk -X POST "https://localhost:9000/api/v1/auth/login" \
        -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin"}' 2>/dev/null \
        | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
    [[ -n "$TOK" ]] && break
    sleep 5
done
[[ -n "$TOK" ]] && ok "cribl leader API authenticates" || bad "no cribl API token"

api() { podman exec lab-cribl-leader curl -sk -H "Authorization: Bearer $TOK" "https://localhost:9000/api/v1/$1"; }

# The group's config helper is spawned lazily; until it is up every query
# reads exactly like invalid config. Waiting is not the same as passing.
for _ in $(seq 1 40); do
    state=$(api "m/default/system/inputs" 2>/dev/null | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print('notready'); raise SystemExit
if d.get('status')!='error': print('ready'); raise SystemExit
m=d.get('message','')
print('notready' if ('not available' in m or 'nitalized' in m or 'nitialized' in m) else 'invalid')" 2>/dev/null)
    [[ "$state" == "ready" ]] && break
    [[ "$state" == "invalid" ]] && break
    sleep 10
done
[[ "$state" == "ready" ]] && ok "group config helper up" \
    || bad "group config helper never came up (state=${state:-unknown})"

[[ "$(num "$(api "m/default/system/inputs" | grep -c "in_win_tcpjson")")" -gt 0 ]] \
    && ok "tcpjson Source loaded from the group config" \
    || bad "in_win_tcpjson is not in the group config"

COMMIT=$(podman exec lab-cribl-leader curl -sk -X POST -H "Authorization: Bearer $TOK" \
    -H 'Content-Type: application/json' -d '{"message":"lab seed","group":"default"}' \
    "https://localhost:9000/api/v1/version/commit" 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('items',[{}])[0].get('commit',''))" 2>/dev/null)
if [[ -n "$COMMIT" ]]; then
    podman exec lab-cribl-leader curl -skf -X PATCH -H "Authorization: Bearer $TOK" \
        -H 'Content-Type: application/json' -d "{\"version\":\"$COMMIT\"}" \
        "https://localhost:9000/api/v1/master/groups/default/deploy" >/dev/null 2>&1 \
        && ok "config committed and deployed (${COMMIT:0:12})" \
        || bad "deploy rejected the commit"
else
    bad "nothing to commit"
fi

# The worker must actually open the Source port before traffic is sent.
# 10060 is 0x274C in /proc/net/tcp.
listening=0
for _ in $(seq 1 40); do
    hits=$(num "$(podman exec "$WORKER" sh -c \
        'awk "NR>1{split(\$2,a,\":\"); print a[2]}" /proc/net/tcp /proc/net/tcp6 2>/dev/null' \
        | grep -c "274C")")
    if [[ "$hits" -gt 0 ]]; then
        listening=1; break
    fi
    sleep 10
done
if [[ "$listening" == 1 ]]; then
    ok "worker is listening on tcp/10060 for the Source"
else
    bad "worker never opened tcp/10060" \
        "the Source is in its applied config; without the listener no endpoint can connect"
fi

# The leader-to-worker link carries the group bundle, which is outputs.yml
# verbatim - every Destination credential, once per worker, on every deploy.
# `tls://` in CRIBL_DIST_LEADER_URL is the only thing that encrypts it, and a
# stack on `tcp://` is fully functional, so nothing else shows this.
tlsoff=$(num "$(podman exec "$WORKER" sh -c \
    'sed -n "/^    tls:/,/^    [a-z]/p" /opt/cribl/local/_system/instance.yml' 2>/dev/null \
    | grep -c "disabled: true")")
if [[ "$tlsoff" -eq 0 ]]; then
    ok "leader-to-worker channel is TLS"
else
    skip "leader-to-worker channel is plaintext (documented limitation, see README)"
fi

exdev=$(podman logs "$WORKER" 2>&1 | grep -c EXDEV || true)
[[ "$(num "$exdev")" -eq 0 ]] && ok "no EXDEV bundle failures" \
    || bad "worker hit EXDEV ${exdev}x" "a volume on the worker's /opt/cribl/state breaks every config apply"

# --- traffic -----------------------------------------------------------------
head2 "log sources"
# Exported, not written into the compose file: the token is created at run time
# and must never land in a tracked file.
export LAB_HEC_URL="https://splunk:8088/services/collector/event"
export LAB_HEC_TOKEN="$HEC_TOKEN"
export LAB_HEC_INDEX="$RAW_INDEX"
podman compose up -d endpoints >/dev/null 2>&1
GEN=$(podman ps -a --format '{{.Names}}' | grep endpoints | head -1)
for _ in $(seq 1 60); do
    st=$(podman inspect -f '{{.State.Status}}' "$GEN" 2>/dev/null || echo gone)
    [[ "$st" == "exited" ]] && break
    sleep 5
done
podman logs "$GEN" > "$WORK/generator.log" 2>&1 || true
sent=$(num "$(grep -oE '^dataset_total events=[0-9]+' "$WORK/generator.log" | grep -oE '[0-9]+$' | tail -1)")
raw_bytes=$(num "$(grep -oE '^dataset_total events=[0-9]+ bytes=[0-9]+' "$WORK/generator.log" \
    | grep -oE 'bytes=[0-9]+' | cut -d= -f2 | tail -1)")
if [[ "$(num "$sent")" -ge "$COUNT" ]]; then
    ok "${SOURCES} sources emitted ${sent} records"
else
    bad "generator sent ${sent:-0}, expected ${COUNT}" "$(tail -3 "$WORK/generator.log" | tr '\n' ' ')"
fi

# The sender leg must be mutual TLS. The Source sets requestCert with
# rejectUnauthorized, so a client without a certificate fails the handshake —
# but a Source whose tls block was dropped accepts plaintext and everything
# downstream still passes.
tls_leg=$(num "$(grep -c "over tls" "$WORK/generator.log")")
if [[ "$tls_leg" -gt 0 ]]; then
    ok "senders connected over mutual TLS"
else
    bad "senders connected in the clear" \
        "the Source's tls block or the client certificate is missing"
fi

printf '  waiting for the pipeline to drain'
for _ in $(seq 1 12); do printf '.'; sleep 5; done; printf '\n'

# --- what actually landed in Splunk ------------------------------------------
head2 "end to end: what reached the Splunk index"
# Every helper guards its arguments. Under `set -u` a bare $1 in a function
# aborts the whole run the moment one is called without one, and the error
# names the function's line rather than the caller's - which reads like a bug
# in the assertion instead of in the call.
# -output csv, NOT rawdata. `rawdata` fails on any result without a _raw
# field - which every `stats` result is - with "result had no _raw key". The
# helper then returns nothing, every count reads 0, and a WORKING pipeline is
# reported as "nothing reached the index". The check could not run; that is
# not a verdict.
spl() { # spl <search> - returns CSV rows
    local q="${1:-}"
    [[ -n "$q" ]] || return 0
    podman exec -u splunk lab-splunk /opt/splunk/bin/splunk search "$q" -maxout 0 -output csv \
        -auth "admin:${LAB_SPLUNK_PASSWORD}" 2>/dev/null | grep -v '^WARNING'
}
count_of() { # count_of <search> - the single number a `stats count` returns
    local q="${1:-}" out
    [[ -n "$q" ]] || { printf '0\n'; return 0; }
    out="$(spl "$q | stats count")"
    # CSV: a header line then the value. Empty result set means zero.
    printf '%s\n' "$out" | tail -1 | tr -d '"' | grep -oE '^[0-9]+$' || printf '0\n'
}

# Before any count below means anything, the indexer has to be indexing and
# this account has to be able to search. Both fail silently and both look
# identical from here - "nothing reached the pipeline index" - so separate them:
#
#   index_thruput ev=0   nothing reaches the index writer. outputs.conf
#                        [indexAndForward] selectiveIndexing = true does this:
#                        HEC still answers 200 and every event is discarded.
#   ev>0 but no results  the events are indexed and this role cannot see them.
#                        authorize.conf srchIndexesAllowed is the usual cause.
indexed_ev=$(num "$(podman exec -u splunk lab-splunk sh -c \
    "awk -F'ev=' '/name=index_thruput/ {s+=\$2} END {printf \"%d\", s}' \
     /opt/splunk/var/log/splunk/metrics.log" 2>/dev/null)")
internal=$(num "$(count_of 'index=_internal earliest=-15m')")
if [[ "$indexed_ev" -eq 0 ]]; then
    bad "the indexer indexed nothing at all, not even its own logs" \
        "index_thruput ev=0: events are being routed away before the index writer"
elif [[ "$internal" -eq 0 ]]; then
    bad "events are indexed but this account cannot search them" \
        "index_thruput counted ${indexed_ev} events while index=_internal returns none"
else
    ok "the indexer is indexing and admin can search it (_internal: ${internal})"
fi

# From here on the searches interpolate $PIPE_INDEX, so they are double
# quoted. A single-quoted search containing ${PIPE_INDEX} reaches Splunk as the
# literal string and returns nothing, which reads as an empty index.
total=$(num "$(count_of "index=${PIPE_INDEX} earliest=-1h")")
if [[ "$total" -gt 0 ]]; then
    ok "events reached the pipeline index (${total})"
else
    bad "nothing reached the pipeline index" "the whole path is broken somewhere upstream"
fi

# Every source must be represented. A route filter that does not match sends a
# whole feed to the unmatched capture file, and on a totals dashboard that is
# invisible.
SOURCES_EXPECTED="$SOURCES"
src_seen=$(num "$(spl "index=${PIPE_INDEX} earliest=-1h | stats dc(sourcetype) as n" \
    | tail -1 | tr -d '"' | grep -oE '^[0-9]+$')")
if [[ "$src_seen" -ge "$SOURCES_EXPECTED" ]]; then
    ok "all ${SOURCES_EXPECTED} sources are represented after reduction"
else
    bad "only ${src_seen} of ${SOURCES_EXPECTED} sources reached Splunk" \
        "a route that claims nothing sends its whole feed to the unmatched file"
fi

# The unmatched capture must be empty. It is the only thing that distinguishes
# "the routes are right" from "everything fell through to the catch-all".
unmatched=$(num "$(podman exec "$WORKER" sh -c \
    'find /opt/cribl/state/dropped -type f 2>/dev/null | wc -l')")
if [[ "$unmatched" -eq 0 ]]; then
    ok "no events fell through to the unmatched route"
else
    bad "${unmatched} unmatched capture files on the worker" \
        "a sourcetype no route claims; check route.yml filters against the emitter"
fi

hosts=$(num "$(spl "index=${PIPE_INDEX} earliest=-1h | stats dc(host) as n" \
    | tail -1 | tr -d '"' | grep -oE '^[0-9]+$')")
[[ "$hosts" -ge 20 ]] && ok "${hosts} distinct hosts represented" \
    || bad "only ${hosts} distinct hosts reached Splunk" "the environment should span 40+ machines"

# --- what the reduction cost, per control ------------------------------------
# The assertion that makes the volume number mean something. Each source
# declares the 800-53r5 controls and CSF 2.0 subcategories its events evidence,
# and which of those must not be dropped. After reduction, every must_not_drop
# control has to still have evidence in the index. A pipeline that saves volume
# by removing a control's only evidence has not saved anything, it has moved
# the cost somewhere that does not show up until an audit.
python3 - "$WORK/generator.log" "$WORK/controls.txt" <<'PYIN'
import json, sys, pathlib
log = pathlib.Path(sys.argv[1]).read_text().splitlines()
line = next((l for l in log if l.startswith("control_manifest ")), "")
rows = json.loads(line[len("control_manifest "):]) if line else []
out = []
for r in rows:
    if not r.get("must_not_drop"):
        continue
    out.append("\t".join([r["control"], r["csf"], r["sourcetype"],
                          r.get("field") or "-", ",".join(r["events"])]))
pathlib.Path(sys.argv[2]).write_text("\n".join(sorted(set(out))) + ("\n" if out else ""))
print(len(set(out)))
PYIN
ctl_total=$(num "$(wc -l < "$WORK/controls.txt" 2>/dev/null)")
ctl_missing=0
ctl_lines=""
while IFS=$'\t' read -r control csf stype field events; do
    [[ -n "${control:-}" ]] || continue
    # The source names the field its own pipeline extracts, so the control
    # check and the routing agree on how an event is identified. A dash means
    # the control is evidenced by the source arriving at all.
    if [[ "$field" == "-" || -z "${field:-}" ]]; then
        q="index=${PIPE_INDEX} earliest=-1h sourcetype=\"${stype}\""
    else
        clause=$(echo "$events" | tr ',' '\n' | sed "s|^|${field}=|" \
                 | paste -sd'@' - | sed 's/@/ OR /g')
        q="index=${PIPE_INDEX} earliest=-1h sourcetype=\"${stype}\" (${clause})"
    fi
    n=$(num "$(count_of "$q")")
    if [[ "$n" -gt 0 ]]; then
        ctl_lines+="  ok   ${control} / ${csf}  ${n} events\n"
    else
        ctl_missing=$((ctl_missing + 1))
        ctl_lines+="  MISS ${control} / ${csf}  no evidence in ${stype}\n"
    fi
done < "$WORK/controls.txt"
if [[ "$ctl_missing" -eq 0 ]]; then
    ok "every must-not-drop control still has evidence after reduction (${ctl_total} controls)"
else
    bad "${ctl_missing} of ${ctl_total} controls lost their evidence to the pipeline" \
        "reduction that removes a control's only evidence is a deferred cost, not a saving"
    printf '%b' "$ctl_lines" | grep MISS | head -10
fi

# The specific things the pipeline is supposed to do, still asserted directly.
noise=$(num "$(count_of "index=${PIPE_INDEX} earliest=-1h sourcetype=\"XmlWinEventLog:Security\" (EventID=5156 OR EventID=5158)")")
if [[ "$total" -eq 0 ]]; then
    skip "noise-dropped not exercised (nothing reached the index)"
elif [[ "$noise" -eq 0 ]]; then
    ok "Filtering Platform noise (5156/5158) was dropped"
else
    bad "${noise} connection-noise events reached Splunk" "the drop function did not run"
fi

cleared=$(num "$(count_of "index=${PIPE_INDEX} earliest=-1h EventID=1102")")
[[ "$cleared" -gt 0 ]] && ok "audit-log-cleared (1102) survived the pipeline (${cleared})" \
    || bad "no 1102 events reached Splunk" "the rarest and highest-value event was lost"

# match() against _raw, not a bare quoted term: the quoting a bare term needs
# survives neither the shell nor the CLI reliably, and a search that silently
# matches nothing reads as "the pipeline removed it".
count_match() { # count_match <index> <regex>
    local ix="${1:-}" re="${2:-}"
    num "$(spl "index=${ix} earliest=-1h | stats count(eval(match(_raw,\"${re}\"))) as n" \
        | tail -1 | tr -d '"' | grep -oE '^[0-9]+$')"
}
# The payload is ROUTED, not destroyed. It must be absent from the main index,
# present in the restricted index, and present in the unfiltered control - the
# last of those is what proves there was something to route in the first place.
leaked_main=$(count_match "$PIPE_INDEX" "RwBlAHQALQBQAHIAbwBjAGUAcwBz")
kept_restricted=$(count_match "$RESTRICTED_INDEX" "RwBlAHQALQBQAHIAbwBjAGUAcwBz")
ctl_leaked=$(count_match "$RAW_INDEX" "RwBlAHQALQBQAHIAbwBjAGUAcwBz")
if [[ "$ctl_leaked" -eq 0 ]]; then
    skip "encoded-command routing not exercised (none in the control arm)"
elif [[ "$leaked_main" -eq 0 && "$kept_restricted" -gt 0 ]]; then
    ok "encoded commands routed to ${RESTRICTED_INDEX} (${kept_restricted}), absent from the main index"
elif [[ "$kept_restricted" -eq 0 ]]; then
    bad "the encoded-command payload reached no index" \
        "routing destroyed the artifact instead of restricting access to it"
else
    bad "${leaked_main} encoded payloads reached the main index" "the route did not claim them"
fi


head2 "what the pipeline is worth: indexed volume, with and without cribl"
# Splunk licenses on INDEXED VOLUME - the size of _raw as it lands. So the
# comparison is like for like: sum(len(_raw)) for every event the endpoints
# produced (what a UF pointed straight at Splunk would meter) against
# sum(len(_raw)) actually in the index after the pipeline ran.
#
# These are MEASUREMENTS, printed whether or not they are flattering. The one
# assertion is two-sided, because a pipeline that dropped everything would
# otherwise post the best savings number in the report.
# Helper: licensed volume of an index, straight out of Splunk.
licensed_bytes() { # licensed_bytes <index>
    local ix="${1:-}"
    [[ -n "$ix" ]] || { printf '0\n'; return 0; }
    spl "index=${ix} earliest=-1h | eval b=len(_raw) | stats sum(b) as bytes" \
        | tail -1 | tr -d '"' | grep -oE '^[0-9]+' || printf '0\n'
}
# Helper: bytes actually on disk for an index. currentDBSizeMB rounds to whole
# megabytes, which is useless at lab volumes, so measure the bucket directory.
disk_bytes() { # disk_bytes <index>
    local ix="${1:-}"
    [[ -n "$ix" ]] || { printf '0\n'; return 0; }
    podman exec -u splunk lab-splunk sh -c "du -sb /opt/splunk/var/lib/splunk/${ix} 2>/dev/null | cut -f1" \
        2>/dev/null || printf '0\n'
}

idx_bytes=$(num "$(licensed_bytes "$PIPE_INDEX")")

# The measured control. Everything below prefers it over the generator's own
# accounting; raw_bytes stays as a cross-check on the control itself.
ctl_events=$(num "$(count_of "index=${RAW_INDEX} earliest=-1h")")
ctl_bytes=$(num "$(licensed_bytes "$RAW_INDEX")")
# Anything the forwarder could not send. A blocked or failing tcpout group is
# the one failure that would shorten the control arm and flatter the result.
hec_err=$(num "$(grep -oE 'direct_hec sent=[0-9]+ errors=[0-9]+' "$WORK/generator.log" \
    | grep -oE 'errors=[0-9]+' | cut -d= -f2 | tail -1)")

# An A/B with an empty control arm is not an A/B - it is the pipeline number
# with a flattering denominator. Say so rather than quietly falling back.
if [[ "$ctl_events" -eq 0 ]]; then
    bad "the unfiltered control index is empty" \
        "$(grep -m1 'direct_hec last_error' "$WORK/generator.log" || echo 'the direct-to-HEC tee sent nothing')"
elif [[ "$hec_err" -gt 0 ]]; then
    bad "the control arm lost ${hec_err} events to HEC errors" \
        "a short baseline overstates the saving"
else
    ok "control arm received all ${ctl_events} events unfiltered"
fi

# Cross-check the two independent accountings of the same quantity. They are
# measured in different places - the generator counting what it produced, and
# Splunk counting what it stored - so agreement is evidence that neither is
# silently short.
if [[ "$raw_bytes" -gt 0 && "$ctl_bytes" -gt 0 ]]; then
    skew=$(awk -v a="$raw_bytes" -v b="$ctl_bytes" 'BEGIN{d=(a>b?a-b:b-a); printf "%d", d/a*1000}')
    if [[ "$skew" -le 10 ]]; then
        ok "generator and control index agree on baseline volume (within 1%)"
    else
        bad "baseline accountings disagree by $((skew / 10))%" \
            "generator metered ${raw_bytes} bytes, the control index holds ${ctl_bytes}"
    fi
fi

ctl_disk=$(num "$(disk_bytes "$RAW_INDEX")")
pipe_disk=$(num "$(disk_bytes "$PIPE_INDEX")")

# Fleet projection. Both inputs are stated, not measured here: the EPS model is
# section 1 of cribl/docs/windows-to-splunk-pipeline.md, and the price is a
# term-license figure the operator supplies.
FLEET_EPS="${LAB_FLEET_EPS:-56750}"
COST_PER_GB_DAY="${LAB_COST_PER_GB_DAY:-150}"

# Both arms are measured out of Splunk. base_* is the control index: the same
# events, unfiltered, exactly as a forwarder pointed straight at Splunk would
# have indexed them.
base_events="$ctl_events"
base_bytes="$ctl_bytes"
if [[ "$base_bytes" -eq 0 ]]; then
    base_bytes="$raw_bytes"
    base_events="$sent"
fi

if [[ "$base_bytes" -gt 0 && "$idx_bytes" -gt 0 ]]; then
    awk -v raw="$base_bytes" -v idx="$idx_bytes" -v rev="$base_events" -v dev="$total" \
        -v eps="$FLEET_EPS" -v price="$COST_PER_GB_DAY" \
        -v rdisk="$ctl_disk" -v ddisk="$pipe_disk" 'BEGIN {
        kept = idx / raw * 100
        cut  = 100 - kept
        rawper = raw / rev
        printf "  A  no pipeline   %6d events %8.2f MB licensed  %6.0f bytes/event\n",
               rev, raw/1048576, rawper
        printf "  B  through cribl %6d events %8.2f MB licensed  %6.0f bytes/event\n",
               dev, idx/1048576, (dev>0 ? idx/dev : 0)
        printf "  =  removed       %6d events %8.2f MB licensed  %.1f%% of licensed volume\n",
               rev-dev, (raw-idx)/1048576, cut
        if (rdisk > 0 && ddisk > 0)
            printf "     on disk      %8.2f MB -> %8.2f MB (%.1f%% less; lab-scale buckets, not a production ratio)\n",
                   rdisk/1048576, ddisk/1048576, (rdisk-ddisk)/rdisk*100
        evday   = eps * 86400
        rawday  = evday * rawper / 1073741824
        idxday  = rawday * kept / 100
        printf "  projected at %d EPS: %.1f GB/day raw -> %.1f GB/day with cribl (%.1f GB/day less)\n",
               eps, rawday, idxday, rawday - idxday
        printf "  projected license at $%.0f per GB/day: $%.0f -> $%.0f, saving $%.0f\n",
               price, rawday*price, idxday*price, (rawday-idxday)*price
    }'
    echo "            arms A and B are both measured from Splunk; EPS model and price are"
    echo "            INPUTS (LAB_FLEET_EPS, LAB_COST_PER_GB_DAY), not measurements"

    # Where the saving comes from, per source. An aggregate percentage does
    # not survive a question like "what if we keep netflow?" - this does. Both
    # columns come out of Splunk, so the table is two measurements rather than
    # a measurement against the emitter's own bookkeeping.
    spl "index=${PIPE_INDEX} earliest=-1h | eval b=len(_raw) | stats count as n sum(b) as bytes by sourcetype" \
        > "$WORK/by_src_pipeline.csv" 2>/dev/null
    spl "index=${RAW_INDEX} earliest=-1h | eval b=len(_raw) | stats count as n sum(b) as bytes by sourcetype" \
        > "$WORK/by_src_control.csv" 2>/dev/null
    printf '\n  %-46s %9s %11s %9s %11s  %s\n' \
        sourcetype "A events" "A KB" "B events" "B KB" "removed"
    tail -n +2 "$WORK/by_src_control.csv" 2>/dev/null | tr -d '"' | sort -t, -k3 -rn \
    | while IFS=, read -r st n bytes; do
        [[ -n "${st:-}" ]] || continue
        drow=$(tr -d '"' < "$WORK/by_src_pipeline.csv" | grep -F "${st}," | head -1)
        dn=$(printf '%s' "$drow" | awk -F, '{print $2+0}')
        db=$(printf '%s' "$drow" | awk -F, '{print $3+0}')
        awk -v st="$st" -v n="${n:-0}" -v b="${bytes:-0}" -v dn="${dn:-0}" -v db="${db:-0}" 'BEGIN{
            printf "  %-46s %9d %11.1f %9d %11.1f  %.1f%%\n", st, n, b/1024, dn, db/1024,
                   (b>0 ? (b-db)/b*100 : 0)
        }'
    done
    echo

    kept_pct=$(awk -v raw="$base_bytes" -v idx="$idx_bytes" 'BEGIN{printf "%d", idx/raw*100}')
    # A two-sided band, and a narrow one. The previous 10-60% band admitted
    # almost any data set and any pipeline, which made it a check that could not
    # fail. This band is set from what the declared per-source treatments
    # arithmetically predict on the declared shares, so a pipeline edit or a
    # data set edit that moves the result has to be looked at rather than
    # absorbed.
    if [[ "$kept_pct" -ge 40 && "$kept_pct" -le 70 ]]; then
        ok "volume reduction is within the predicted band (${kept_pct}% of licensed bytes kept)"
    else
        bad "kept ${kept_pct}% of licensed bytes, predicted 40-70% for the detection-safe rule set" \
            "too high means a treatment did not run; too low means one is removing more than it was meant to"
    fi
else
    bad "could not measure indexed volume" \
        "control=${base_bytes} bytes, pipeline=${idx_bytes} bytes"
fi

head2 "no plaintext remains"
# A check that FAILS before the hardening and passes after. Plain http against
# an SSL listener gets a TLS-level rejection, never a 200.
# No `|| echo 000`: curl already writes 000 on a connection failure, and the
# fallback then appends a second one, so the report reads "got 000000".
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
    "http://127.0.0.1:${LAB_SPLUNK_WEB:-18000}/" 2>/dev/null)
code="${code:-000}"
if [[ "$code" == "200" || "$code" == "303" ]]; then
    bad "Splunk Web answers plain http on ${LAB_SPLUNK_WEB:-18000} (got $code)" \
        "enableSplunkWebSSL did not take effect"
else
    ok "Splunk Web refuses plain http (got ${code})"
fi
if curl -sk -o /dev/null --max-time 10 "https://127.0.0.1:${LAB_SPLUNK_WEB:-18000}/" 2>/dev/null; then
    ok "Splunk Web answers https"
else
    bad "Splunk Web does not answer https either" "the UI is unreachable, not merely plaintext"
fi
# The receiving port must not be a plaintext acceptor. `splunk enable listen`
# writes [splunktcp://9997] into the search app, which never merges with the
# [splunktcp-ssl://9997] in system/local, so both can be bound at once and the
# TLS stanza's presence proves nothing.
nonssl=$(num "$(podman exec -u splunk lab-splunk sh -c \
    "grep -c 'Acceptor for IPv4 port 9997 with Non-SSL' /opt/splunk/var/log/splunk/splunkd.log" 2>/dev/null)")
if [[ "$nonssl" -eq 0 ]]; then
    ok "no plaintext acceptor on 9997"
else
    bad "splunkd bound a Non-SSL acceptor on 9997 (${nonssl}x)" \
        "SPLUNK_ENABLE_LISTEN writes a plaintext [splunktcp://9997] the TLS stanza does not override"
fi

# The Cribl UI and API must be TLS as well. Plaintext here carries the same
# session cookie that authorizes every configuration change.
cribl_http=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 \
    "http://127.0.0.1:${LAB_CRIBL_WEB:-19010}/" 2>/dev/null)
cribl_https=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 8 \
    "https://127.0.0.1:${LAB_CRIBL_WEB:-19010}/" 2>/dev/null)
if [[ "${cribl_https:-000}" == "200" && "${cribl_http:-000}" != "200" ]]; then
    ok "Cribl UI answers https and refuses plain http"
else
    bad "Cribl UI is not TLS (http ${cribl_http:-000}, https ${cribl_https:-000})" \
        "api.ssl in the leader's cribl.yml did not take effect"
fi

# Nothing anywhere on port 80.
if [[ "$(num "$(podman ps --format '{{.Ports}}' | grep -cE '(^|[^0-9])80->|:80->')")" -gt 0 ]]; then
    bad "a container publishes port 80"
else
    ok "nothing published on port 80"
fi

head2 "result"
printf 'passed %d  failed %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
    printf '\nfailures:\n'
    for f in "${FAILURES[@]}"; do printf '  - %s\n' "$f"; done
    exit 1
fi
printf 'LAB PASSED\n'
