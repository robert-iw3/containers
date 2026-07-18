"""
demo-api: proves the mesh + dynamic-credentials story end to end.

Every GET / does:
  1. read its Vault token (scoped to database/creds/app-readonly),
  2. ask Vault for fresh short-lived PostgreSQL credentials,
  3. query PostgreSQL through the local Consul Connect sidecar upstream
     (mTLS between sidecars, enforced by service intentions).
"""

import json
import os
import ssl
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import psycopg

VAULT_ADDR = os.environ.get("VAULT_ADDR", "https://vault:8200")
VAULT_CACERT = os.environ.get("VAULT_CACERT", "/vault-certs/vault-ca.crt.pem")
TOKEN_FILE = os.environ.get("VAULT_TOKEN_FILE", "/demo-state/app-token")
CREDS_PATH = os.environ.get("VAULT_CREDS_PATH", "database/creds/app-readonly")
DB_HOST = os.environ.get("MESH_UPSTREAM_HOST", "api-sidecar")
DB_PORT = int(os.environ.get("MESH_UPSTREAM_PORT", "20001"))
DB_NAME = os.environ.get("APP_DB_NAME", "appdb")


def vault_db_creds():
    with open(TOKEN_FILE) as f:
        token = f.read().strip()
    ctx = ssl.create_default_context(cafile=VAULT_CACERT)
    req = urllib.request.Request(
        f"{VAULT_ADDR}/v1/{CREDS_PATH}", headers={"X-Vault-Token": token}
    )
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        body = json.load(resp)
    return body["data"]["username"], body["data"]["password"], body["lease_duration"]


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        payload = json.dumps(obj, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def do_GET(self):
        if self.path == "/healthz":
            self._send(200, {"status": "ok"})
            return
        try:
            user, password, ttl = vault_db_creds()
            with psycopg.connect(
                host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                user=user, password=password, connect_timeout=10,
            ) as conn, conn.cursor() as cur:
                cur.execute("SELECT current_user, now(), (SELECT count(*) FROM customers)")
                db_user, db_time, rows = cur.fetchone()
            self._send(200, {
                "status": "ok",
                "db_user_from_vault": db_user,
                "credential_ttl_seconds": ttl,
                "db_time": db_time.isoformat(),
                "customer_rows": rows,
                "path": "demo-api -> api-sidecar -> mTLS mesh -> postgres-sidecar -> postgres-app",
            })
        except Exception as exc:  # surface the failure to the smoke test
            self._send(500, {"status": "error", "error": str(exc)})


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
