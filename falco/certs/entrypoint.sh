#!/bin/sh

set -e
umask 077

cert() {
  COMMON_NAME="$1"
  FILENAME="$2"

  if [ -z "$FILENAME" ]; then
    FILENAME="sslcert_${COMMON_NAME//./_}"
  fi

  echo "Creating certificate for ${COMMON_NAME}"

  if [ ! -f "${FILENAME}_rsa.key" ]; then
    openssl genrsa -out "${FILENAME}_rsa.key" 4096
  fi

  openssl req -new -sha512 -key "${FILENAME}_rsa.key" -out "${FILENAME}.csr" \
    -subj "/C=${COUNTRY_CODE}/ST=${STATE}/L=${CITY}/O=${COMPANY}/CN=${COMMON_NAME}" || exit 1

  echo "authorityKeyIdentifier=keyid,issuer" > ext.cnf
  echo "basicConstraints=CA:FALSE" >> ext.cnf
  echo "keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment" >> ext.cnf
  echo "subjectAltName = DNS:${COMMON_NAME},DNS:*.${COMMON_NAME}" >> ext.cnf

  openssl x509 -req -sha512 -days 3650 -passin "pass:${AUTHORITY_PASSWORD}" \
    -in "${FILENAME}.csr" -CA ca.crt -CAkey ca.key -CAserial ca.srl -CAcreateserial \
    -out "${FILENAME}.crt" -extfile ext.cnf || exit 1

  cat "${FILENAME}.crt" ca.crt > "${FILENAME}_chain.pem"
  cat "${FILENAME}.crt" "${FILENAME}_rsa.key" > "${FILENAME}.pem"
  cp "${FILENAME}_rsa.key" "${FILENAME}_rsa.key.pem"

  rm "${FILENAME}.csr" ext.cnf
  chmod 600 *
}

mkdir -p /certs
cd /certs

if [ ! -f ca.key ] || [ ! -f ca.crt ]; then
  echo "Creating CA..."
  openssl genrsa -aes256 -passout "pass:${AUTHORITY_PASSWORD}" -out ca.key 4096 || exit 1
  openssl req -new -x509 -sha512 -passin "pass:${AUTHORITY_PASSWORD}" -extensions v3_ca -key ca.key -out ca.crt -days 3650 \
    -subj "/C=${COUNTRY_CODE}/O=${COMPANY}/CN=${AUTHORITY_NAME}" || exit 1
  echo "01" > ca.srl
fi

cert "${DOMAIN_NAME}" "falco"
cert "sidekick.local" "sidekick"
cert "tinyauth.local" "tinyauth"
cert "dashboard.podman.localhost" "traefik_dashboard"
cert "falco-webui.local" "falco_webui"

ls -l /certs