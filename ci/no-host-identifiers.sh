#!/usr/bin/env bash
# Fails when a tracked file carries information tying it to the machine it
# was written on: a real account name, hostname, home directory or lab
# subnet. Generated sample data must use fictional identities, because these
# files are committed and shipped.
#
# Scope defaults to the whole tree; pass paths to narrow it.
#
# Add a pattern by appending to PATTERNS. Keep each one anchored enough that
# it does not fire on ordinary words.
set -uo pipefail

PATHS=("$@")
if [ ${#PATHS[@]} -eq 0 ]; then PATHS=("."); fi

# The real account, host and lab network of the workstation this repository
# is developed on, plus the generic shapes that leak a home directory.
PATTERNS=(
  'shiftyroot'
  'ubuntu-main'
  'robertiweber'
  '10\.89\.1\.'
  '/home/[a-z][a-z0-9_-]*/Documents/GitHub'
)

# Files that legitimately mention a developer path: none today. Entries are
# matched as fixed substrings against the repo-relative path.
ALLOW=(
  'ci/no-host-identifiers.sh'
)

allowed() {
  local f="$1" a
  for a in "${ALLOW[@]}"; do
    case "$f" in *"$a"*) return 0 ;; esac
  done
  return 1
}

# git ls-files keeps this to tracked content and avoids .git, build output
# and anything ignored. grep on this host is ugrep, which honours
# .gitignore, so the file list comes from git rather than a tree walk.
mapfile -t FILES < <(git ls-files -z -- "${PATHS[@]}" | tr '\0' '\n')

if [ ${#FILES[@]} -eq 0 ]; then
  echo "no tracked files under: ${PATHS[*]}"
  exit 0
fi

fail=0
for pat in "${PATTERNS[@]}"; do
  for f in "${FILES[@]}"; do
    [ -f "$f" ] || continue
    allowed "$f" && continue
    # grep -c, not grep -q: a pipe to a short-circuiting reader makes grep
    # exit 141 on SIGPIPE, which reads as "no match".
    n=$(grep -c -E -- "$pat" "$f" 2>/dev/null || true)
    [ -z "$n" ] && n=0
    if [ "$n" -gt 0 ]; then
      printf 'HOST IDENTIFIER  %-56s %s (%s occurrence(s))\n' "$f" "$pat" "$n"
      fail=1
    fi
  done
done

if [ "$fail" -ne 0 ]; then
  echo
  echo "Replace these with fictional values. Sample data ships to other"
  echo "people; it must not name a real account, host or subnet."
  exit 1
fi

echo "no host identifiers in ${#FILES[@]} tracked file(s) under: ${PATHS[*]}"
exit 0
