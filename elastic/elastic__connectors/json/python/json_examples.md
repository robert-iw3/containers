# JSON Example Inputs for Splunk and Elasticsearch Connectors

This document explains the example JSON inputs for the JSON connectors (`json_splunk_connector.py` and `json_elasticsearch_connector.py`), which parse JSON Lines (JSONL) logs from `/var/log/json_data` and forward them to Splunk (CIM-compliant) or Elasticsearch (ECS-compliant). Each example corresponds to a schema defined in `schemas.yaml`, covering common log types such as network, system, application, security, and industrial control system (ICS) logs. The connectors use a `schema_key` (e.g., `event_type`, `log_type`) to identify the schema and map fields to CIM or ECS.

## Overview
- **Purpose**: The JSON connectors process large JSONL files (multi-GB, 10,000+ events/second) from diverse sources, supporting multiple schemas.
- **Schema Identification**: Each JSON object includes a `schema_key` (e.g., `event_type`, `log_type`) matching a `schema_value` in `schemas.yaml`.
- **Field Mappings**: Fields are mapped to Splunk CIM or Elasticsearch ECS, with unmapped fields preserved in `json.raw` (ECS).
- **Format**: JSON Lines (one JSON object per line).

## Example JSON Inputs

### 1. simple_event.json
**Purpose**: Represents generic network events, such as traffic logs from routers or switches.
- **Use Case**: Network monitoring, traffic analysis.
- **Schema Key**: `event_type=network_event`
- **Fields**:
  - `event_type`: Schema identifier (`network_event`).
  - `id`: Unique event ID.
  - `timestamp`: ISO 8601 timestamp.
  - `category`: Event category (e.g., `network`).
  - `source`: Object with `ip` and `port`.
  - `destination`: Object with `ip` and `port`.
  - `protocol`: Network protocol (e.g., `tcp`).
  - `bytes_sent`, `bytes_received`: Data transferred.
  - `action`: Action taken (e.g., `allowed`).
- **Example**:
  ```json
  {"event_type":"network_event","id":"12345","timestamp":"2025-08-27T22:42:00Z","category":"network","source":{"ip":"192.168.1.10","port":12345},"destination":{"ip":"10.0.0.20","port":80},"protocol":"tcp","bytes_sent":1024,"bytes_received":2048,"action":"allowed"}
  ```
- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `network.protocol`, `event.action`.
  - **CIM**: `source`, `dest`, `protocol`, `action`, `sourcetype=json:simple_event`.

### 2. scada_modbus.json
**Purpose**: Captures Modbus protocol events from ICS environments.
- **Use Case**: SCADA monitoring, industrial network security.
- **Schema Key**: `event_type=modbus_event`
- **Fields**:
  - `event_type`: Schema identifier (`modbus_event`).
  - `transaction_id`: Unique transaction ID.
  - `timestamp`: ISO 8601 timestamp.
  - `client`: Object with `ip` and `port`.
  - `server`: Object with `ip` and `port`.
  - `function_code`: Modbus function code (e.g., `3`).
- **Example**:
  ```json
  {"event_type":"modbus_event","transaction_id":"67890","timestamp":"2025-08-27T22:42:01Z","client":{"ip":"192.168.1.100","port":502},"server":{"ip":"10.0.0.200","port":502},"function_code":3}
  ```
- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `network.protocol=modbus`, `event.dataset=json.scada_modbus`.
  - **CIM**: `source`, `dest`, `app=modbus`, `sourcetype=json:scada_modbus`.

### 3. network_flow.json
**Purpose**: Represents NetFlow, firewall, or VPN traffic logs.
- **Use Case**: Network performance, security monitoring.
- **Schema Key**: `event_type=flow`
- **Fields**:
  - `event_type`: Schema identifier (`flow`).
  - `flow_id`: Unique flow ID.
  - `timestamp`: ISO 8601 timestamp.
  - `src`: Object with `ip` and `port`.
  - `dst`: Object with `ip` and `port`.
  - `proto`: Protocol (e.g., `tcp`).
  - `bytes_out`, `bytes_in`: Data transferred.
  - `duration_ms`: Flow duration in milliseconds.
  - `packets_out`, `packets_in`: Packet counts.
- **Example**:
  ```json
  {"event_type":"flow","flow_id":"54321","timestamp":"2025-08-27T22:42:00Z","src":{"ip":"192.168.1.10","port":12345},"dst":{"ip":"10.0.0.20","port":80},"proto":"tcp","bytes_out":1024,"bytes_in":2048,"duration_ms":500,"packets_out":10,"packets_in":15}
  ```
- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `network.bytes`, `event.duration`.
  - **CIM**: `source`, `dest`, `bytes_in`, `bytes_out`, `sourcetype=json:network_flow`.

### 4. syslog.json
**Purpose**: Captures Linux/Unix system logs.
- **Use Case**: System monitoring, troubleshooting.
- **Schema Key**: `log_type=syslog`
- **Fields**:
  - `log_type`: Schema identifier (`syslog`).
  - `timestamp`: ISO 8601 timestamp.
  - `message_id`: Unique message ID.
  - `hostname`: Host generating the log.
  - `severity`: Log level (e.g., `INFO`).
  - `facility`: Syslog facility (e.g., `auth`).
  - `message`: Log message.
- **Example**:
  ```json
  {"log_type":"syslog","timestamp":"2025-08-27T22:42:01Z","message_id":"123","hostname":"server1","severity":"INFO","facility":"auth","message":"User logged in successfully"}
  ```
- **Mappings**:
  - **ECS**: `host.name`, `log.level`, `message`.
  - **CIM**: `host`, `severity`, `sourcetype=syslog`.

### 5. windows_event.json
**Purpose**: Represents Windows Event Logs.
- **Use Case**: Security auditing, system monitoring.
- **Schema Key**: `log_type=windows_event`
- **Fields**:
  - `log_type`: Schema identifier (`windows_event`).
  - `timestamp`: ISO 8601 timestamp.
  - `event_id`: Event ID (e.g., `4624`).
  - `computer_name`: Hostname.
  - `user`: User associated with the event.
  - `logon_type`: Logon type (e.g., `3`).
  - `event_code`: Windows event code.
  - `message`: Event description.
- **Example**:
  ```json
  {"log_type":"windows_event","timestamp":"2025-08-27T22:42:02Z","event_id":"4624","computer_name":"DC01","user":"jsmith","logon_type":3,"event_code":"4624","message":"Successful logon"}
  ```
- **Mappings**:
  - **ECS**: `host.name`, `user.name`, `event.code`.
  - **CIM**: `host`, `user`, `event_code`, `sourcetype=wineventlog`.

### 6. web_access.json
**Purpose**: Captures web server access logs (e.g., Apache, Nginx).
- **Use Case**: Web traffic analysis, security monitoring.
- **Schema Key**: `event_type=web_access`
- **Fields**:
  - `event_type`: Schema identifier (`web_access`).
  - `request_id`: Unique request ID.
  - `timestamp`: ISO 8601 timestamp.
  - `client`: Object with `ip`.
  - `method`: HTTP method (e.g., `GET`).
  - `url`: Requested URL.
  - `status_code`: HTTP status code (e.g., `200`).
  - `user_agent`: Client user agent.
  - `bytes_out`, `bytes_in`: Data transferred.
  - `response_time_ms`: Response time in milliseconds.
- **Example**:
  ```json
  {"event_type":"web_access","request_id":"98765","timestamp":"2025-08-27T22:42:03Z","client":{"ip":"192.168.1.100"},"method":"GET","url":"/index.html","status_code":200,"user_agent":"Mozilla/5.0","bytes_out":2048,"bytes_in":1024,"response_time_ms":50}
  ```
- **Mappings**:
  - **ECS**: `client.ip`, `http.method`, `url.full`, `http.response.status_code`.
  - **CIM**: `source`, `http_method`, `url`, `sourcetype=access_combined`.

### 7. authentication.json
**Purpose**: Represents authentication events.
- **Use Case**: Security monitoring, user activity tracking.
- **Schema Key**: `event_type=auth`
- **Fields**:
  - `event_type`: Schema identifier (`auth`).
  - `auth_id`: Unique authentication ID.
  - `timestamp`: ISO 8601 timestamp.
  - `user`: Username.
  - `src`: Object with `ip`.
  - `outcome`: Result (e.g., `success`).
  - `auth_type`: Authentication method (e.g., `ssh`).
  - `message`: Event description.
- **Example**:
  ```json
  {"event_type":"auth","auth_id":"45678","timestamp":"2025-08-27T22:42:04Z","user":"jsmith","src":{"ip":"192.168.1.100"},"outcome":"success","auth_type":"ssh","message":"SSH login successful"}
  ```
- **Mappings**:
  - **ECS**: `user.name`, `source.ip`, `event.outcome`.
  - **CIM**: `user`, `source`, `action`, `sourcetype=auth`.

### 8. ids_alert.json
**Purpose**: Captures IDS/IPS alerts (e.g., Snort, Suricata).
- **Use Case**: Intrusion detection, threat hunting.
- **Schema Key**: `event_type=ids_alert`
- **Fields**:
  - `event_type`: Schema identifier (`ids_alert`).
  - `alert_id`: Unique alert ID.
  - `timestamp`: ISO 8601 timestamp.
  - `src`: Object with `ip` and `port`.
  - `dst`: Object with `ip` and `port`.
  - `proto`: Protocol (e.g., `tcp`).
  - `signature`: Alert signature.
  - `category`: Alert category (e.g., `malign`).
  - `severity`: Alert severity (e.g., `high`).
- **Example**:
  ```json
  {"event_type":"ids_alert","alert_id":"11223","timestamp":"2025-08-27T22:42:05Z","src":{"ip":"192.168.1.200","port":54321},"dst":{"ip":"10.0.0.50","port":80},"proto":"tcp","signature":"ET SCAN Suspicious","category":"malign","severity":"high"}
  ```
- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `rule.name`, `event.severity`.
  - **CIM**: `source`, `dest`, `signature`, `sourcetype=ids`.

### 9. scada_dnp3.json
**Purpose**: Captures DNP3 protocol events from ICS environments.
- **Use Case**: Industrial network monitoring, SCADA security.
- **Schema Key**: `event_type=dnp3_event`
- **Fields**:
  - `event_type`: Schema identifier (`dnp3_event`).
  - `transaction_id`: Unique transaction ID.
  - `timestamp`: ISO 8601 timestamp.
  - `client`: Object with `ip` and `port`.
  - `server`: Object with `ip` and `port`.
  - `function_code`: DNP3 function code (e.g., `2`).
  - `point_address`: Data point address.
- **Example**:
  ```json
  {"event_type":"dnp3_event","transaction_id":"78901","timestamp":"2025-08-27T22:42:06Z","client":{"ip":"192.168.1.100","port":20000},"server":{"ip":"10.0.0.200","port":20000},"function_code":2,"point_address":1001}
  ```
- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `network.protocol=dnp3`, `event.dataset=json.scada_dnp3`.
  - **CIM**: `source`, `dest`, `app=dnp3`, `sourcetype=json:scada_dnp3`.

## Notes
- **Format**: JSON Lines (one object per line, no trailing commas).
- **Unmapped Fields**: Preserved in `json.raw` (ECS) for analysis.
- **Error Handling**: Malformed JSON lines or missing schemas are logged and skipped.
- **Performance**: Supports 10,000+ events/second with multiprocessing.
- **Customization**: Add new schemas to `schemas.yaml` for custom JSON formats.

## Usage
1. Place JSONL files in `/var/log/json_data`.
2. Ensure `schemas.yaml` is in `/app/schemas.yaml` (or as configured).
3. Deploy using `deploy_json_connectors.py` or `deploy_json_connectors.yml` (see `README.md`).
4. Verify in Splunk (`index=json source=json:*`) or Elasticsearch (`curl http://localhost:9200/json-logs/_search`).

For further customization or additional schemas, edit `schemas.yaml` or consult the connector documentation.