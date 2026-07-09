#!/usr/bin/env python3

"""
pip install cryptography
python generate_cert.py --cn myserver.com --org MyCompany --ou DevOps --country US --state NY --locality NYC --key-size 4096 --ca-validity 3650 --cert-validity 730 --out-dir ./certs --key-pass mypass

Notes

The script generates RSA keys with SHA256 signatures, suitable for most use cases (e.g., Splunk/Elastic integrations).
The CA certificate is self-signed and marked as a CA (BasicConstraints: ca=True).
The server certificate includes SubjectAlternativeName for the CN and is suitable for server authentication.
For production, secure the private keys (ca.key, server.key) and consider using a vault solution.
The script validates inputs minimally; ensure valid inputs for fields like country (2-letter ISO code).

This script can be integrated with the Cribl deployment by placing the generated server.crt and server.key in the certs/ directory for Splunk SSL integration, replacing the placeholder client.pem.

Enhanced: added key password, better arg validation.
"""

import argparse
import os
from datetime import datetime, timedelta, timezone
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import re

def parse_args():
    parser = argparse.ArgumentParser(description="Generate CA, key, CSR, and certificate with customizable fields.")
    parser.add_argument('--cn', default='example.com', help="Common Name (CN) for the certificate (default: example.com)")
    parser.add_argument('--org', default='MyOrg', help="Organization (O) for the certificate (default: MyOrg)")
    parser.add_argument('--ou', default='IT', help="Organizational Unit (OU) for the certificate (default: IT)")
    parser.add_argument('--country', default='US', help="Country (C) for the certificate (default: US)")
    parser.add_argument('--state', default='CA', help="State (ST) for the certificate (default: CA)")
    parser.add_argument('--locality', default='San Francisco', help="Locality (L) for the certificate (default: San Francisco)")
    parser.add_argument('--key-size', type=int, default=4096, choices=[2048, 4096], help="Key size in bits (default: 4096)")
    parser.add_argument('--ca-validity', type=int, default=3650, help="CA certificate validity in days (default: 10 years)")
    parser.add_argument('--cert-validity', type=int, default=730, help="Certificate validity in days (default: 2 years)")
    parser.add_argument('--out-dir', default='certs', help="Output directory for generated files (default: certs)")
    parser.add_argument('--key-pass', help="Password for encrypting private keys (recommended for prod)")
    args = parser.parse_args()
    if not re.match(r'^[A-Z]{2}$', args.country):
        parser.error("Country must be 2-letter ISO code")
    if args.key_size < 2048:
        parser.error("Key size must be at least 2048")
    return args

def generate_ca_key():
    """Generate a CA private key."""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=args.key_size,
        backend=default_backend()
    )

def generate_ca_cert(ca_key):
    """Generate a self-signed CA certificate."""
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, f"{args.cn} CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, args.org),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, args.ou),
        x509.NameAttribute(NameOID.COUNTRY_NAME, args.country),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, args.state),
        x509.NameAttribute(NameOID.LOCALITY_NAME, args.locality),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=args.ca_validity))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256(), default_backend())
    )
    return cert

def generate_server_key():
    """Generate a server private key."""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=args.key_size,
        backend=default_backend()
    )

def generate_csr(server_key):
    """Generate a CSR with customizable fields."""
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, args.cn),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, args.org),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, args.ou),
            x509.NameAttribute(NameOID.COUNTRY_NAME, args.country),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, args.state),
            x509.NameAttribute(NameOID.LOCALITY_NAME, args.locality),
        ]))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(args.cn)]),
            critical=False,
        )
        .sign(server_key, hashes.SHA256(), default_backend())
    )
    return csr

def generate_server_cert(csr, ca_key, ca_cert):
    """Generate a server certificate signed by the CA."""
    cert = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca_cert.subject)
        .public_key(csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=args.cert_validity))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(args.cn)]),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                data_encipherment=True,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256(), default_backend())
    )
    return cert

def save_file(filename, content, mode='wb'):
    """Save content to a file in the output directory."""
    os.makedirs(args.out_dir, exist_ok=True)
    filepath = os.path.join(args.out_dir, filename)
    with open(filepath, mode) as f:
        f.write(content)
    print(f"Saved: {filepath}")

def main():
    global args
    args = parse_args()
    encryption = serialization.BestAvailableEncryption(args.key_pass.encode()) if args.key_pass else serialization.NoEncryption()

    # Generate CA key and certificate
    ca_key = generate_ca_key()
    ca_cert = generate_ca_cert(ca_key)

    # Generate server key and CSR
    server_key = generate_server_key()
    csr = generate_csr(server_key)

    # Generate server certificate
    server_cert = generate_server_cert(csr, ca_key, ca_cert)

    # Save files
    save_file('ca.key', ca_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=encryption
    ))
    save_file('ca.crt', ca_cert.public_bytes(serialization.Encoding.PEM))
    save_file('server.key', server_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=encryption
    ))
    save_file('server.csr', csr.public_bytes(serialization.Encoding.PEM))
    save_file('server.crt', server_cert.public_bytes(serialization.Encoding.PEM))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        exit(1)