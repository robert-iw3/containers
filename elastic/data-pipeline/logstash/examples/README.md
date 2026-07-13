# Logstash example pipelines

Reference pipelines to build from. The deployed pipeline (`../pipeline/logstash.conf`)
is intentionally minimal: it accepts Beats/TCP/UDP input and routes every event
to a `logs-<dataset>-<namespace>` data stream over TLS. These examples show how to
parse and enrich specific log types before that routing.

| File | Shows |
| --- | --- |
| `syslog-grok.conf` | `grok` + `date` + `syslog_pri` parsing of RFC3164 syslog |
| `nginx-access-geoip.conf` | `grok` combined log, `geoip`, `useragent`, conditional `drop` |
| `json-app-dissect-dedup.conf` | `json` codec, `dissect`, `translate`, `fingerprint` de-dup to a classic index |

## Using one

Add it to the pipeline mount and register it in `config/pipelines.yml`, e.g.:

```yaml
- pipeline.id: syslog
  path.config: "/usr/share/logstash/pipeline/syslog-grok.conf"
```

Then either copy the file into `../pipeline/` before building the image, or bind
mount it in `docker-compose.yml`. Each example is self-contained (its own input
and output) so it can also run as a standalone pipeline.

## Routing notes

- Data streams route by the `[data_stream][dataset]` / `[data_stream][namespace]`
  fields; set them in a `filter` (as the examples do) and keep
  `data_stream_auto_routing => true` in the output.
- Use a classic `index =>` (not a data stream) when you need a custom
  `document_id`, since data streams are append-only.
- Dataset names align with `../../../siem/datasets.yml`, so SIEM ILM policies and
  index templates apply automatically when a dataset matches (e.g. `siem.auth`).
