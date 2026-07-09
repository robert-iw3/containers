## Introduction

If you want to look into the health of your Cribl environments, you are usually pretty set with the default Monitoring functionality that Cribl offers out of the box.

But Cribl also lets you send Internal Metrics/Logs to external monitoring tools, so you can take advantage of the advanced searching, visualization and alerting capabilities of Elasticsearch.

## How It Works

We prepare Elasticsearch before sending the data with the appropriate mappings.

Metrics are saved in [Time Series Data Stream (TSDS)](https://www.elastic.co/guide/en/elasticsearch/reference/current/tsds.html).

Logs are saved in [Data Streams](https://www.elastic.co/guide/en/elasticsearch/reference/current/data-streams.html).

We connect [the Cribl Internal Metrics and Logs sources](https://docs.cribl.io/stream/sources-cribl-internal/#configuring-cribl-internal-logsmetrics-as-a-datasource) to an [Elasticsearch destination](https://docs.cribl.io/stream/destinations-elastic/) using QuickConnect.

We select a custom pipeline as a pre-processing pipeline for logs before sending to Elasticsearch.

We have created some dashboards and alerts for you, from the perspective of a Cribl Support Engineer that we can import into Kibana.

## Prerequisites

- Cribl Stream or Edge Version 3.3+
- Elasticsearch and Kibana Version 8.8+

## Getting started

We provide 2 options to set you up quickly.

Option 1: You can prepare Elasticsearch and Cribl automatically using a `bootstrap.sh` script. This is ideal for larger environments, to prevent having to configure many worker groups at the same time.

Option 2: You can quickly configure Elasticsearch and Cribl manually as well.

For both options you will then have to manually commit and deploy Cribl's changes and import the Dashboards into Kibana.

You can then also choose to collect logs from the Leader separately as an optional step.

## Option 1 - Bootstrap Script

<details><summary>This script will run the manual steps for every Stream Worker Group or Edge Fleet, which could save some time.</summary>

Prerequisites for the script are: `Bash, jq, curl`

Files to run the script are in [the Github repository](https://github.com/criblio/elastic-cribl-monitoring).

| :information_source: The following variables will need to be updated in the `.env` file: |
|----------------------------------------------|

| Variable(s)  | Description |
| ------------- | ------------- |
|`ES_ELASTIC_URL` | The endpoint to your Elasticsearch deployment (e.g. `https://elasticsearch.domain.com:9200`) |
|`ES_KIBANA_URL` | The endpoint to your Kibana instance (e.g. `https://kibana.domain.com:5601`) |
|`ES_CRIBL_URL` | The endpoint to your Cribl Leader node or your Cribl.Cloud URL .  (e.g. `https://cribl.domain.com:9000` or `https://main-happy-margulis-topxery.cribl.cloud`) |
|`CRIBL_USER`, `CRIBL_PASSWORD` | **On-Premise specific options.** Your typical Username and Password combination for Authenticating through the Cribl UI. |
| `CRIBL_CLIENT_ID` , `CRIBL_CLIENT_SECRET` | **Cribl.Cloud specific options.** The Client ID and secret created by [following instructions here](https://docs.cribl.io/stream/api-tutorials/#criblcloud-free-tier). |
| `ES_ELASTIC_USER`, `ES_ELASTIC_PASSWORD` | Elasticsearch username and password to authenticate Elasticsearch API calls with. |
| `ES_ELASTIC_BEARER_TOKEN` | (optional) If you want to use [token-based authentication service](https://www.elastic.co/guide/en/elasticsearch/reference/current/token-authentication-services.html) to authenticate Elasticsearch API calls (limited to service-accounts and token-service) |
| `ES_ELASTIC_PASSWORD` | The password for your Cribl Writer user |
| `ES_CRIBL_WORKERGROUP_NAME` | The Stream groups or Edge Fleet names for which to apply the bootstrap script to (e.g. `("default" "defaultHybrid")` for multiple or `("defaultHybrid")` for a single group/fleet) |
| `ES_CRIBL_CUSTOM_IDENTIFIER` | (optional) Any value for a custom identifier that you want to add, such as a data centre name. Will be added as a field to the events. |
| `ES_CRIBL_ELASTIC_OUTPUT_ID` (optional) | The ID of the Elasticsearch output that will be created/updated. This id will be the same across all your worker groups. |

| :information_source: The bootstrap script has some debugging options which can be enabled by uncommenting lines at the top of the file. This will create a log file with very verbose information in the same working directory as the script. |
|----------------------------------------------|

#### Run the bootstrap script:

1. Make `bootstrap.sh` executable (`chmod +x bootstrap.sh`)
2. Run: `./bootstrap.sh`
3. Commit and deploy from Cribl to make sure the changes take effect
4. Continue to the Importing Saved Objects section.

| Common issues while running the script: |
|----------------------------------------------|
| - Be sure to commit and deploy, for the changes in Stream to take effect! |
| - If the `ES_*_URL` endpoints require a TLS connection while the Certificate Authorities certificates are not in your local trust stores, you will have to adjust the curl commands to use the `-k` flag |

</details>

## Option 2 - Manual Configuration

<details><summary>Here are the manual steps to configure Elasticsearch first and then Cribl Stream. The instructions here are for Stream, but will work for Edge fleets too.</summary>

#### 1. Elasticsearch Configuration

Please copy & paste and then execute the appropriate commands into your [Developer Console](https://www.elastic.co/guide/en/kibana/current/console-kibana.html) one by one in the order that they are displayed:

| :information_source: Please update the password for the user and/or the permissions of the corresponding user role. |
|----------------------------------------------|

<details><summary>1. Roles</summary>

```
PUT _security/role/cribl_writer
{
  "cluster": ["manage_index_templates", "monitor", "manage_ilm"],
  "indices": [
    {
      "names": [ "metrics-cribl-internal", "logs-cribl-internal" ],
      "privileges": ["write","create","create_index","manage","manage_ilm"]
    }
  ]
}
```

</details>

<details><summary>2. Users</summary>

```
PUT _security/user/cribl_internal
{
  "password" : "cribl-test-password",
  "roles" : [ "cribl_writer"],
  "full_name" : "Internal Cribl User"
}
```

</details>

<details><summary>3. Component Templates</summary>

**Metrics:**

Endpoint:
`PUT _component_template/metrics-cribl-internal`

Payload:
https://github.com/criblio/elastic-cribl-monitoring/blob/b6f4ead8bdd3045a94159e86ed0f80098199b802/ecm_metrics_component_template.json#L1-L88

**Logs:**

Endpoint:
`PUT _component_template/logs-cribl-internal`

Payload:
https://github.com/criblio/elastic-cribl-monitoring/blob/b6f4ead8bdd3045a94159e86ed0f80098199b802/ecm_logs_component_template.json#L1-L4054

</details>

<details><summary>4. Index Templates</summary>

**Metrics:**

```
PUT _index_template/metrics-cribl-internal
{
  "priority": 500,
  "index_patterns": [
    "metrics-cribl-internal"
  ],
  "composed_of": [
    "metrics-cribl-internal"
  ],
  "data_stream": { },
  "template": {
    "settings": {
      "index.mode": "time_series",
      "index.routing_path": ["host.name", "cribl_wp", "_metric"]
    }
  }
}
```

**Logs:**

```
PUT _index_template/logs-cribl-internal
{
  "index_patterns": [
    "logs-cribl-internal"
  ],
  "composed_of": [
    "logs-cribl-internal"
  ],
  "priority": 101,
  "data_stream": {}
}
```

</details>

#### 2. Cribl Stream Configuration

Repeat the following instructions for every Worker Group in your distributed environment:

1. Import the pipeline to remove mapping conflicts:
  - Create a new pipeline with the name `cribl-internal_rm_conflicts` and wait to save it
  - Open the Advanced JSON editor.
  - Copy and paste the following JSON and then save the pipeline:

<details><summary>Pipeline cribl-internal_rm_conflicts</summary>

https://github.com/criblio/elastic-cribl-monitoring/blob/b6f4ead8bdd3045a94159e86ed0f80098199b802/ecm_pipeline_config.json#L1-L656
</details>

2. Create a new [Elasticsearch Destination](https://docs.cribl.io/stream/destinations-elastic/#configuring-product-to-output-to-elasticsearch) named `cribl_elasticsearch`:
  - Set the appropriate Bulk API URL or Cloud ID
  - Set the appropriate authentication settings
  - Set the DataStream to ``metrics-cribl-internal``
  - Configure backpressure behaviour to be persistent queueing
  - Ensure the `Include document _id` advanced setting is disabled

3. Configure the [Cribl Internal Metrics](https://docs.cribl.io/stream/sources-cribl-internal/#configuring) Source and from the source configuration page:
  - Navigate to **Processing Settings > Fields**
    - Set an `__index` field with value ``metrics-cribl-internal``
    - (Optional) Add a `custom_id` field with a custom value, for example a data centre name
  - Navigate to **Connected Destinations**
    - Set the *Pipeline/Pack* to `cribl_metrics_rollup`
    - Set the *Destination* to `elastic:cribl_elasticsearch`
  - Enable the source

4. Configure the [Cribl Internal Logs](https://docs.cribl.io/stream/internal-logs/) Source and from the source configuration page:
  - Navigate to **Processing Settings > Fields**
    - Set an `__index` field with value ``logs-cribl-internal``
    - (Optional) Add a `custom_id` field with a custom value, for example a data centre name
  - Navigate to **Connected Destinations**
    - Set the *Pipeline/Pack* to `cribl-internal_rm_conflicts`
    - Set the *Destination* to `elastic:cribl_elasticsearch`
  - Enable the source

5. Commit & deploy if your Stream is in a distributed environment

</details>

## Importing Saved Objects

Dashboards as well as Rules can be imported by uploading [the `ecm_saved_objects.ndjson` file](https://github.com/criblio/elastic-cribl-monitoring/blob/main/ecm_saved_objects.ndjson) to Kibana.

They can be imported through the [Managed Saved Objects Interface](https://www.elastic.co/guide/en/kibana/current/managing-saved-objects.html#_import).

Note that the setting [`xpack.encryptedSavedObjects.encryptionKey`](https://www.elastic.co/guide/en/kibana/current/xpack-security-secure-saved-objects.html) may need to be set.

## Optional Configuration

#### Leader logs:

Leader logs are currently NOT sent via the Internal Logs source, so for the leader dashboard to work, additional steps need to be performed so leader logs are forwarded to the Elasticsearch destination as well:

1. Install a *Cribl Edge* node on your *Leader* node and configure local log collection via a File Monitor source. An easy way to do this would be by using [the bootstrap method described here](https://docs.cribl.io/stream/deploy-workers/#add-bootstrap).

| :information_source: When deploying the edge node to your leader node, we recommend having a separate fleet just for this node. Be sure to disable all other inputs on that edge node except for file monitor inputs. |
|----------------------------------------------|

2. Configure the File Monitor source to collect logs by setting the Filename Allowlist modal to `/opt/cribl/log/*.log`
3. Then you’ll also need to import the `cribl-internal_rm_conflicts` pipeline from step 2.1 above into the edge environment.
4. And configure the File Monitor Source like the Cribl Internal Logs source in step 2.4.

## Additional Considerations

#### Mappings:

The existing field mapping for logs is set to static and this has been deliberately the chosen for the following reasons:

- prevent excessive mapping conflicts and explosions
- to keep in line with shard sizing across versions
- to have a solid set of known fields as a starting point to choose from

The mappings specified in the component templates may need further adjustments going forward. This is because the list of existing fields will continue to grow as more features are either enabled or added.

#### General:

1. Due to the static mapping on the logs data streams, the size of the created Logs indices can grow quickly.
    - Consider adjusting the index templates and add an Index Lifecycle Management (ILM) policy with a rollover action
2. Some mapping conflicts could still arise for specific unaccounted for logs
    - The index mapping or pre-processing pipeline attached to the Elasticsearch destination may have to be continuously updated
3. If some interesting fields cannot be searched or aggregated
    - You can add the field to the component template in the index template. You may have to reindex the existing index and/or do a rollover to have new data come in with the updated mapping.

4. The metrics index uses TSDS under the hood, so you can use Elasticsearch’s [Downsample](https://www.elastic.co/guide/en/elasticsearch/reference/current/downsampling.html) ILM action, to reduce storage over time as metrics become less relevant.

#### Available Dashboards

| Name | Description |
| ------------- | ------------- |
| Cribl Logs - Home  | Starting point for troubleshooting issues in a Cribl environment  |
| Cribl Logs - Stats | Minutely Stats created from Internal Logs |
| Cribl Logs - Stats by Worker Process | Minutely Stats created from Internal Logs but split by Worker Process |
| Cribl Leader - Overview | Overview of important leader related Statistics and metrics created from the logs of the leader node |
| Cribl Metrics - Overview | Dashboard based on general metrics on a host level |
| Cribl Metrics - Worker Processes | The overview of workers broken down by worker process |
| Cribl Metrics - Source & Destination | The overview of incoming and outgoing data broken down by source and destination |

#### Available Rules

| Name | Description |
| ------------- | ------------- |
| Thruput Threshold | 200GB Total Thruput per worker process per day exceeded |
| Memory Threshold | 2GB Memory Usage per worker process exceeded in the last 5 minutes |
| CPU Threshold | CPU Utilization by Worker Process averages above 95% in the last 5 minutes |
| PQ Threshold | Persistent Queue size is engaged or exceeded threshold in the last 5 minutes |
| Source Unhealthy | Destination has been marked as unhealthy in the last 5 minutes |
| Destination Unhealthy | Destination has been marked as unhealthy in the last 5 minutes |

## Searching Leader Logs

You can use the Discover App to find leader logs. The included pipeline splits the logs by `sourcetype` field, allowing you to quickly search for a specific type of log:

| `sourcetype` value  | Description |
| ------------- | ------------- |
| cribl:access    | API calls |
| cribl:audit     | Actions pertaining to files |
| cribl:log       | Principal logs |
| cribl:notifications | Messages that appear in the notification list |
| cribl:stderr    | Garbage collections and OOM killers |
| cribl:ui-access | Interactions with different UI components |

## Navigating the available Dashboards

Start by applying the available controls. Every Dashboard can have its own set of Controls. Controls are filters to help narrow down the searches that are sent to the Elasticsearch infrastructure. These are filters to help let you set context on the dashboards. That context can then be carried over to the other dashboards as well by pinning filters.

#### Controls

| :information_source: Narrowing down the time range can help prevent infrastructure overhead. |
|----------------------------------------------|

- The available values in the controls depend on the data which has been found in the time range.
- Every dashboard will have different controls based on the underlying searched data
- You can easily switch dashboards while keeping context with pinned filters

#### Drilldowns

Most dashboards included here contain drill downs, allowing you to go into more details.

For example:

Visualizations on the `Cribl Metrics - Overview` dashboard, allows you to drilldown into the `Cribl Metrics - Worker Processes` dashboard after observing that one of the workers shows signs of high CPU utilization.

### About

These dashboards should help you get started to monitor Cribl Products with Elastic. Feel free to contribute and shoot us a pull request. If you notice any issues, feel free to create an issue in this repository.

You’re welcome to share feedback and ideas [in our community slack channel](https://cribl-community.slack.com/archives/C06AE510KC1). Are you not a member of our Slack Community? Head over to https://cribl-community.slack.com/


