# Creating schemas.yaml for Rust Parquet Connector (Elastic ECS)

This guide explains how to create the `schemas.yaml` file for the Rust-based Parquet connector, which processes Parquet files and sends ECS-compliant data to Elasticsearch. The `schemas.yaml` file maps columns from Parquet files to Elastic Common Schema (ECS) fields, enabling consistent indexing and analysis in Elasticsearch and Kibana. This document outlines the structure, best practices, and validation steps for creating a robust and extensible schema.

## Overview
The Rust Parquet connector (`parquet-connector`) reads Parquet files from a specified directory, transforms data to ECS format, and sends it to Elasticsearch via the Bulk API. The `schemas.yaml` file defines how Parquet columns map to ECS fields for various data sources (e.g., network logs, authentication events). The schema is loaded in `schema.rs` using `serde_yaml` and validated in `handler.rs` during processing.

## Structure of schemas.yaml
The `schemas.yaml` file is a YAML document with a list of schema entries, each corresponding to a Parquet file or data source. Each entry includes:
- `name`: A unique identifier for the schema (e.g., `network_events`).
- `file_name`: The Parquet file name (e.g., `network_events.parquet`).
- `timestamp_field`: The Parquet column used for incremental processing and mapped to ECS `@timestamp`.
- `mappings.ecs`: A dictionary mapping ECS field names to Parquet column names or static values.

Example `schemas.yaml`:
```yaml
schemas:
  - name: network_events
    file_name: network_events.parquet
    timestamp_field: timestamp
    mappings:
      ecs:
        '@timestamp': timestamp
        'event.category': '"network"'
        'source.ip': source_ip
        'source.port': source_port
        'destination.ip': dest_ip
        'destination.port': dest_port
        'network.protocol': protocol
        'network.bytes': bytes_received
  - name: authentication_events
    file_name: auth_events.parquet
    timestamp_field: login_time
    mappings:
      ecs:
        '@timestamp': login_time
        'user.name': username
        'event.outcome': outcome
        'source.ip': source_ip
        'host.name': dest_host
```

## Steps to Create schemas.yaml
1. **Identify Parquet Data Sources**:
   - Determine the types of data in your Parquet files (e.g., network traffic, authentication logs, system logs, web access, IDS alerts).
   - Example: A network log Parquet file might have columns: `timestamp`, `source_ip`, `dest_ip`, `protocol`.

2. **Map to ECS Fields**:
   - Refer to the [ECS Field Reference](https://www.elastic.co/guide/en/ecs/current/ecs-field-reference.html) for field definitions.
   - Map Parquet columns to ECS fields based on semantic meaning:
     - `timestamp` → `@timestamp` (required, ISO 8601 format).
     - `source_ip` → `source.ip`.
     - `protocol` → `network.protocol`.
   - Use static values (enclosed in quotes) for constant fields (e.g., `"network"` for `event.category`).
   - Ensure `ecs.version` is added programmatically (set to `"8.0.0"` in `handler.rs`).

3. **Define Schema Entries**:
   - Create a schema entry for each Parquet file or data type.
   - Specify `file_name` to match the Parquet file in the `DATA_DIR`.
   - Set `timestamp_field` to the column used for `@timestamp` and incremental processing (e.g., `timestamp`).
   - In `mappings.ecs`, list ECS fields and their corresponding Parquet columns or static values.

4. **Handle Diverse Data Sources**:
   - Create entries for various sources to support multiple Parquet files.
   - Example sources:
     - **Network Events**: Map to `source.ip`, `destination.ip`, `network.protocol`.
     - **Authentication Events**: Map to `user.name`, `event.outcome`.
     - **System Logs**: Map to `log.level`, `message`.
     - **Web Access**: Map to `http.request.method`, `url.original`.
     - **IDS Alerts**: Map to `event.category="intrusion_detection"`, `message`.

5. **Validate and Test**:
   - Ensure `@timestamp` is mapped to a valid timestamp column.
   - Validate Parquet schemas against `mappings.ecs` during processing (handled in `handler.rs`).
   - Test with sample Parquet files to confirm ECS output matches expectations.

## Best Practices
- **ECS Compliance**: Use exact ECS field names (e.g., `source.ip`, not `src_ip`). Include `@timestamp` and let `handler.rs` add `ecs.version`.
- **Timestamp Format**: Ensure `timestamp_field` is in a format convertible to ISO 8601 (e.g., `2023-01-01T00:00:00Z`).
- **Static Values**: Enclose static values in quotes (e.g., `"network"`) to distinguish from column names.
- **Extensibility**: Add new schema entries for new Parquet files without changing code.
- **Error Handling**: Rely on `handler.rs` to log missing fields during validation for debugging.
- **Minimal Mapping**: Map only relevant fields to avoid unnecessary data in Elasticsearch.

## Example for Multiple Data Sources
Below is an expanded `schemas.yaml` covering common data sources:
```yaml
schemas:
  - name: network_events
    file_name: network_events.parquet
    timestamp_field: timestamp
    mappings:
      ecs:
        '@timestamp': timestamp
        'event.category': '"network"'
        'source.ip': source_ip
        'source.port': source_port
        'destination.ip': dest_ip
        'destination.port': dest_port
        'network.protocol': protocol
        'network.bytes': bytes_received
  - name: authentication_events
    file_name: auth_events.parquet
    timestamp_field: login_time
    mappings:
      ecs:
        '@timestamp': login_time
        'user.name': username
        'event.outcome': outcome
        'source.ip': source_ip
        'host.name': dest_host
  - name: system_log
    file_name: system_log.parquet
    timestamp_field: timestamp
    mappings:
      ecs:
        '@timestamp': timestamp
        'event.category': '"system"'
        'log.level': severity
        'message': message
        'host.name': hostname
  - name: web_access
    file_name: web_access.parquet
    timestamp_field: timestamp
    mappings:
      ecs:
        '@timestamp': timestamp
        'event.category': '"web"'
        'http.request.method': method
        'url.original': url
        'http.response.status_code': status_code
        'user_agent.original': user_agent
        'source.ip': client_ip
  - name: ids_alert
    file_name: ids_alert.parquet
    timestamp_field: timestamp
    mappings:
      ecs:
        '@timestamp': timestamp
        'event.category': '"intrusion_detection"'
        'source.ip': src_ip
        'source.port': src_port
        'destination.ip': dst_ip
        'destination.port': dst_port
        'network.protocol': proto
        'event.outcome': severity
        'message': signature
```

## Validation
- **Syntax**: Ensure `schemas.yaml` is valid YAML (test with `serde_yaml::from_str`).
- **Field Validation**: `handler.rs` validates that Parquet columns exist for mapped ECS fields, logging missing fields.
- **Testing**: Create sample Parquet files matching each `file_name` and verify ECS output in Elasticsearch:
  - Network events: `{ "@timestamp": "2023-01-01T00:00:00Z", "ecs": {"version": "8.0.0"}, "event.category": "network", "source.ip": "192.168.1.1", ... }`
  - Authentication events: `{ "@timestamp": "2023-01-01T00:00:00Z", "ecs": {"version": "8.0.0"}, "user.name": "alice", ... }`
- **Incremental Processing**: Ensure `timestamp_field` is set for incremental mode to filter processed rows.

## Troubleshooting
- **Missing Fields**: Check logs for warnings about missing Parquet columns.
- **Timestamp Issues**: Verify `timestamp_field` format is compatible with ISO 8601.
- **Schema Reload**: Ensure `schemas.yaml` changes are detected by `notify` in `schema.rs`.

## Notes
- The connector does not support partitioned Parquet datasets fully (single files only). Future enhancements could use `arrow::dataset`.
- Add authentication fields (e.g., `ES_AUTH`) in `deploy_config.yaml` for secure Elasticsearch access.