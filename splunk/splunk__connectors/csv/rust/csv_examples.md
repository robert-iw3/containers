# CSV Example Inputs for Splunk and Elasticsearch Connectors

This document explains the example CSV inputs for the Rust-based CSV connector, which parses CSV logs from `/var/log/csv_data` and forwards them to Splunk (CIM-compliant) or Elasticsearch (ECS-compliant). Each example corresponds to a schema defined in `schemas.yaml`, covering common log types such as network, system, application, security, and industrial control system (ICS) logs. The connector uses a `schema_key` (e.g., `event_type`, `log_type`) to identify the schema and map fields to CIM or ECS.

## Overview
- **Purpose**: The CSV connector processes large CSV files (multi-GB, 10,000+ events/second) from diverse sources, supporting multiple schemas.
- **Schema Identification**: Each CSV row includes a `schema_key` (e.g., `event_type`, `log_type`) matching a `schema_value` in `schemas.yaml`.
- **Field Mappings**: Fields are mapped to Splunk CIM or Elasticsearch ECS, with unmapped fields preserved in `csv.raw` (ECS).
- **Delimiter**: Supports multiple delimiters (`,`, `;`, `\t`, `|`), detected automatically or configured via `CSV_DELIMITER`.

## Example CSV Inputs

### 1. simple_event.csv
**Purpose**: Represents generic network events, such as traffic logs from routers or switches.
- **Use Case**: Network monitoring, traffic analysis.
- **Schema Key**: `event_type=network_event`
- **Fields**:
  - `event_type`: Schema identifier (`network_event`).
  - `id`: Unique event ID.
  - `timestamp`: ISO 8601 timestamp (e.g., `2025-08-27T22:42:00Z`).
  - `category`: Event category (e.g., `network`).
  - `source_ip`, `source_port`: Source IP and port.
  - `dest_ip`, `dest_port`: Destination IP and port.
  - `protocol`: Network protocol (e.g., `tcp`, `udp`).
  - `bytes_sent`, `bytes_received`: Data transferred.
  - `action`: Action taken (e.g., `allowed`, `blocked`).
- **Example**:
  ```csv
  event_type,id,timestamp,category,source_ip,source_port,dest_ip,dest_port,protocol,bytes_sent,bytes_received,action
  network_event,12345,2025-08-27T22:42:00Z,network,192.168.1.10,12345,10.0.0.20,80,tcp,1024,2048,allowed
  ```
- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `network.protocol`, `event.action`.
  - **CIM**: `source`, `dest`, `protocol`, `action`, `sourcetype=csv:simple_event`.

### 2. scada_modbus.csv
**Purpose**: Captures Modbus protocol events from industrial control systems (ICS).
- **Use Case**: SCADA monitoring, industrial network security.
- **Schema Key**: `event_type=modbus_event`
- **Fields**:
  - `event_type`: Schema identifier (`modbus_event`).
  - `transaction_id`: Unique transaction ID.
  - `timestamp`: ISO 8601 timestamp.
  - `client_ip`, `client_port`: Client IP and port.
  - `server_ip`, `server_port`: Server IP and port.
  - `function_code`: Modbus function code (e.g., `3` for Read Holding Registers).
- **Example**:
  ```csv
  event_type,transaction_id,timestamp,client_ip,client_port,server_ip,server_port,function_code
  modbus_event,67890,2025-08-27T22:42:01Z,192.168.1.100,502,10.0.0.200,502,3
  ```
- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `network.protocol=modbus`, `event.dataset=csv.scada_modbus`.
  - **CIM**: `source`, `dest`, `app=modbus`, `sourcetype=csv:scada_modbus`.

### 3. network_flow.csv
**Purpose**: Represents NetFlow, firewall, or VPN traffic logs.
- **Use Case**: Network performance, security monitoring.
- **Schema Key**: `event_type=flow`
- **Fields**:
  - `event_type`: Schema identifier (`flow`).
  - `flow_id`: Unique flow ID.
  - `timestamp`: ISO 8601 timestamp.
  - `src_ip`, `src_port`: Source IP and port.
  - `dst_ip`, `dst_port`: Destination IP and port.
  - `proto`: Protocol (e.g., `tcp`, `udp`).
  - `bytes_out`, `bytes_in`: Data transferred.
  - `duration_ms`: Flow duration in milliseconds.
  - `packets_out`, `packets_in`: Packet counts.
- **Example**:
  ```csv
  event_type,flow_id,timestamp,src_ip,src_port,dst_ip,dst_port,proto,bytes_out,bytes_in,duration_ms,packets_out,packets_in
  flow,54321,2025-08-27T22:42:02Z,192.168.1.50,54321,10.0.0.100,443,tcp,4096,8192,500,10,15
  ```
- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `network.protocol`, `network.bytes`.
  - **CIM**: `source`, `dest`, `protocol`, `sourcetype=csv:network_flow`.

### 4. authentication.csv
**Purpose**: Represents authentication events (e.g., SSH, Active Directory).
- **Use Case**: Security monitoring, user activity tracking.
- **Schema Key**: `event_type=auth`
- **Fields**:
  - `event_type`: Schema identifier (`auth`).
  - `auth_id`: Unique authentication ID.
  - `timestamp`: ISO 8601 timestamp.
  - `user`: Username.
  - `src_ip`: Source IP of the authentication attempt.
  - `outcome`: Result (e.g., `success`, `failure`).
  - `auth_type`: Authentication method (e.g., `ssh`, `kerberos`).
  - `message`: Event description.
- **Example**:
  ```csv
  event_type,auth_id,timestamp,user,src_ip,outcome,auth_type,message
  auth,45678,2025-08-27T22:42:04Z,jsmith,192.168.1.100,success,ssh,SSH login successful
  ```
- **Mappings**:
  - **ECS**: `user.name`, `source.ip`, `event.outcome`.
  - **CIM**: `user`, `source`, `action`, `sourcetype=csv:auth`.

### 5. ids_alert.csv
**Purpose**: Captures IDS/IPS alerts (e.g., Snort, Suricata).
- **Use Case**: Intrusion detection, threat hunting.
- **Schema Key**: `event_type=ids_alert`
- **Fields**:
  - `event_type`: Schema identifier (`ids_alert`).
  - `alert_id`: Unique alert ID.
  - `timestamp`: ISO 8601 timestamp.
  - `src_ip`, `src_port`: Source IP and port.
  - `dst_ip`, `dst_port`: Destination IP and port.
  - `proto`: Protocol (e.g., `tcp`, `udp`).
  - `signature`: Alert signature (e.g., `ET SCAN Suspicious`).
  - `category`: Alert category (e.g., `malign`).
  - `severity`: Alert severity (e.g., `high`, `medium`).
- **Example**:
  ```csv
  event_type,alert_id,timestamp,src_ip,src_port,dst_ip,dst_port,proto,signature,category,severity
  ids_alert,11223,2025-08-27T22:42:05Z,192.168.1.200,54321,10.0.0.50,80,tcp,ET SCAN Suspicious,malign,high
  ```
- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `rule.name`, `event.severity`.
  - **CIM**: `source`, `dest`, `signature`, `sourcetype=csv:ids`.

### 6. scada_dnp3.csv
**Purpose**: Captures DNP3 protocol events from ICS environments.
- **Use Case**: Industrial network monitoring, SCADA security.
- **Schema Key**: `event_type=dnp3_event`
- **Fields**:
  - `event_type`: Schema identifier (`dnp3_event`).
  - `transaction_id`: Unique transaction ID.
  - `timestamp`: ISO 8601 timestamp.
  - `client_ip`, `client_port`: Client IP and port.
  - `server_ip`, `server_port`: Server IP and port.
  - `function_code`: DNP3 function code (e.g., `2` for Read).
  - `point_address`: Data point address.
- **Example**:
  ```csv
  event_type,transaction_id,timestamp,client_ip,client_port,server_ip,server_port,function_code,point_address
  dnp3_event,78901,2025-08-27T22:42:06Z,192.168.1.100,20000,10.0.0.200,20000,2,1001
  ```
- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `network.protocol=dnp3`, `event.dataset=csv.scada_dnp3`.
  - **CIM**: `source`, `dest`, `app=dnp3`, `sourcetype=csv:scada_dnp3`.

## Notes
- **Delimiter**: The connector detects delimiters (`,`, `;`, `\t`, `|`) or uses `CSV_DELIMITER` from `deploy_config.yaml`.
- **Unmapped Fields**: Preserved in `csv.raw` (ECS) for analysis.
- **Error Handling**: Malformed rows or missing schemas are logged and skipped.
- **Performance**: Supports 10,000+ events/second with Tokio-based async processing.
- **Customization**: Add new schemas to `schemas.yaml` for custom CSV formats.

## Usage
1. Place CSV files in `/var/log/csv_data`.
2. Ensure `schemas.yaml` is in `/app/schemas.yaml` (or as configured).
3. Deploy using `deploy_csv_connectors.rs` or `deploy_csv_connectors.yml` (see `README.md`).
4. Verify in Splunk (`index=csv source=csv:*`) or Elasticsearch (`curl http://localhost:9200/csv-logs/_search`).

For further customization or additional schemas, edit `schemas.yaml` or consult the connector documentation.