#!/bin/bash
set -e

if [[ "${PUSER_RLIMIT_UNLOCK:-false}" == "true" ]] && command -v ulimit >/dev/null 2>&1; then
  ulimit -l unlimited >/dev/null 2>&1
  ulimit -n 65535 >/dev/null 2>&1
  ulimit -u 262144 >/dev/null 2>&1
fi

unset ENTRYPOINT_CMD ENTRYPOINT_ARGS
[ "$#" -ge 1 ] && ENTRYPOINT_CMD="$1" && [ "$#" -gt 1 ] && shift 1 && ENTRYPOINT_ARGS=( "$@" )

usermod --non-unique --uid "${PUID:-${DEFAULT_UID}}" "${PUSER}"
groupmod --non-unique --gid "${PGID:-${DEFAULT_GID}}" "${PGROUP}"

set +e

if [[ -n ${PUSER_CHOWN} ]]; then
  IFS=';' read -ra ENTITIES <<< "${PUSER_CHOWN}"
  for ENTITY in "${ENTITIES[@]}"; do
    chown -R "${PUSER}:${PGROUP}" "${ENTITY}" 2>/dev/null
  done
fi

if [[ -n ${PUID} ]] && [[ "${PUID}" != "${DEFAULT_UID}" ]]; then
  find / -path /sys -prune -o -path /proc -prune -o -user "${DEFAULT_UID}" -exec chown -f "${PUID}" "{}" \; 2>/dev/null
fi
if [[ -n ${PGID} ]] && [[ "${PGID}" != "${DEFAULT_GID}" ]]; then
  find / -path /sys -prune -o -path /proc -prune -o -group "${DEFAULT_GID}" -exec chown -f ":${PGID}" "{}" \; 2>/dev/null
fi

if [[ "${PUSER_PRIV_DROP}" == "true" ]]; then
  EXEC_USER="${PUSER}"
  USER_HOME="$(getent passwd "${PUSER}" | cut -d: -f6)"
else
  EXEC_USER="${USER:-root}"
  USER_HOME="${HOME:-/root}"
fi

su -s /bin/bash -p "${EXEC_USER}" << EOF
export USER="${EXEC_USER}"
export HOME="${USER_HOME}"
if [[ "${PUSER_RLIMIT_UNLOCK:-false}" == "true" ]] && command -v ulimit >/dev/null 2>&1; then
  ulimit -l unlimited >/dev/null 2>&1
  ulimit -n 65535 >/dev/null 2>&1
  ulimit -u 262144 >/dev/null 2>&1
fi
if [[ ! -z "${ENTRYPOINT_CMD}" ]]; then
  if [[ -z "${ENTRYPOINT_ARGS}" ]]; then
    "${ENTRYPOINT_CMD}"
  else
    "${ENTRYPOINT_CMD}" $(printf "%q " "${ENTRYPOINT_ARGS[@]}")
  fi
fi
EOF
