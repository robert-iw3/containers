#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import ast

load_dotenv()
BASE = Path(__file__).parent
CERTS_DIR = BASE / "certs"
CERTS_DIR.mkdir(exist_ok=True)

VM_SPECS = ast.literal_eval(os.getenv("VM_SPECS", "{}"))

def generate_certs():
    if (CERTS_DIR / "ca" / "ca.crt").exists():
        print("Certs already exist.")
        return

    instances_yml = "instances:\n"
    for name, spec in VM_SPECS.items():
        instances_yml += f"  - name: {name}\n"
        instances_yml += f"    dns: [{name}, {name}.local]\n"
        instances_yml += f"    ip: [{spec['ip']}]\n"

    (CERTS_DIR / "instances.yml").write_text(instances_yml)

    print("Generating certs with real IPs...")
    subprocess.run([
        "docker", "run", "--rm",
        "-v", f"{CERTS_DIR}:/certs",
        f"docker.elastic.co/elasticsearch/elasticsearch:9.2.0",
        "bash", "-c",
        """
        set -e
        bin/elasticsearch-certutil ca --pem --out /certs/ca.zip --silent
        unzip -o /certs/ca.zip -d /certs
        bin/elasticsearch-certutil cert --ca-cert /certs/ca/ca.crt --ca-key /certs/ca/ca.key --in /certs/instances.yml --out /certs/certs.zip --pem
        unzip -o /certs/certs.zip -d /certs
        for i in $(ls /certs | grep -v ca); do
          cat /certs/$i/$i.crt /certs/ca/ca.crt > /certs/$i/$i.chain.pem
        done
        chown -R 1000:1000 /certs
        """
    ], check=True)
    print("Certs generated in ./certs/")

if __name__ == "__main__":
    generate_certs()