## generate server certificate
```sh
mkdir -p ./apps/keycloak/ubi9/certs; cd ./apps/keycloak/ubi9/certs

# variables to pass to csr config file

COUNTRY="US"
STATE="FL"
LOCALE="Floribama"
ORG="UMBRELLA_CORP"
ORG_UNIT="ReaperActual"
COMMON_NAME="keycloak.io"
CA_CN="Keycloak Root CA"
SUBJ_ALT_NAME1="keycloak"
SUBJ_ALT_NAME2="www.keycloak.io"
IP1=
IP2=

tee csr.conf<<EOF
[ req ]
default_bits = 4096
prompt = no
default_md = sha384
req_extensions = req_ext
distinguished_name = dn

[ dn ]
C = $(echo $COUNTRY)
ST = $(echo $STATE)
L = $(echo $LOCALE)
O = $(echo $ORG)
OU = $(echo $ORG_UNIT)
CN = $(echo $COMMON_NAME)

[ req_ext ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = $(echo $SUBJ_ALT_NAME1)
DNS.2 = $(echo $SUBJ_ALT_NAME2)
IP.1 = $(echo $IP1)
IP.2 = $(echo $IP2)
EOF

#generate CA, server certificate and key

openssl genrsa -out ca.key 4096

openssl req -new -x509 -days 730 -key ca.key \
-subj "/C=$(echo $COUNTRY)/ST=$(echo $STATE)/L=$(echo $LOCALE)/O=$(echo $ORG)/CN=$(echo $CA_CN)" -out ca.crt

openssl req -new -key keycloak.key.pem -out keycloak.csr -config csr.conf

openssl x509 -req -in keycloak.csr -CA ca.crt -CAkey ca.key \
-CAcreateserial -out keycloak.crt.pem -days 365 \
-extfile csr.conf
```

## move certs and insert COPY command in Dockerfile
```sh

COPY --chmod=755 certs /opt/certs

```

## build and run keycloak
```sh
# base image is ubi9, redhat requires subscription manager
# https://www.keycloak.org/server/all-config?options-filter=all

podman build -t keycloak \
  --build-arg SUBSCRIPTION_USER=" " \
  --build-arg SUBSCRIPTION_PASS=" " \
  --build-arg DB_TYPE=postgres \
  --build-arg URL=keycloak.io \
  --build-arg HTTPS_PORT=8443 \
  --build-arg CERT_FILE=/opt/certs/keycloak.crt.pem \
  --build-arg CERT_KEY=/opt/certs/keycloak.key.pem \
  .

podman run --rm -it --name keycloak -p 8443:8443 localhost/keycloak:latest

```
