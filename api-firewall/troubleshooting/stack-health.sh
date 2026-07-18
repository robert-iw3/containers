#!/bin/bash
# Health overview of every api-firewall-related container (main stack, demo,
# UAT, integrations), with error tails for any that are not healthy.
#
#   ./stack-health.sh            # api-firewall* + apifw-*
#   ./stack-health.sh myprefix   # myprefix*
source "$(dirname "$0")/_common.sh"
PATTERN="${1:-api-firewall|apifw-}"

rows="$($CE ps -a --format '{{.Names}}\t{{.Status}}' 2>/dev/null | grep -E "^(${PATTERN})" | sort)"

hdr "containers matching '${PATTERN}'"
if [ -z "$rows" ]; then
  warn "no containers matching '${PATTERN}*' (stack not running?)"
  exit 0
fi
while IFS=$'\t' read -r name status; do
  case "$status" in
    *"(healthy)"*) printf "  ${G}%-26s${N} %s\n" "$name" "$status" ;;
    "Up "*)        printf "  ${Y}%-26s${N} %s\n" "$name" "$status" ;;
    *)             printf "  ${R}%-26s${N} %s\n" "$name" "$status" ;;
  esac
done <<<"$rows"

hdr "recent errors from non-healthy containers"
unhealthy=0
while IFS=$'\t' read -r name status; do
  case "$status" in
    *"(healthy)"*|"Up "*) : ;;
    *)
      unhealthy=$((unhealthy + 1))
      printf "${B}--- %s (%s) ---${N}\n" "$name" "$status"
      $CE logs --tail 20 "$name" 2>&1 | grep -iE 'error|fatal|panic|fail|refused|denied|cannot|unmarshal' | tail -6
      ;;
  esac
done <<<"$rows"
[ "$unhealthy" = "0" ] && ok "all matched containers are up/healthy"
