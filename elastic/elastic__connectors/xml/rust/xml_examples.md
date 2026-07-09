# XML Example Inputs for XML Connector

This document provides example XML inputs for the Rust-based XML connector (`xml-connector`), which parses XML logs from `/var/log/xml_data` and forwards them to Splunk (CIM-compliant) and/or Elasticsearch (ECS-compliant). Each example corresponds to a schema defined in `schemas.yaml`, covering common log types such as network, system, application, security, and industrial control system (ICS) logs. The connector uses a `schema_key` (e.g., `event_type`, `log_type`) to identify the schema and map fields to CIM or ECS.

## Overview

- **Purpose**: The XML connector processes large XML files (multi-GB, 10,000+ events/second) from diverse sources, supporting multiple schemas.
- **Schema Identification**: Each XML event includes a `schema_key` (e.g., `event_type`, `log_type`) as an element or attribute matching a `schema_value` in `schemas.yaml`.
- **Field Mappings**: Fields are mapped to Splunk CIM or Elasticsearch ECS, with unmapped fields preserved in `xml.raw` (ECS).
- **Format**: XML with a root `<events>` element containing multiple `<event>` elements.

## Example XML Inputs

### 1. simple_event.xml

**Purpose**: Represents generic network events, such as traffic logs from routers or switches.

- **Use Case**: Network monitoring, traffic analysis.
- **Schema Key**: `event_type=network_event`
- **Fields**:
  - `event_type`: Schema identifier (`network_event`).
  - `id`: Unique event ID.
  - `timestamp`: ISO 8601 timestamp.
  - `category`: Event category (e.g., `network`).
  - `source/ip`, `source/port`: Source IP and port.
  - `destination/ip`, `destination/port`: Destination IP and port.
  - `protocol`: Network protocol (e.g., `tcp`).
  - `bytes_sent`, `bytes_received`: Data transferred.
  - `action`: Action taken (e.g., `allowed`).

- **Example**:
  ```xml
  <events>
    <event>
      <event_type>network_event</event_type>
      <id>12345</id>
      <timestamp>2025-08-27T22:42:00Z</timestamp>
      <category>network</category>
      <source>
        <ip>192.168.1.10</ip>
        <port>12345</port>
      </source>
      <destination>
        <ip>10.0.0.20</ip>
        <port>80</port>
      </destination>
      <protocol>tcp</protocol>
      <bytes_sent>1024</bytes_sent>
      <bytes_received>2048</bytes_received>
      <action>allowed</action>
    </event>
  </events>
  ```

- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `network.protocol`, `event.action`.
  - **CIM**: `source`, `dest`, `protocol`, `action`, `sourcetype=xml:simple_event`.

### 2. scada_modbus.xml

**Purpose**: Captures Modbus protocol events from ICS environments.

- **Use Case**: SCADA monitoring, industrial network security.
- **Schema Key**: `event_type=modbus_event`
- **Fields**:
  - `event_type`: Schema identifier (`modbus_event`).
  - `transaction_id`: Unique transaction ID.
  - `timestamp`: ISO 8601 timestamp.
  - `client/ip`, `client/port`: Client IP and port.
  - `server/ip`, `server/port`: Server IP and port.
  - `function_code`: Modbus function code (e.g., `3`).

- **Example**:
  ```xml
  <events>
    <event>
      <event_type>modbus_event</event_type>
      <transaction_id>67890</transaction_id>
      <timestamp>2025-08-27T22:42:01Z</timestamp>
      <client>
        <ip>192.168.1.100</ip>
        <port>502</port>
      </client>
      <server>
        <ip>10.0.0.200</ip>
        <port>502</port>
      </server>
      <function_code>3</function_code>
    </event>
  </events>
  ```

- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `network.protocol=modbus`, `event.dataset=xml.scada_modbus`.
  - **CIM**: `source`, `dest`, `app=modbus`, `sourcetype=xml:scada_modbus`.

### 3. network_flow.xml

**Purpose**: Represents network flow data (e.g., NetFlow, IPFIX).

- **Use Case**: Network traffic analysis, bandwidth monitoring.
- **Schema Key**: `event_type=flow`
- **Fields**:
  - `event_type`: Schema identifier (`flow`).
  - `flow_id`: Unique flow ID.
  - `timestamp`: ISO 8601 timestamp.
  - `src/ip`, `src/port`: Source IP and port.
  - `dst/ip`, `dst/port`: Destination IP and port.
  - `proto`: Protocol (e.g., `tcp`).
  - `bytes_out`, `bytes_in`: Bytes sent/received.
  - `duration_ms`: Flow duration in milliseconds.
  - `packets_out`, `packets_in`: Packets sent/received.

- **Example**:
  ```xml
  <events>
    <event>
      <event_type>flow</event_type>
      <flow_id>54321</flow_id>
      <timestamp>2025-08-27T22:42:02Z</timestamp>
      <src>
        <ip>192.168.1.50</ip>
        <port>54321</port>
      </src>
      <dst>
        <ip>10.0.0.100</ip>
        <port>443</port>
      </dst>
      <proto>tcp</proto>
      <bytes_out>5120</bytes_out>
      <bytes_in>10240</bytes_in>
      <duration_ms>1500</duration_ms>
      <packets_out>10</packets_out>
      <packets_in>20</packets_in>
    </event>
  </events>
  ```

- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `network.bytes`, `event.duration`.
  - **CIM**: `source`, `dest`, `bytes_in`, `bytes_out`, `sourcetype=xml:network_flow`.

### 4. syslog.xml

**Purpose**: Captures syslog messages from systems or devices.

- **Use Case**: System monitoring, log aggregation.
- **Schema Key**: `log_type=syslog`
- **Fields**:
  - `log_type`: Schema identifier (`syslog`).
  - `message_id`: Unique message ID.
  - `timestamp`: ISO 8601 timestamp.
  - `hostname`: Hostname of the source.
  - `severity`: Log level (e.g., `info`).
  - `message`: Log message.
  - `facility`: Syslog facility.

- **Example**:
  ```xml
  <events>
    <event>
      <log_type>syslog</log_type>
      <message_id>98765</message_id>
      <timestamp>2025-08-27T22:42:03Z</timestamp>
      <hostname>server01</hostname>
      <severity>info</severity>
      <message>Login successful</message>
      <facility>auth</facility>
    </event>
  </events>
  ```

- **Mappings**:
  - **ECS**: `host.name`, `log.level`, `message`.
  - **CIM**: `host`, `severity`, `message`, `sourcetype=syslog`.

### 5. windows_event.xml

**Purpose**: Captures Windows event logs.

- **Use Case**: System security, audit logging.
- **Schema Key**: `log_type=windows_event`
- **Fields**:
  - `log_type`: Schema identifier (`windows_event`).
  - `event_id`: Unique event ID.
  - `timestamp`: ISO 8601 timestamp.
  - `computer_name`: Hostname of the Windows system.
  - `user`: Username associated with the event.
  - `logon_type`: Logon type (e.g., `3` for network).
  - `event_code`: Windows event code.
  - `message`: Event description.

- **Example**:
  ```xml
  <events>
    <event>
      <log_type>windows_event</log_type>
      <event_id>45678</event_id>
      <timestamp>2025-08-27T22:42:04Z</timestamp>
      <computer_name>WIN-SERVER01</computer_name>
      <user>admin</user>
      <logon_type>3</logon_type>
      <event_code>4624</event_code>
      <message>Successful logon</message>
    </event>
  </events>
  ```

- **Mappings**:
  - **ECS**: `host.name`, `user.name`, `event.code`.
  - **CIM**: `host`, `user`, `event_code`, `sourcetype=wineventlog`.

### 6. web_access.xml

**Purpose**: Captures web server access logs.

- **Use Case**: Web traffic analysis, security monitoring.
- **Schema Key**: `event_type=web_access`
- **Fields**:
  - `event_type`: Schema identifier (`web_access`).
  - `request_id`: Unique request ID.
  - `timestamp`: ISO 8601 timestamp.
  - `client/ip`: Client IP address.
  - `method`: HTTP method (e.g., `GET`).
  - `url`: Requested URL.
  - `status_code`: HTTP status code.
  - `user_agent`: User agent string.
  - `bytes_out`, `bytes_in`: Bytes sent/received.
  - `response_time_ms`: Response time in milliseconds.

- **Example**:
  ```xml
  <events>
    <event>
      <event_type>web_access</event_type>
      <request_id>23456</request_id>
      <timestamp>2025-08-27T22:42:05Z</timestamp>
      <client>
        <ip>192.168.1.150</ip>
      </client>
      <method>GET</method>
      <url>/index.html</url>
      <status_code>200</status_code>
      <user_agent>Mozilla/5.0</user_agent>
      <bytes_out>1024</bytes_out>
      <bytes_in>512</bytes_in>
      <response_time_ms>50</response_time_ms>
    </event>
  </events>
  ```

- **Mappings**:
  - **ECS**: `client.ip`, `http.request.method`, `url.full`, `http.response.status_code`.
  - **CIM**: `source`, `http_method`, `url`, `status`, `sourcetype=access_combined`.

### 7. authentication.xml

**Purpose**: Captures authentication events.

- **Use Case**: Security monitoring, user activity tracking.
- **Schema Key**: `event_type=auth`
- **Fields**:
  - `event_type`: Schema identifier (`auth`).
  - `auth_id`: Unique authentication ID.
  - `timestamp`: ISO 8601 timestamp.
  - `user`: Username.
  - `src/ip`: Source IP address.
  - `outcome`: Authentication result (e.g., `success`).
  - `auth_type`: Authentication type (e.g., `password`).
  - `message`: Event description.

- **Example**:
  ```xml
  <events>
    <event>
      <event_type>auth</event_type>
      <auth_id>34567</auth_id>
      <timestamp>2025-08-27T22:42:05Z</timestamp>
      <user>jdoe</user>
      <src>
        <ip>192.168.1.200</ip>
      </src>
      <outcome>success</outcome>
      <auth_type>password</auth_type>
      <message>User authenticated</message>
    </event>
  </events>
  ```

- **Mappings**:
  - **ECS**: `user.name`, `source.ip`, `event.outcome`.
  - **CIM**: `user`, `source`, `action`, `sourcetype=auth`.

### 8. ids_alert.xml

**Purpose**: Captures IDS/IPS alerts (e.g., Snort, Suricata).

- **Use Case**: Intrusion detection, threat hunting.
- **Schema Key**: `event_type=ids_alert`
- **Fields**:
  - `event_type`: Schema identifier (`ids_alert`).
  - `alert_id`: Unique alert ID.
  - `timestamp`: ISO 8601 timestamp.
  - `src/ip`, `src/port`: Source IP and port.
  - `dst/ip`, `dst/port`: Destination IP and port.
  - `proto`: Protocol (e.g., `tcp`).
  - `signature`: Alert signature.
  - `category`: Alert category (e.g., `malign`).
  - `severity`: Alert severity (e.g., `high`).

- **Example**:
  ```xml
  <events>
    <event>
      <event_type>ids_alert</event_type>
      <alert_id>11223</alert_id>
      <timestamp>2025-08-27T22:42:05Z</timestamp>
      <src>
        <ip>192.168.1.200</ip>
        <port>54321</port>
      </src>
      <dst>
        <ip>10.0.0.50</ip>
        <port>80</port>
      </dst>
      <proto>tcp</proto>
      <signature>ET SCAN Suspicious</signature>
      <category>malign</category>
      <severity>high</severity>
    </event>
  </events>
  ```

- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `rule.name`, `event.severity`.
  - **CIM**: `source`, `dest`, `signature`, `sourcetype=ids`.

### 9. scada_dnp3.xml

**Purpose**: Captures DNP3 protocol events from ICS environments.

- **Use Case**: Industrial network monitoring, SCADA security.
- **Schema Key**: `event_type=dnp3_event`
- **Fields**:
  - `event_type`: Schema identifier (`dnp3_event`).
  - `transaction_id`: Unique transaction ID.
  - `timestamp`: ISO 8601 timestamp.
  - `client/ip`, `client/port`: Client IP and port.
  - `server/ip`, `server/port`: Server IP and port.
  - `function_code`: DNP3 function code (e.g., `2`).
  - `point_address`: Data point address.

- **Example**:
  ```xml
  <events>
    <event>
      <event_type>dnp3_event</event_type>
      <transaction_id>78901</transaction_id>
      <timestamp>2025-08-27T22:42:06Z</timestamp>
      <client>
        <ip>192.168.1.100</ip>
        <port>20000</port>
      </client>
      <server>
        <ip>10.0.0.200</ip>
        <port>20000</port>
      </server>
      <function_code>2</function_code>
      <point_address>1001</point_address>
    </event>
  </events>
  ```

- **Mappings**:
  - **ECS**: `source.ip`, `destination.ip`, `network.protocol=dnp3`, `event.dataset=xml.scada_dnp3`.
  - **CIM**: `source`, `dest`, `app=dnp3`, `sourcetype=xml:scada_dnp3`.

## Notes

- **Format**: XML with a root `<events>` element containing multiple `<event>` elements.
- **Unmapped Fields**: Preserved in `xml.raw` (ECS) for analysis.
- **Error Handling**: Malformed XML elements or missing schemas are logged and skipped.
- **Performance**: The Rust connector supports 10,000+ events/second using asynchronous concurrency, optimized for low memory and CPU usage.
- **Customization**: Add new schemas to `schemas.yaml` for custom XML formats.

## Usage

1. Place XML files in `/var/log/xml_data` (see examples above).
2. Ensure `schemas.yaml` is in `/app/schemas.yaml` (or as configured in `XML_LOG_DIR`).
3. Deploy using `deploy_xml_connectors.py` or `deploy_xml_connectors.yml` (see `README.md`).
4. Verify in Splunk (`index=xml source=xml:*`) or Elasticsearch (`curl http://localhost:9200/xml-logs/_search`).

For further customization or additional schemas, edit `schemas.yaml` or consult the `README.md` for deployment details.