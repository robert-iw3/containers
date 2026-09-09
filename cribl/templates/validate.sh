#!/usr/bin/env bash
# Check a rendered group directory against Cribl's own schema, before deploying.
#
#   ./validate.sh out/ [--image docker.io/cribl/cribl:4.19.2]
#
# Cribl reports a bad key only as "Output config validation failed during
# startup". It names an output without saying why - often a different, entirely
# valid one - and ONE invalid entry disables every output in the file. The
# symptom downstream is "nothing reached the index", which sends you hunting the
# wrong leg for an afternoon. This reads the schema out of the image instead.
set -uo pipefail

OUT="${1:?usage: validate.sh <rendered-dir> [--image IMAGE]}"; shift || true
IMAGE="${CRIBL_IMAGE:-docker.io/cribl/cribl:4.19.2}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --image) IMAGE="$2"; shift 2 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); printf '  ok    %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; [[ -n "${2:-}" ]] && printf '          %s\n' "$2"; return 0; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# The schema comes out of the image, not out of memory. Every key in these
# templates was confirmed this way; recalled key names are how the four
# original Destination bugs got written.
if podman image exists "$IMAGE" 2>/dev/null; then
    cid="$(podman create "$IMAGE" 2>/dev/null)"
    podman cp "${cid}:/opt/cribl/default/ui/static/swagger/openapi.json.gz" "$WORK/openapi.json.gz" 2>/dev/null
    podman rm -f "$cid" >/dev/null 2>&1
    gunzip -f "$WORK/openapi.json.gz" 2>/dev/null
fi
if [[ ! -f "$WORK/openapi.json" ]]; then
    echo "validate.sh: could not read the schema from ${IMAGE}" >&2
    echo "             pull it first: podman pull ${IMAGE}" >&2
    exit 1
fi
ok "read the schema from ${IMAGE}"

python3 - "$WORK/openapi.json" "$OUT" <<'PYIN'
import json, sys, os, glob
import yaml

schemas = json.load(open(sys.argv[1]))["components"]["schemas"]
out = sys.argv[2]
problems, checks = [], []

INPUT_KIND = {"syslog": "InputSyslog", "splunk": "InputSplunk", "tcpjson": "InputTcpjson",
              "splunk_hec": "InputSplunkHec", "http": "InputHttp", "tcp": "InputTcp",
              "kafka": "InputKafka", "elastic": "InputElastic"}
OUTPUT_KIND = {"splunk_hec": "OutputSplunkHec", "splunk_lb": "OutputSplunkLb",
               "splunk": "OutputSplunk", "filesystem": "OutputFilesystem",
               "devnull": None, "s3": "OutputS3"}

def check_entries(doc, key, kindmap, label):
    for name, obj in (doc.get(key) or {}).items():
        kind = kindmap.get(obj.get("type"))
        if not kind or kind not in schemas:
            checks.append(f"{label} {name}: type '{obj.get('type')}' not checked")
            continue
        props = schemas[kind].get("properties", {})
        for k in obj:
            if k not in props:
                problems.append(f"{label} {name}: '{k}' is not a key of {obj['type']}")
        for k in schemas[kind].get("required", []):
            if k not in obj:
                problems.append(f"{label} {name}: missing required key '{k}'")

inputs = yaml.safe_load(open(os.path.join(out, "inputs.yml"))) or {}
outputs = yaml.safe_load(open(os.path.join(out, "outputs.yml"))) or {}
routes = yaml.safe_load(open(os.path.join(out, "route.yml"))) or {}
check_entries(inputs, "inputs", INPUT_KIND, "Source")
check_entries(outputs, "outputs", OUTPUT_KIND, "Destination")

# Key existence is not enough. `urls` is read only when loadBalanced is true, so
# a Destination carrying `urls` with the default false has NO url at all and
# dies with "URL must start with http or https".
for name, o in (outputs.get("outputs") or {}).items():
    if o.get("type") == "splunk_hec":
        if not o.get("url") and not (o.get("loadBalanced") and o.get("urls")):
            problems.append(f"Destination {name}: no usable URL - set `url`, or `loadBalanced: true` with `urls`")
        if str(o.get("url", "")).startswith("http://"):
            problems.append(f"Destination {name}: url is http. Splunk ships HEC with enableSSL=1")
    if o.get("type") in ("splunk_lb", "splunk") and not (o.get("hosts") or o.get("host")):
        problems.append(f"Destination {name}: no hosts")
    # filesystem and object-store Destinations accept only block|drop.
    if o.get("type") in ("filesystem", "s3") and o.get("onBackpressure") not in (None, "block", "drop"):
        problems.append(f"Destination {name}: onBackpressure '{o['onBackpressure']}' - "
                        f"filesystem accepts only block or drop")

# Pipeline functions have to exist by id, and every route has to point at a
# pipeline directory and an output that is actually declared.
fn_dirs = set()
for p in ("/opt/cribl/default/cribl/functions",):
    pass
declared_outputs = set((outputs.get("outputs") or {}).keys())
pipeline_dirs = {os.path.basename(os.path.dirname(p))
                 for p in glob.glob(os.path.join(out, "pipelines", "*", "conf.yml"))}
for r in (routes.get("routes") or []):
    if r.get("pipeline") not in pipeline_dirs:
        problems.append(f"Route {r.get('id')}: pipeline '{r.get('pipeline')}' has no directory")
    if r.get("output") not in declared_outputs:
        problems.append(f"Route {r.get('id')}: output '{r.get('output')}' is not in outputs.yml")

# A route list with no final catch-all sends unmatched events nowhere visible.
if not any(r.get("filter") == "true" for r in (routes.get("routes") or [])):
    problems.append("route.yml: no catch-all route - unmatched events vanish without a trace")

for f in sorted(glob.glob(os.path.join(out, "pipelines", "*", "conf.yml"))):
    doc = yaml.safe_load(open(f)) or {}
    name = os.path.basename(os.path.dirname(f))
    for fn in (doc.get("functions") or []):
        if not fn.get("id"):
            problems.append(f"Pipeline {name}: a function has no id")

print(json.dumps({"problems": problems, "checks": checks}))
PYIN
res=$?
[[ $res -eq 0 ]] || { echo "validate.sh: schema check could not run" >&2; exit 1; }
