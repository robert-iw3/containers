import os
import subprocess
import shutil

def generate_vault_certs(certs_dir="/certs", node_id="0"):
    os.makedirs(certs_dir, exist_ok=True)

    # Certificate configuration
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
DNS.1 = vault.local
DNS.2 = localhost
IP.1 = 127.0.0.1
"""

    # Write CSR configuration
    with open(f"{certs_dir}/vault-csr.conf", "w") as f:
        f.write(csr_conf)

    # Generate CA key and certificate (only for node 0)
    if node_id == "0":
        subprocess.run(["openssl", "genrsa", "-out", f"{certs_dir}/vault-ca.key.pem", "4096"], check=True)
        subprocess.run([
            "openssl", "req", "-new", "-x509", "-sha256", "-days", "730",
            "-key", f"{certs_dir}/vault-ca.key.pem",
            "-subj", "/C=US/ST=CO/L=Denver/O=HashiCorp/CN=Vault CA",
            "-out", f"{certs_dir}/vault-ca.crt.pem"
        ], check=True)

    # Generate server key and CSR
    subprocess.run(["openssl", "genrsa", "-out", f"{certs_dir}/vault-{node_id}.key.pem", "4096"], check=True)
    subprocess.run([
        "openssl", "req", "-new", "-key", f"{certs_dir}/vault-{node_id}.key.pem",
        "-out", f"{certs_dir}/vault-{node_id}.csr", "-config", f"{certs_dir}/vault-csr.conf"
    ], check=True)

    # Sign server certificate
    subprocess.run([
        "openssl", "x509", "-req", "-in", f"{certs_dir}/vault-{node_id}.csr",
        "-CA", f"{certs_dir}/vault-ca.crt.pem", "-CAkey", f"{certs_dir}/vault-ca.key.pem",
        "-CAcreateserial", "-sha256", "-out", f"{certs_dir}/vault-{node_id}.crt.pem",
        "-days", "365", "-extfile", f"{certs_dir}/vault-csr.conf"
    ], check=True)

    # Set permissions
    for file in [f"vault-ca.key.pem", f"vault-ca.crt.pem", f"vault-{node_id}.key.pem", f"vault-{node_id}.crt.pem"]:
        if os.path.exists(f"{certs_dir}/{file}"):
            os.chmod(f"{certs_dir}/{file}", 0o640)
            subprocess.run(["chown", "vault:vault", f"{certs_dir}/{file}"], check=True)

    # Clean up temporary files
    for file in ["vault-csr.conf", f"vault-{node_id}.csr", "vault-ca.srl"]:
        if os.path.exists(f"{certs_dir}/{file}"):
            os.remove(f"{certs_dir}/{file}")

if __name__ == "__main__":
    node_id = os.environ.get("VAULT_NODE_ID", "0")
    generate_vault_certs(certs_dir="/certs", node_id=node_id)