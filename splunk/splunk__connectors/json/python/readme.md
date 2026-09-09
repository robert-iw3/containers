# JSON connector

Tails newline-delimited JSON in `JSON_LOG_DIR`, maps each record through `schemas.yaml`, and posts it
to Splunk HEC or to Elasticsearch.

The loop, offsets, schema matching, time coercion, retry and HEC framing are
shared with the other formats in [`core/`](../../core/). This directory holds
the parser wiring, the schemas and the image.

**Read [`../../README.md`](../../README.md) first** — it carries the delivery
contract, the full configuration table and the rules every format inherits.

## Files

```
json_splunk_connector.py          entry point, Splunk HEC
json_elasticsearch_connector.py   entry point, Elasticsearch _bulk
schemas.yaml                     schema definitions, first match wins in file order
Dockerfile                       one image, ENABLE_SPLUNK picks the destination
docker-compose.yml               both services, with resource limits
json-splunk-deployment.yaml       Kubernetes manifest
deploy_json_connectors.py         deployment script
deploy_json_connectors.yml        Ansible playbook
```

## Build and run

The image needs `core/`, so build from the connectors root rather than here:

```bash
cd ../..
podman build -f json/python/Dockerfile -t json-connector .
```

`docker-compose.yml` already sets that context:

```bash
cd ../..
podman compose -f json/python/docker-compose.yml up -d json-splunk
```

`CONNECTOR_HEC_URL` and `CONNECTOR_HEC_TOKEN` have no defaults. A connector
pointed at a placeholder reports send failures forever instead of saying it is
unconfigured.

## Settings specific to this format

One object per line. A line that will not parse is forwarded carrying its
own text under `_raw` with `_parse_error` set, so malformed input is
searchable rather than a gap in the timeline.

Mapping values may use dotted paths (`source.ip`, `destination.port`) to
address nested objects. A flat key of the same name wins over the walk.

## Offsets

Offsets live at `STATE_PATH` and advance only after the destination
acknowledges the events. Mount a volume on `/var/lib/connector` or a restart
re-sends every file from the beginning.

## Tests

```bash
cd ../../uat && ./run-uat.sh json-generic
```
