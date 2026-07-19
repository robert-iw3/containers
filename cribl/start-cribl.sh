#!/bin/bash
# Seed first-boot state and run Cribl Stream in the foreground (tini is
# PID 1; `cribl start` would daemonize and kill the container).
set -euo pipefail

CRIBL_HOME=/opt/cribl

mkdir -p "$CRIBL_HOME/local/cribl/auth"
if [ ! -s "$CRIBL_HOME/local/cribl/auth/676f6174733432.dat" ]; then
  cat << EOF > "$CRIBL_HOME/local/cribl/auth/676f6174733432.dat"
{"it":$(date +%s),"phf":0,"guid":"$(uuidgen)","email":"demo@cribl.io"}
EOF
fi

exec "$CRIBL_HOME/bin/cribl" server
