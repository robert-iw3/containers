#!/bin/bash
# Health overview of every container in the stack, with error tails for any that
# are not healthy. First arg overrides the container name prefix (default: the
# stack directory name, e.g. "nextcloud").
#
#   ./stack-health.sh            # nextcloud-*
#   ./stack-health.sh owncloud   # owncloud-*
source "$(dirname "$0")/_common.sh"
PREFIX="${1:-$STACK_NAME}"

# Capture once (grep in a var, not a pipe, so counters survive).
rows="$($CE ps -a --format '{{.Names}}\t{{.Status}}' 2>/dev/null | grep -E "^${PREFIX}" | sort)"

hdr "$PREFIX containers"
if [ -z "$rows" ]; then
  warn "no containers matching '${PREFIX}*' (stack not running?)"
  exit 0
fi
while IFS=$'\t' read -r name status; do
  case "$status" in
    *"(healthy)"*|"Up "*) printf "  ${G}%-26s${N} %s\n" "$name" "$status" ;;
    *)                    printf "  ${R}%-26s${N} %s\n" "$name" "$status" ;;
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
      $CE logs --tail 12 "$name" 2>&1 | grep -iE 'error|fatal|panic|fail|refused|denied|cannot' | tail -6
      ;;
  esac
done <<<"$rows"
[ "$unhealthy" = "0" ] && ok "all matched containers are up/healthy"
