# XML Example Inputs for Splunk and Elasticsearch Connectors

This document explains the example XML inputs for the XML connectors (`xml_splunk_connector.py` and `xml_elasticsearch_connector.py`), which parse XML logs from `/var/log/xml_data` and forward them to Splunk (CIM-compliant) or Elasticsearch (ECS-compliant). Each example corresponds to a schema defined in `schemas.yaml`, covering common log types such as network, system, application, security, and industrial control system (ICS) logs. The connectors use a `schema_key` (e.g., `event_type`, `log_type`) to identify the schema and map fields to CIM or ECS.

## Overview

- **Purpose**: The XML connectors process large XML files (multi-GB, 10,000+ events/second) from diverse sources, supporting multiple schemas.
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

**Purpose**: Represents NetFlow, firewall, or VPN traffic logs.

- **Use Case**: Network performance, security monitoring.

- **Schema Key**: `event_type=flow`

- **Fields**:

  - `event_type`: Schema identifier (`flow`).
  - `flow_id`: Unique flow ID.
  - `timestamp`: ISO 8601 timestamp.
  - `src/ip`, `src/port`: Source IP and port.
  - `dst/ip`, `dst/port`: Destination IP and port.
  - `proto`: Protocol (e.g., `tcp`).
  - `bytes_out`, `bytes_in`: Data transferred.
  - `duration_ms`: Flow duration in milliseconds.
  - `packets_out`, `packets_in`: Packet counts.

- **Example**:

  ```xml
  <events>
    <event>
      <event_type>flow</event_type>
      <flow_id>54321</flow_id>
      <timestamp>2025-08-27T22:42:00Z</timestamp>
      <src>
        <ip>192.168.1.10</ip>
        <port>12345</port>
      </src>
      <dst>
        <ip>10.0.0.20</ip>
        <port>80</port>
      </dst>
      <proto>tcp</proto>
      <bytes_out>1024</bytes_out>
      <bytes_in>2048</bytes_in>
      <duration_ms>500</duration_ms>
      <packets_out>10</packets_out>
      <packets_in>15</packets_in>
    </event>
  </events>
  ```

- **Mappings**:

  - **ECS**: `source.ip`, `destination.ip`, `network.bytes`, `event.duration`.
  - **CIM**: `source`, `dest`, `bytes_in`, `bytes_out`, `sourcetype=xml:network_flow`.

### 4. syslog.xml

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

  ```xml
  <events>
    <event>
      <log_type>syslog</log_type>
      <timestamp>2025-08-27T22:42:01Z</timestamp>
      <message_id>123</message_id>
      <hostname>server1</hostname>
      <severity>INFO</severity>
      <facility>auth</facility>
      <message>User logged in successfully</message>
    </event>
  </events>
  ```

- **Mappings**:

  - **ECS**: `host.name`, `log.level`, `message`.
  - **CIM**: `host`, `severity`, `sourcetype=syslog`.

### 5. windows_event.xml

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

  ```xml
  <events>
    <event>
      <log_type>windows_event</log_type>
      <timestamp>2025-08-27T22:42:02Z</timestamp>
      <event_id>4624</event_id>
      <computer_name>DC01</computer_name>
      <user>jsmith</user>
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

**Purpose**: Captures web server access logs (e.g., Apache, Nginx).

- **Use Case**: Web traffic analysis, security monitoring.

- **Schema Key**: `event_type=web_access`

- **Fields**:

  - `event_type`: Schema identifier (`web_access`).
  - `request_id`: Unique request ID.
  - `timestamp`: ISO 8601 timestamp.
  - `client/ip`: Client IP address.
  - `method`: HTTP method (e.g., `GET`).
  - `url`: Requested URL.
  - `status_code`: HTTP status code (e.g., `200`).
  - `user_agent`: Client user agent.
  - `bytes_out`, `bytes_in`: Data transferred.
  - `response_time_ms`: Response time in milliseconds.

- **Example**:

  ```xml
  <events>
    <event>
      <event_type>web_access</event_type>
      <request_id>98765</request_id>
      <timestamp>2025-08-27T22:42:03Z</timestamp>
      <client>
        <ip>192.168.1.100</ip>
      </client>
      <method>GET</method>
      <url>/index.html</url>
      <status_code>200</status_code>
      <user_agent>Mozilla/5.0</user_agent>
      <bytes_out>2048</bytes_out>
      <bytes_in>1024</bytes_in>
      <response_time_ms>50</response_time_ms>
    </event>
  </events>
  ```

- **Mappings**:

  - **ECS**: `client.ip`, `http.method`, `url.full`, `http.response.status_code`.
  - **CIM**: `source`, `http_method`, `url`, `sourcetype=access_combined`.

### 7. authentication.xml

**Purpose**: Represents authentication events.

- **Use Case**: Security monitoring, user activity tracking.

- **Schema Key**: `event_type=auth`

- **Fields**:

  - `event_type`: Schema identifier (`auth`).
  - `auth_id`: Unique authentication ID.
  - `timestamp`: ISO 8601 timestamp.
  - `user`: Username.
  - `src/ip`: Source IP.
  - `outcome`: Result (e.g., `success`).
  - `auth_type`: Authentication method (e.g., `ssh`).
  - `message`: Event description.

- **Example**:

  ```xml
  <events>
    <event>
      <event_type>auth</event_type>
      <auth_id>45678</auth_id>
      <timestamp>2025-08-27T22:42:04Z</timestamp>
      <user>jsmith</user>
      <src>
        <ip>192.168.1.100</ip>
      </src>
      <outcome>success</outcome>
      <auth_type>ssh</auth_type>
      <message>SSH login successful</message>
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
- **Performance**: Supports 10,000+ events/second with multiprocessing.
- **Customization**: Add new schemas to `schemas.yaml` for custom XML formats.

## Usage

1. Place XML files in `/var/log/xml_data`.
2. Ensure `schemas.yaml` is in `/app/schemas.yaml` (or as configured).
3. Deploy using `deploy_xml_connectors.py` or `deploy_xml_connectors.yml` (see `README.md`).
4. Verify in Splunk (`index=xml source=xml:*`) or Elasticsearch (`curl http://localhost:9200/xml-logs/_search`).

For further customization or additional schemas, edit `schemas.yaml` or consult the connector documentation.xml_examples.mdxml_examples.md