"""
Print the app's generated OpenAPI 3.0.2 spec as JSON on stdout.

Run inside the container (no DB needed — the spec is static):
    docker compose exec api python3 export_spec.py > ../openapi.json
"""
import json
import os

# main.py imports db.py which requires SQL_PASSWORD; the spec itself does
# not need a database, so satisfy the import with a dummy when unset.
os.environ.setdefault("SQL_PASSWORD", "spec-export-only")

from main import app  # noqa: E402

print(json.dumps(app.openapi(), indent=2, sort_keys=True))
