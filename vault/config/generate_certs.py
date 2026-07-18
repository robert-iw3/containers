"""
Generate a self-signed CA and server certificate for Vault.

Idempotent: exits early if the server certificate for this node already
exists, so container restarts do not regenerate (and desynchronize) the CA.

Environment:
  VAULT_NODE_ID          node index, default "0" (CA is created by node 0)
  VAULT_TLS_EXTRA_SANS   comma-separated extra SANs, e.g. "DNS:vault.example.com,IP:10.0.0.5"
"""

import os
import subprocess

CERTS_DIR = os.environ.get("VAULT_CERTS_DIR", "/certs")


def generate_vault_certs(certs_dir=CERTS_DIR, node_id="0"):
    os.makedirs(certs_dir, exist_ok=True)

    server_cert = f"{certs_dir}/vault-{node_id}.crt.pem"
    if os.path.exists(server_cert):
        print(f"{server_cert} already exists, skipping certificate generation")
        return

    alt_names = [
        "DNS.1 = vault.local",
        "DNS.2 = vault",
        f"DNS.3 = vault-{node_id}",
        "DNS.4 = localhost",
        "IP.1 = 127.0.0.1",
    ]
    dns_i, ip_i = 5, 2
    for san in filter(None, os.environ.get("VAULT_TLS_EXTRA_SANS", "").split(",")):
        kind, _, value = san.strip().partition(":")
        if kind.upper() == "DNS":
            alt_names.append(f"DNS.{dns_i} = {value}")
            dns_i += 1
        elif kind.upper() == "IP":
            alt_names.append(f"IP.{ip_i} = {value}")
            ip_i += 1

    csr_conf = f"""
[ req ]
default_bits = 4096
prompt = no
default_md = sha384
req_extensions = req_ext
distinguished_name = dn

[ dn ]
C = US
ST = CO
L = Denver
O = HashiCorp
OU = Vault
CN = vault.local

[ req_ext ]
subjectAltName = @alt_names
keyUsage = critical, nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = critical, serverAuth

[ alt_names ]
{os.linesep.join(alt_names)}
"""

    with open(f"{certs_dir}/vault-csr.conf", "w") as f:
        f.write(csr_conf)

    if node_id == "0" and not os.path.exists(f"{certs_dir}/vault-ca.crt.pem"):
        subprocess.run(["openssl", "genrsa", "-out", f"{certs_dir}/vault-ca.key.pem", "4096"], check=True)
        subprocess.run([
            "openssl", "req", "-new", "-x509", "-sha256", "-days", "730",
            "-key", f"{certs_dir}/vault-ca.key.pem",
            "-subj", "/C=US/ST=CO/L=Denver/O=HashiCorp/CN=Vault CA",
            # OpenSSL 3 strict validation (e.g. python 3.13 clients) rejects
            # CA certs without an explicit keyUsage extension
            "-addext", "basicConstraints=critical,CA:TRUE",
            "-addext", "keyUsage=critical,keyCertSign,cRLSign",
            "-out", f"{certs_dir}/vault-ca.crt.pem"
        ], check=True)

    subprocess.run(["openssl", "genrsa", "-out", f"{certs_dir}/vault-{node_id}.key.pem", "4096"], check=True)
    subprocess.run([
        "openssl", "req", "-new", "-key", f"{certs_dir}/vault-{node_id}.key.pem",
        "-out", f"{certs_dir}/vault-{node_id}.csr", "-config", f"{certs_dir}/vault-csr.conf"
    ], check=True)

    subprocess.run([
        "openssl", "x509", "-req", "-in", f"{certs_dir}/vault-{node_id}.csr",
        "-CA", f"{certs_dir}/vault-ca.crt.pem", "-CAkey", f"{certs_dir}/vault-ca.key.pem",
        "-CAcreateserial", "-sha256", "-out", server_cert,
        "-days", "365",
        "-extensions", "req_ext", "-extfile", f"{certs_dir}/vault-csr.conf"
    ], check=True)

    for file in ["vault-ca.key.pem", f"vault-{node_id}.key.pem"]:
        os.chmod(f"{certs_dir}/{file}", 0o600)
    for file in ["vault-ca.crt.pem", server_cert.split("/")[-1]]:
        os.chmod(f"{certs_dir}/{file}", 0o644)

    for file in ["vault-csr.conf", f"vault-{node_id}.csr", "vault-ca.srl"]:
        if os.path.exists(f"{certs_dir}/{file}"):
            os.remove(f"{certs_dir}/{file}")

    print(f"Generated CA and server certificate for node {node_id} in {certs_dir}")


if __name__ == "__main__":
    generate_vault_certs(node_id=os.environ.get("VAULT_NODE_ID", "0"))
