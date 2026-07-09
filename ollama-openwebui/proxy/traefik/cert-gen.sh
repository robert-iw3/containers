#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    source .env
else
    echo "Error: .env file not found"
    exit 1
fi

# Create required directories
mkdir -p ./certs
chmod 755 ./certs

# Generate SSL self-signed certificates
openssl req -x509 \
    -nodes \
    -days 365 \
    -newkey rsa:2048 \
    -keyout ./certs/cert.key \
    -out ./certs/cert.crt \
    -subj "/CN=$HOSTNAME" \
    -addext "subjectAltName = DNS:$HOSTNAME"

# Define certificates permissions
chmod 644 ./certs/cert.crt
chmod 600 ./certs/cert.key