<p align="center">
  <img src="https://www.elastic.co/security-labs/grid.svg" />
</p>

## Ingesting data

All NDJSON documents are structured in ECS format so they can be ingested by the Elastic Agent or Filebeat.

### The Elastic Agent

Instructions below are to upload the ECS NDJSON document using the Elastic Agent.

1. In Kibana, create a Fleet policy with the [Custom Logs integration](https://docs.elastic.co/integrations/log).
2. Define the Log file path (`/path/to/documents/*.ndjson`)
3. Click the Advanced options dropdown and enter the following in the Custom configurations box
```
json:
  keys_under_root: true
  add_error_key: true
  overwrite_keys: true
```
4. Click Save integration
5. Install and enroll the Elastic Agent on the endpoint where the NDJSON documents are located
6. Check the `logs-*` data view in Kibana

![image](https://user-images.githubusercontent.com/7442091/234921587-0e660a67-c773-4518-8894-38b890ad8b8d.png)

### Filebeat

Instructions below are to upload the ECS NDJSON document using Filebeat.

1. [Install Filebeat](https://www.elastic.co/guide/en/beats/filebeat/current/filebeat-installation-configuration.html)
2. [Enable the Filestream input](https://www.elastic.co/guide/en/beats/filebeat/current/configuration-filebeat-options.html)
3. Add the directory of the `.ndjson` document
4. Add the NDJSON configuration options to `filebeat.yml`

```yaml
...truncated
filebeat.inputs:

# Each - is an input. Most options can be set at the input level, so
# you can use different inputs for various configurations.
# Below are the input specific configurations.

# filestream is an input for collecting log messages from files.
- type: filestream

# Change to true to enable this input configuration
enabled: true

# Paths that should be crawled and fetched. Glob based paths
paths:
  - /path/to/documents/*.ndjson
parsers:
  - ndjson:
      target: ""
      add_error_key: true
...truncated
```

5. Configure the [output](https://www.elastic.co/guide/en/beats/filebeat/current/configuring-output.html)
6. Check your configuration with `filebeat test output` and `filebeat test config`
7. Run the Filebeat setup `filebeat setup`
8. Start Filebeat and check the `filebeat-*` data view in Kibana

## Threat Hunting Queries

See ../../threat_hunting/elastic_security for examples of ES|QL hunting.
