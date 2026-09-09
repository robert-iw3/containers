# CSV connector

Tails delimited files in `CSV_LOG_DIR`, maps each record through `schemas.yaml`, and posts it
to Splunk HEC or to Elasticsearch.

The loop, offsets, schema matching, time coercion, retry and HEC framing are
shared with the other formats in [`core/`](../../core/). This directory holds
the parser wiring, the schemas and the image.

**Read [`../../README.md`](../../README.md) first** — it carries the delivery
contract, the full configuration table and the rules every format inherits.

## Files

```
csv_splunk_connector.py          entry point, Splunk HEC
csv_elasticsearch_connector.py   entry point, Elasticsearch _bulk
schemas.yaml                     schema definitions, first match wins in file order
Dockerfile                       one image, ENABLE_SPLUNK picks the destination
docker-compose.yml               both services, with resource limits
csv-splunk-deployment.yaml       Kubernetes manifest
deploy_csv_connectors.py         deployment script
deploy_csv_connectors.yml        Ansible playbook
```

## Build and run

The image needs `core/`, so build from the connectors root rather than here:

```bash
cd ../..
podman build -f csv/python/Dockerfile -t csv-connector .
```

`docker-compose.yml` already sets that context:

```bash
cd ../..
podman compose -f csv/python/docker-compose.yml up -d csv-splunk
```

`CONNECTOR_HEC_URL` and `CONNECTOR_HEC_TOKEN` have no defaults. A connector
pointed at a placeholder reports send failures forever instead of saying it is
unconfigured.

## Settings specific to this format

`CSV_DELIMITER` (default `,`) is configuration, not a guess. Sniffing it
from content returns a comma for any file containing one anywhere, so a
semicolon-delimited export parses as a single column and every mapped
field comes back empty.

The header is read once and stored with the offset. A resumed read starts
mid-file where no header line exists, and a reader left to find one there
treats the first data row as the header.

## Offsets

Offsets live at `STATE_PATH` and advance only after the destination
acknowledges the events. Mount a volume on `/var/lib/connector` or a restart
re-sends every file from the beginning.

## Tests

```bash
cd ../../uat && ./run-uat.sh csv-trellix
```
