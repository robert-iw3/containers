# Data pipeline

Two interchangeable log shippers that ingest from external sources and deliver to
the Elastic stack over TLS. Both attach to the running stack the same way as the
other add-ons (see `../ADDONS.md`): they join the stack network and trust its CA.

| Shipper | Directory | Use it for |
| --- | --- | --- |
| Logstash | `logstash/` | Rich parsing/enrichment (grok, geoip, dissect, translate, dedup) |
| Fluentd | `fluentd/` | Lightweight forwarding with a small footprint |

Pick one (or run both). Each has an `examples/` directory of ready-to-adapt
ingestion configs.

## Logstash

The deployed pipeline (`logstash/pipeline/logstash.conf`) accepts:

- Beats on `5044`
- JSON lines over TCP `50000`
- JSON over UDP `5140`

Every event is routed to a `logs-<dataset>-<namespace>` data stream. Set
`[data_stream][dataset]` / `[data_stream][namespace]` in a filter to control the
destination; they default to `generic` / `default`. Dataset names line up with
`../siem/datasets.yml`, so matching SIEM ILM policies and index templates apply.

See `logstash/examples/` for grok/geoip/dissect/dedup patterns.

## Fluentd

`fluentd/conf/fluent.conf` forwards everything to Elasticsearch over TLS, driven by
`FLUENT_ELASTICSEARCH_*` env (host, `https` scheme, `ca_file`, credentials). It
includes `conf.d/*.conf`; drop an example from `fluentd/examples/conf.d/` in to add
a source.

## Run

```bash
# the stack is already up (docker compose up -d from ../)
cd logstash        # or fluentd
docker compose up -d --build
```
