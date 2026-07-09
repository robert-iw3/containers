# OpenCTI SOC Prime Connector

The OpenCTI SOC Prime connector can be used to import rules (indicators) from the SOC Prime Platform.
The connector leverages the SOC Prime Threat Detection Marketplace API to get the rules.
Rules for importing can be selected using content lists or jobs created on the SOC Prime Platform.


## Installation

The OpenCTI SOC Prime connector is a standalone Python process that requires access to the OpenCTI platform, RabbitMQ and API Key to the SOC Prime CCM to be able to pull Sigma rules. RabbitMQ credentials and connection parameters are provided by the OpenCTI API directly, as configured in the platform settings.

Enabling this connector could be done by launching the Python process directly after
providing the correct configuration in the `config.yml` file or within a Docker with
the image `opencti/connector-socprime:latest`. We provide an example of
[`docker-compose.yml`](docker-compose.yml) file that could be used independently or
integrated to the global `docker-compose.yml` file of OpenCTI.

If you are using it independently, remember that the connector will try to connect to
RabbitMQ on the port configured in the OpenCTI platform.

## Configuration

The connector can be configured with the following variables:

| Config Parameter                 | Docker env var                              | Default                      | Description                                                                                             |
| -------------------------------- | ------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------- |
| `api_key`                        | `SOCPRIME_API_KEY`                          | `ChangeMe`                   | The SOC Prime CCM API Key                                                                               |
| `content_list_name`              | `SOCPRIME_CONTENT_LIST_NAME`                |                  | List of comma-separated content list names at the SOC Prime Platform from which rules will be downloaded. At least one of `content_list_name` and `job_ids` parameters has to be provided. If `content_list_name` is provided, then the parameter `indicator_siem_type` has to be provided too.                   |
| `indicator_siem_type`              | `SOCPRIME_INDICATOR_SIEM_TYPE`                | `sigma`                   | Security platform formats in which rules will be downloaded. This parameter is applicable only to `content_list_name` parameter and not to `job_ids`. Optional. The default value is `sigma`.                     |
| `job_ids`                   | `SOCPRIME_JOB_IDS`                     |                       | List of comma-separated job IDs at the SOC Prime Platform from which rules will be downloaded. At least one of `content_list_name` and `job_ids` parameters has to be provided.                                                                          |
| `interval_sec`                   | `SOCPRIME_INTERVAL_SEC`                     | `3600`                       | The import interval in seconds                                                                          |
| `siem_type`                      | `SOCPRIME_SIEM_TYPE`                        |                              | (Optional) Security platform formats for which external links will be generated. In case of using `config.yml`, it should be a list; and in case of Docker env var, it should be a string with comma-separated values. See possible values below. |

The list of possible values for the `siem_type` or `indicator_siem_type` (`SOCPRIME_SIEM_TYPE` or `SOCPRIME_INDICATOR_SIEM_TYPE`) variables:
* `ala-rule` — Microsoft Sentinel Rule
* `ala` — Microsoft Sentinel Query
* `elasticsearch` — Elasticsearch Query (Lucene)
* `es-eql` — Elasticsearch Query (EQL)
* `xpack-watcher` — Elasticsearch Watcher
* `elasticsearch-rule` — Elasticsearch Detection Rule (Lucene)
* `es-rule-eql` — Elasticsearch Detection Rule (EQL)
* `kibana` — Kibana Saved Search
* `elastalert` — Elasticsearch ElastAlert
* `qradar` — Qradar Query
* `humio` — Falcon LogScale Query
* `humio-alert` — Falcon LogScale Alert
* `splunk` — Splunk Query
* `splunk_alert` — Splunk Alert
* `sumologic` — Sumo Logic Query
* `sumologic-cse` — Sumo Logic CSE Query
* `sumologic-cse-rule` — Sumo Logic CSE Rule
* `arcsight-esm` — ArcSight Rule
* `arcsight-keyword` — ArcSight Query
* `logpoint` — LogPoint Query
* `grep` — Regex Grep Query
* `powershell` — PowerShell Query
* `graylog` — Graylog Query
* `kafka` — Apache Kafka KSQL Query
* `rsa_netwitness` — RSA NetWitness Query
* `carbonblack` — VMware Carbon Black Cloud Query
* `carbonblack-edr` — VMware Carbon Black EDR Query
* `open-ioc` — FireEye OpenIOC
* `fireeye-helix` — FireEye Helix Query
* `chronicle` — Chronicle Security Rule
* `securonix` — Securonix Query
* `s1-events` — SentinelOne Events Query
* `s1-process` — SentinelOne Process State Query
* `mdatp` — Microsoft Defender for Endpoint Query
* `qualys` — Qualys IOC Query
* `sysmon` — Sysmon Rule
* `crowdstrike` — CrowdStrike Endpoint Security Query
* `limacharlie` — LimaCharlie Rule
* `devo` — Devo Query
* `snowflake` — Snowflake Query
* `athena` — Amazon Athena Query
* `opendistro-query` — Amazon OpenSearch Query
* `opendistro-rule` — Amazon OpenSearch Rule
* `fortisiem` — FortiSIEM rule
* `axon-ads-query` — LogRhythm Axon Query
* `axon-ads-rule` — LogRhythm Axon Rule
