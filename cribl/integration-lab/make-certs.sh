#!/usr/bin/env bash
# Generate the lab's CA and per-service certificates.
#
#   ./make-certs.sh [out-dir]        default: ./certs (gitignored)
#
# Every certificate carries a subjectAltName for the service name containers
# resolve. A CN-only certificate fails verification in every current TLS client,
# so a SAN-less cert here would force rejectUnauthorized: false everywhere and
# make the TLS decorative.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-$HERE/certs}"
DAYS="${CERT_DAYS:-825}"

mkdir -p "$OUT"; chmod 700 "$OUT"

if [[ ! -f "$OUT/ca.crt" ]]; then
    openssl req -x509 -nodes -newkey rsa:4096 -days "$DAYS" \
        -keyout "$OUT/ca.key" -out "$OUT/ca.crt" \
        -subj "/CN=cribl-lab-ca/O=lab" \
        -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
        -addext "keyUsage=critical,keyCertSign,cRLSign" 2>/dev/null
    echo "  CA created"
fi

# issue <name> <SAN list>
issue() {
    local name="$1" sans="$2"
    [[ -f "$OUT/$name.crt" ]] && return 0
    # Unencrypted key on purpose: Splunk needs an sslPassword for an encrypted
    # one, and a passphrase in a config file protects nothing here.
    openssl req -nodes -newkey rsa:2048 -keyout "$OUT/$name.key" \
        -out "$OUT/$name.csr" -subj "/CN=$name/O=lab" 2>/dev/null
    openssl x509 -req -in "$OUT/$name.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" \
        -CAcreateserial -days "$DAYS" -out "$OUT/$name.crt" \
        -extfile <(printf 'subjectAltName=%s\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth,clientAuth\n' "$sans") 2>/dev/null
    rm -f "$OUT/$name.csr"
    echo "  issued $name  ($sans)"
}

# The names containers actually resolve, plus localhost for host-side checks.
issue splunk       "DNS:splunk,DNS:lab-splunk,DNS:localhost,IP:127.0.0.1"
issue cribl-leader "DNS:cribl-leader,DNS:lab-cribl-leader,DNS:localhost,IP:127.0.0.1"
issue cribl-worker "DNS:cribl-worker,DNS:localhost,IP:127.0.0.1"
issue endpoint     "DNS:endpoint,DNS:endpoints"
# The universal forwarder's client certificate. Splunk's [splunktcp-ssl://9997]
# checks the common name, so this CN has to match sslCommonNameToCheck there and
# the Source's commonNameRegex on the Cribl side.
issue splunkuf     "DNS:splunkuf,DNS:uf,DNS:localhost"

# Splunk wants cert+key concatenated in one PEM.
for n in splunk cribl-leader cribl-worker splunkuf; do
    cat "$OUT/$n.crt" "$OUT/$n.key" > "$OUT/$n-bundle.pem"
done
chmod 600 "$OUT"/*.key "$OUT"/*-bundle.pem
chmod 644 "$OUT"/*.crt

echo "  verifying the chain:"
for n in splunk cribl-leader cribl-worker endpoint splunkuf; do
    printf '    %-14s ' "$n"
    openssl verify -CAfile "$OUT/ca.crt" "$OUT/$n.crt" 2>&1 | tail -1
done
