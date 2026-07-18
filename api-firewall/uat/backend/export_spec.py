"""Print the app's generated OpenAPI 3.0.2 spec as JSON on stdout.

Used by run-uat.sh (via docker exec) so the firewall always validates
against the exact contract the app publishes.
"""
import json

from main import app

print(json.dumps(app.openapi(), indent=2, sort_keys=True))
