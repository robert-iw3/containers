#!/bin/bash
# Probe a running firewall container: effective configuration, liveness/
# readiness (readiness also proves backend connectivity), and live block
# behaviour on the published edge address.
#
#   ./firewall-probe.sh
#   FIREWALL_CONTAINER=apifw-uat-firewall EDGE_URL=http://127.0.0.1:8081 ./firewall-probe.sh
source "$(dirname "$0")/_common.sh"

hdr "container: $FW"
if ! fw_running; then
  bad "not running"
  status="$($CE inspect "$FW" --format '{{.State.Status}} (exit {{.State.ExitCode}})' 2>/dev/null)"
  [ -n "$status" ] && info "state: $status"
  $CE logs --tail 15 "$FW" 2>&1 | grep -iE 'error|fatal|unmarshal|denied|cannot' | tail -5
  exit 1
fi
ok "running"

hdr "effective configuration"
for v in APIFW_MODE APIFW_URL APIFW_API_SPECS APIFW_SERVER_URL \
         APIFW_REQUEST_VALIDATION APIFW_RESPONSE_VALIDATION \
         APIFW_CUSTOM_BLOCK_STATUS_CODE APIFW_MODSEC_CONF_FILES \
         APIFW_DENYLIST_TOKENS_FILE APIFW_ALLOW_IP_FILE; do
  val="$(fw_env "$v")"
  [ -n "$val" ] && info "$(printf '%-36s %s' "$v" "$val")"
done
[ -z "$(fw_env APIFW_MODSEC_CONF_FILES)" ] && warn "WAF (Coraza/CRS) not configured"

BLOCK_CODE="$(fw_env APIFW_CUSTOM_BLOCK_STATUS_CODE)"
BLOCK_CODE="${BLOCK_CODE:-403}"

hdr "health listeners (:9667 inside the container)"
if $CE exec "$FW" wget -q -O /dev/null http://127.0.0.1:9667/v1/liveness 2>/dev/null; then
  ok "liveness"
else
  bad "liveness — process up but health listener unreachable"
fi
if $CE exec "$FW" wget -q -O /dev/null http://127.0.0.1:9667/v1/readiness 2>/dev/null; then
  ok "readiness (spec loaded AND backend reachable)"
else
  bad "readiness — usually means the backend ($(fw_env APIFW_SERVER_URL)) is unreachable; run ./backend-check.sh"
fi

hdr "block behaviour on $EDGE_URL"
code="$(tcurl -o /dev/null -w '%{http_code}' "$EDGE_URL/apifw-troubleshoot-$RANDOM" 2>/dev/null)"
case "$code" in
  "$BLOCK_CODE") ok "unknown path blocked with $code (matches APIFW_CUSTOM_BLOCK_STATUS_CODE)" ;;
  000)           bad "edge not reachable at $EDGE_URL (published port? TLS? set EDGE_URL/CACERT/CURL_INSECURE)" ;;
  404|200)       warn "unknown path returned $code from the BACKEND — request validation is not blocking (mode: $(fw_env APIFW_REQUEST_VALIDATION))" ;;
  *)             warn "unknown path returned $code (expected block code $BLOCK_CODE)" ;;
esac

if [ -n "$(fw_env APIFW_MODSEC_CONF_FILES)" ]; then
  code="$(tcurl -o /dev/null -w '%{http_code}' -A 'sqlmap/1.7' "$EDGE_URL/" 2>/dev/null)"
  case "$code" in
    403)         ok "WAF blocks scanner UA (403 from CRS)" ;;
    000)         bad "edge not reachable for WAF probe" ;;
    *)           warn "scanner UA returned $code — CRS may not be loaded (rules dir mounted? get-crs.sh run?)" ;;
  esac
fi

hdr "recent blocks (last 5)"
$CE logs --tail 200 "$FW" 2>&1 | grep -iE '"error"|blocked|matched' | tail -5 | cut -c1-160
exit 0
