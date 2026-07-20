#!/usr/bin/env bash
# Install the stack's demo CA where browsers actually look.
#
#   ./troubleshooting/install-ca.sh            # Firefox profiles + visible copy
#   ./troubleshooting/install-ca.sh --system   # also the system trust store (sudo)
#
# Firefox gotchas this solves:
#   - the extracted CA is a hidden dotfile (.portal-ca.crt) — snap Firefox's
#     file picker can't even see it, so manual import "doesn't work"
#   - Firefox uses its own NSS store, not the system trust store, so
#     update-ca-certificates alone never helps it
# certutil (libnss3-tools) writes the CA directly into every Firefox
# profile's cert9.db — no file-picker involved. Close Firefox first.
set -euo pipefail

cd "$(dirname "$0")/.."
RUNTIME="${RUNTIME:-podman}"
CA_NAME="backstage-portal-demo-ca"
VISIBLE="$HOME/portal-demo-ca.pem"

echo "==> extracting a fresh CA copy to a visible path: $VISIBLE"
"$RUNTIME" run --rm --user root -v backstage_portal-certs:/portal-certs:ro localhost/vault:2.0.3 \
  cat /portal-certs/ca.crt > "$VISIBLE"
chmod 644 "$VISIBLE"
openssl x509 -in "$VISIBLE" -noout -subject -enddate | sed 's/^/    /'

if ! command -v certutil >/dev/null; then
  echo
  echo "certutil not found — installing libnss3-tools makes this automatic:"
  echo "    sudo apt-get install -y libnss3-tools   # (or dnf install nss-tools)"
  echo
  echo "Manual fallback: Firefox -> Settings -> Privacy & Security ->"
  echo "  Certificates -> View Certificates -> *** AUTHORITIES tab *** ->"
  echo "  Import -> pick $VISIBLE -> check 'Trust this CA to identify websites'."
  echo "  Do NOT use the 'Your Certificates' tab — that one expects a"
  echo "  private key and fails with 'you do not own the corresponding"
  echo "  private key'. A CA import never includes a private key."
  echo "  (Import the VISIBLE copy — snap Firefox cannot open dotfiles.)"
else
  echo "==> installing into Firefox NSS profiles (close Firefox first)"
  FOUND=0
  for db in "$HOME"/.mozilla/firefox/*/cert9.db \
            "$HOME"/snap/firefox/common/.mozilla/firefox/*/cert9.db \
            "$HOME"/.var/app/org.mozilla.firefox/.mozilla/firefox/*/cert9.db; do
    [ -f "$db" ] || continue
    FOUND=1
    PROFILE=$(dirname "$db")
    certutil -D -n "$CA_NAME" -d sql:"$PROFILE" 2>/dev/null || true
    if certutil -A -n "$CA_NAME" -t "C,," -i "$VISIBLE" -d sql:"$PROFILE"; then
      echo "    installed into $PROFILE"
    else
      echo "    FAILED for $PROFILE (is Firefox running? close it and retry)"
    fi
  done
  [ "$FOUND" = 1 ] || echo "    no Firefox profiles found (deb/snap/flatpak paths checked)"
fi

if [ "${1:-}" = "--system" ]; then
  echo "==> system trust store (chromium, curl, CLI tools)"
  if command -v update-ca-certificates >/dev/null; then
    sudo install -m 0644 "$VISIBLE" /usr/local/share/ca-certificates/"$CA_NAME".crt
    sudo update-ca-certificates | tail -1
  elif command -v update-ca-trust >/dev/null; then
    sudo install -m 0644 "$VISIBLE" /etc/pki/ca-trust/source/anchors/"$CA_NAME".crt
    sudo update-ca-trust
  else
    echo "    no known system trust tool found"
  fi
fi

echo
echo "install-ca: DONE — restart Firefox, then browse https://127.0.0.1:27007"
