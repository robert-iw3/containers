#!/bin/bash

set -e

function root_ca{
    # create root CA private key
    openssl ecparam -genkey -name secp384r1 | openssl pkey -outform PEM -out splunkuf-ca.key -aes256
    # create CA
    openssl req -new -x509 -key splunkuf-ca.key -out splunkuf-ca.crt -days 1000 -config splunkuf-ca_openssl.conf
    # verify
    openssl x509 -noout -text -in splunkuf-ca.crt
}

function gen_cert{
    # create client private key
    openssl ecparam -genkey -name secp384r1 | openssl pkey -outform PEM -out splunkuf.key -aes256
    # generate CSR
    openssl req -new -key splunkuf.key -out splunkuf.csr -config splunkuf_openssl.conf
    # verify
    openssl req -noout -text -in splunkuf.csr
    # sign it with root CA
    openssl x509 -req -days 365 -in splunkuf.csr -CA splunkuf-ca.crt -CAkey splunkuf-ca.key -out splunkuf.crt -sha384 -copy_extensions=copyall
    # verify
    openssl x509 -noout -text -in splunkuf.crt
    # cert chain
    cat splunkuf.crt splunkuf.key splunkuf-ca.crt > client.pem
}

root_ca
gen_cert
cp client.pem /var/opt/splunk/etc/auth/client.pem
/opt/splunkforwarder/bin/splunk restart