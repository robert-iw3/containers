#!/bin/bash
# Validate an OpenAPI spec before feeding it to the firewall. Catches the
# failure modes that crash-loop the container with parser errors:
#   - invalid JSON
#   - OpenAPI 3.1 documents (kin-openapi wants 3.0.x)
#   - 3.1/draft-07 constructs inside a 3.0 doc (numeric exclusiveMinimum/
#     exclusiveMaximum — what modern FastAPI/pydantic emit)
#
#   ./spec-check.sh                       # spec from ../.env APIFW_SPEC_FILE
#   ./spec-check.sh path/to/openapi.json
source "$(dirname "$0")/_common.sh"

SPEC="${1:-}"
if [ -z "$SPEC" ]; then
  SPEC="$(env_get APIFW_SPEC_FILE)"
  SPEC="$STACK_DIR/${SPEC:-specs/httpbin-demo.json}"
fi

hdr "spec: $SPEC"
[ -f "$SPEC" ] || { bad "file not found"; exit 1; }

python3 - "$SPEC" <<'EOF'
import json, sys

FAIL = 0
def ok(m):   print(f"  \033[32mPASS\033[0m {m}")
def bad(m):
    global FAIL; FAIL = 1
    print(f"  \033[31mFAIL\033[0m {m}")
def warn(m): print(f"  \033[33mWARN\033[0m {m}")

try:
    spec = json.load(open(sys.argv[1]))
    ok("valid JSON")
except Exception as e:
    bad(f"invalid JSON: {e}")
    sys.exit(1)

version = spec.get("openapi", "")
if version.startswith("3.0"):
    ok(f"OpenAPI {version} (fully supported)")
elif version.startswith("3.1"):
    bad(f"OpenAPI {version}: the firewall's parser (kin-openapi) does not "
        "reliably support 3.1 — regenerate as 3.0.x (e.g. FastAPI 0.98/"
        "pydantic v1, or convert)")
elif spec.get("swagger"):
    bad(f"Swagger {spec['swagger']}: convert to OpenAPI 3.0")
else:
    bad(f"missing/unknown 'openapi' version field: {version!r}")

paths = spec.get("paths") or {}
if paths:
    n_ops = sum(1 for p in paths.values() if isinstance(p, dict)
                for m in p if m in ("get","put","post","delete","patch","head","options","trace"))
    ok(f"{len(paths)} paths / {n_ops} operations")
else:
    bad("no paths defined — the firewall would block everything")

# 3.1/draft-07 constructs that crash the 3.0 parser.
hits = []
def walk(node, path):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("exclusiveMinimum", "exclusiveMaximum") and isinstance(v, (int, float)) and not isinstance(v, bool):
                hits.append(f"{path}/{k}={v}")
            walk(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{path}[{i}]")
walk(spec, "")
if hits:
    bad(f"numeric exclusiveMinimum/Maximum ({len(hits)}x) — 3.1 construct the "
        "parser rejects ('cannot unmarshal number into ... type bool'):")
    for h in hits[:5]:
        print(f"         {h}")
else:
    ok("no numeric exclusiveMinimum/Maximum constructs")

secs = (spec.get("components") or {}).get("securitySchemes") or {}
if secs:
    ok(f"securitySchemes: {', '.join(secs)}")
else:
    warn("no securitySchemes — the firewall cannot enforce authentication presence")

sys.exit(FAIL)
EOF
rc=$?

hdr "verdict"
if [ "$rc" = "0" ]; then ok "spec should load cleanly"; else bad "fix the items above before mounting this spec"; fi
exit "$rc"
