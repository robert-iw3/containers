# Adding subjectAltName to cert, for traefik https redirect

```bash
mkdir certs && cd certs

#generate CA, server certificate and key

openssl genrsa -out ca.key 2048

openssl req -new -x509 -days 365 -key ca.key \
-subj "/C=US/ST=WA/L=Mars/O=Testing/CN=Root CA" -out ca.crt

openssl req -newkey rsa:2048 -nodes -keyout nessus.testing.io.key \
-subj "/C=US/ST=WA/L=Mars/O=Testing/CN=*.nessus.testing.io" -out nessus.testing.io.csr

openssl x509 -req -extfile <(printf "subjectAltName=DNS:nessus.testing.io,DNS:www.nessus.testing.io") \
-days 365 -in nessus.testing.io.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out nessus.testing.io.crt

# move certs to nessus container and import CA, Cert, Key

podman exec nessus mkdir /certs
tar Ccf $(dirname ./) - $(basename ./) | podman exec -i nessus tar Cxf /certs -
podman exec -it nessus /bin/bash

```
```console

/opt/nessus/sbin/nessuscli import-certs --serverkey=/certs/nessus.testing.io.key \
--servercert=/certs/nessus.testing.io.crt --cacert=/certs/ca.crt

```
