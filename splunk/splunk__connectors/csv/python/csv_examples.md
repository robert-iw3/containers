# CSV Example Inputs for Splunk and Elasticsearch Connectors

This document explains the example CSV inputs for the CSV connectors (`csv_splunk_connector.py` and `csv_elasticsearch_connector.py`), which parse CSV logs from `/var/log/csv_data` and forward them to Splunk (CIM-compliant) or Elasticsearch (ECS-compliant). Each example corresponds to a schema defined in `schemas.yaml`, covering common log types such as network, system, application, security, and industrial control system (ICS) logs. The connectors use a `schema_key` (e.g., `event_type`, `log_type`) to identify the schema and map fields to CIM or ECS.

## Overview
- **Purpose**: The CSV connectors process large CSV files (multi-GB, 10,000+ events/second) from diverse sources, supporting multiple schemas.
- **Schema Identification**: Each CSV row includes a `schema_key` (e.g., `event_type`, `log_type`) matching a `schema_value` in `schemas.yaml`.
- **Field Mappings**: Fields are mapped to Splunk CIM or Elasticsearch ECS, with unmapped fields preserved in `csv.raw` (ECS).
- **Delimiter**: Supports multiple delimiters (`,`, `;`, `\t`, `|`), detected via `python-magic` or configured via `CSV_DELIMITER`.

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
  flow,54321,2025-08-27T22:42:00Z,192.168.1.10,12345,10.0.0.20,80,tcp,1024,2048,500,10,15
  ```
- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `network.bytes`, `event.duration`.
  - **CIM**: `source`, `dest`, `bytes_in`, `bytes_out`, `sourcetype=csv:network_flow`.

### 4. syslog.csv
**Purpose**: Captures Linux/Unix system logs (e.g., `/var/log/syslog`).
- **Use Case**: System monitoring, troubleshooting.
- **Schema Key**: `log_type=syslog`
- **Fields**:
  - `log_type`: Schema identifier (`syslog`).
  - `timestamp`: ISO 8601 timestamp.
  - `message_id`: Unique message ID.
  - `hostname`: Host generating the log.
  - `severity`: Log level (e.g., `INFO`, `ERROR`).
  - `facility`: Syslog facility (e.g., `auth`, `kern`).
  - `message`: Log message.
- **Example**:
  ```csv
  log_type,timestamp,message_id,hostname,severity,facility,message
  syslog,2025-08-27T22:42:01Z,123,server1,INFO,auth,User logged in successfully
  ```
- **Mappings**:
  - **ECS**: `host.name`, `log.level`, `message`.
  - **CIM**: `host`, `severity`, `sourcetype=syslog`.

### 5. windows_event.csv
**Purpose**: Represents Windows Event Logs (e.g., Security, System).
- **Use Case**: Security auditing, system monitoring.
- **Schema Key**: `log_type=windows_event`
- **Fields**:
  - `log_type`: Schema identifier (`windows_event`).
  - `timestamp`: ISO 8601 timestamp.
  - `event_id`: Event ID (e.g., `4624` for logon).
  - `computer_name`: Hostname of the Windows machine.
  - `user`: User associated with the event.
  - `logon_type`: Logon type (e.g., `3` for network).
  - `event_code`: Windows event code.
  - `message`: Event description.
- **Example**:
  ```csv
  log_type,timestamp,event_id,computer_name,user,logon_type,event_code,message
  windows_event,2025-08-27T22:42:02Z,4624,DC01,jsmith,3,4624,Successful logon
  ```
- **Mappings**:
  - **ECS**: `host.name`, `user.name`, `event.code`.
  - **CIM**: `host`, `user`, `event_code`, `sourcetype=wineventlog`.

### 6. web_access.csv
**Purpose**: Captures web server access logs (e.g., Apache, Nginx).
- **Use Case**: Web traffic analysis, security monitoring.
- **Schema Key**: `event_type=web_access`
- **Fields**:
  - `event_type`: Schema identifier (`web_access`).
  - `request_id`: Unique request ID.
  - `timestamp`: ISO 8601 timestamp.
  - `client_ip`: Client IP address.
  - `method`: HTTP method (e.g., `GET`, `POST`).
  - `url`: Requested URL.
  - `status_code`: HTTP status code (e.g., `200`, `404`).
  - `user_agent`: Client user agent.
  - `bytes_out`, `bytes_in`: Data transferred.
  - `response_time_ms`: Response time in milliseconds.
- **Example**:
  ```csv
  event_type,request_id,timestamp,client_ip,method,url,status_code,user_agent,bytes_out,bytes_in,response_time_ms
  web_access,98765,2025-08-27T22:42:03Z,192.168.1.100,GET,/index.html,200,Mozilla/5.0,2048,1024,50
  ```
- **Mappings**:
  - **ECS**: `client.ip`, `http.method`, `url.full`, `http.response.status_code`.
  - **CIM**: `source`, `http_method`, `url`, `sourcetype=access_combined`.

### 7. authentication.csv
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
  - **CIM**: `user`, `source`, `action`, `sourcetype=auth`.

### 8. ids_alert.csv
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
  - **CIM**: `source`, `dest`, `signature`, `sourcetype=ids`.

### 9. scada_dnp3.csv
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
- **Delimiter**: The connectors detect delimiters (`,`, `;`, `\t`, `|`) or use `CSV_DELIMITER` from `deploy_config.yaml`.
- **Unmapped Fields**: Preserved in `csv.raw` (ECS) for analysis.
- **Error Handling**: Malformed rows or missing schemas are logged and skipped.
- **Performance**: Supports 10,000+ events/second with multiprocessing.
- **Customization**: Add new schemas to `schemas.yaml` for custom CSV formats.

## Usage
1. Place CSV files in `/var/log/csv_data`.
2. Ensure `schemas.yaml` is in `/app/schemas.yaml` (or as configured).
3. Deploy using `deploy_csv_connectors.py` or `deploy_csv_connectors.yml` (see `README.md`).
4. Verify in Splunk (`index=csv source=csv:*`) or Elasticsearch (`curl http://localhost:9200/csv-logs/_search`).

For further customization or additional schemas, edit `schemas.yaml` or consult the connector documentation.