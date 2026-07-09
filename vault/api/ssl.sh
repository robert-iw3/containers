#!/bin/bash

mkdir certs && cd certs

#generate CA, server certificate and key

openssl genrsa -out ca.key 4096

openssl req -new -x509 -days 730 -key ca.key \
-subj "/C=US/ST=CO/L=a53/O=Testing/CN=api-fw SSL Root CA" -out ca.crt

openssl req -newkey rsa:4096 -nodes -keyout api-fw.key \
-subj "/C=US/ST=CO/L=a53/O=Testing/CN=api-fw" -out api-fw.csr

openssl x509 -req -extfile <(printf "subjectAltName=DNS:api-fw,DNS:api-fw.io") \
-days 365 -in api-fw.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out api-fw.crt