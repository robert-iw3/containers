# Fluentd example ingestion

Fluentd is the alternative shipper to Logstash in this directory. `../conf/fluent.conf`
includes `conf.d/*.conf` and sends everything to Elasticsearch over TLS. These
examples are drop-in `conf.d` sources to build from.

| File | Shows |
| --- | --- |
| `syslog-grok.conf` | `syslog` input with the grok parser |
| `tail-json-app.conf` | `tail` a JSON log file with a position file, add host |
| `http-forward.conf` | `http` input, derive the dataset from the tag |

## Using one

Mount an example into the container's `conf.d` and it is picked up on start:

```yaml
volumes:
  - ./examples/conf.d/syslog-grok.conf:/fluentd/etc/conf.d/syslog-grok.conf:ro
```

## Notes

- The output in `fluent.conf` is driven by `FLUENT_ELASTICSEARCH_*` env (host,
  scheme `https`, `ca_file`, user/password). It trusts the stack CA mounted at
  `/certs/ca/ca.crt`.
- Set `FLUENT_ELASTICSEARCH_LOGSTASH_PREFIX` (or a `target_index_key`) to control
  the destination index/dataset. Logstash is the richer option when you need
  heavy parsing and enrichment; Fluentd is lighter for straight forwarding.
