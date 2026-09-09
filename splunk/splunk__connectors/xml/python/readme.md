# XML connector

Tails XML files in `XML_LOG_DIR`, maps each record through `schemas.yaml`, and posts it
to Splunk HEC or to Elasticsearch.

The loop, offsets, schema matching, time coercion, retry and HEC framing are
shared with the other formats in [`core/`](../../core/). This directory holds
the parser wiring, the schemas and the image.

**Read [`../../README.md`](../../README.md) first** — it carries the delivery
contract, the full configuration table and the rules every format inherits.

## Files

```
xml_splunk_connector.py          entry point, Splunk HEC
xml_elasticsearch_connector.py   entry point, Elasticsearch _bulk
schemas.yaml                     schema definitions, first match wins in file order
Dockerfile                       one image, ENABLE_SPLUNK picks the destination
docker-compose.yml               both services, with resource limits
xml-splunk-deployment.yaml       Kubernetes manifest
deploy_xml_connectors.py         deployment script
deploy_xml_connectors.yml        Ansible playbook
```

## Build and run

The image needs `core/`, so build from the connectors root rather than here:

```bash
cd ../..
podman build -f xml/python/Dockerfile -t xml-connector .
```

`docker-compose.yml` already sets that context:

```bash
cd ../..
podman compose -f xml/python/docker-compose.yml up -d xml-splunk
```

`CONNECTOR_HEC_URL` and `CONNECTOR_HEC_TOKEN` have no defaults. A connector
pointed at a placeholder reports send failures forever instead of saying it is
unconfigured.

## Settings specific to this format

Each top-level element is one event, flattened to its child element names.
`XML_RECORD_ELEM` restricts which element counts as a record; unset, every
top-level element does.

The parser adds `_element` and `_namespace`, so a schema can discriminate
on the element itself. Entity resolution, network access and `huge_tree`
are off: a connector reads files it did not write, and libxml2 with
entities enabled fetches external references on the document's request.

## Offsets

Offsets live at `STATE_PATH` and advance only after the destination
acknowledges the events. Mount a volume on `/var/lib/connector` or a restart
re-sends every file from the beginning.

## Tests

```bash
cd ../../uat && ./run-uat.sh xml-generic
```
