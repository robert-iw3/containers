#### Valid Enterprise Environment Variables
|Environment Variable Name| Description | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|
| SPLUNK_BUILD_URL | URL to Splunk build where we can fetch a Splunk build to install | no | no | no |
| SPLUNK_DEFAULTS_URL | Defaults.yml URL | no | no | no |
| SPLUNK_UPGRADE | If this is True, we won’t run any provisioning after installation. Use this to upgrade and redeploy containers with a newer version of Splunk. | no | no | no |
| SPLUNK_ROLE | Specify the container’s current Splunk Enterprise role. Supported Roles: splunk_standalone, splunk_indexer, splunk_deployer, splunk_search_head, etc. | no | yes | yes |
| DEBUG | Print Ansible vars to stdout (supports Docker logging) | no | no | no |
| SPLUNK_START_ARGS | Accept the license with “—accept-license”. Please note, we will not start a container without the existence of --accept-license in this variable. | yes | yes | yes |
| SPLUNK_LICENSE_URI | URI we can fetch a Splunk Enterprise license. This can be a local path or a remote URL. | no | no | no |
| SPLUNK_STANDALONE_URL | List of all Splunk Enterprise standalone hosts (network alias) separated by comma | no | no | no |
| SPLUNK_SEARCH_HEAD_URL | List of all Splunk Enterprise search head hosts (network alias) separated by comma | no | yes | yes |
| SPLUNK_INDEXER_URL| List of all Splunk Enterprise indexer hosts (network alias) separated by comma | no | yes | yes |
| SPLUNK_HEAVY_FORWARDER_URL | List of all Splunk Enterprise heavy forwarder hosts (network alias) separated by comma | no |  no | no |
| SPLUNK_DEPLOYER_URL | One Splunk Enterprise deployer host (network alias) | no | yes | no |
| SPLUNK_CLUSTER_MASTER_URL | One Splunk Enterprise cluster master host (network alias) | no | no | yes |
| SPLUNK_SEARCH_HEAD_CAPTAIN_URL | One Splunk Enterprise search head host (network alias). Passing this ENV variable will enable search head clustering. | no | yes | no |
| SPLUNK_PASSWORD | Default password of the admin user| yes  | yes | yes |
| SPLUNK_HEC_TOKEN | HEC (HTTP Event Collector) Token when enabled | no | no | no |
| SPLUNK_SHC_SECRET | Search Head Clustering Shared secret | no | yes | no |
| SPLUNK_IDXC_SECRET | Indexer Clustering Shared Secret | no | no | yes |
| NO_HEALTHCHECK | Disable the Splunk healthcheck script | no | no | yes |

#### Valid Universal Forwarder Environment Variables
|Environment Variable Name| Description | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|
| SPLUNK_DEPLOYMENT_SERVER | One Splunk host (network alias) that we use as a deployment server. (http://docs.Splunk.com/Documentation/Splunk/latest/Updating/Configuredeploymentclients) | no | no | no |
| SPLUNK_ADD | List of items to add to monitoring separated by comma. Example, SPLUNK_ADD=udp 1514,monitor /var/log/*. This will monitor udp 1514 port and /var/log/* files. | no | no | no |
| SPLUNK_BEFORE_START_CMD | List of commands to run before Splunk starts separated by comma. Ansible will run “{{splunk.exec}} {{item}}”. | no | no | no |
| SPLUNK_CMD | List of commands to run after Splunk starts separated by comma. Ansible will run “{{splunk.exec}} {{item}}”. | no | no | no |
| DOCKER_MONITORING | True or False. This will install Docker monitoring apps. | no | no | no |

#### default.yml valid options
`defaults.yml` exposes several additional options for configuring Splunk, and may be set by either mounting a volume to `/tmp/defaults` or by setting the
`SPLUNK_DEFAULTS_URL` environment token. A sample `default.yml` file can be found in the [test_scenarios/defaults](path_to_uri_once_published) portion of the open-source project.

Root items influence the behavior of everything in the container; they have global scope inside the container.
Example:
```
    ---
    retry_num: 100
```

|Variable Name| Description | Parent Object | Default Value | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|:---:|:---:|
| retry_num | Default number of loop attempts to connect containers | none | 100 | yes | yes | yes |

The major object "splunk" in the YAML file will contain variables that influence how Splunk operates. Example:
```
    Splunk:
        opt: /opt
        home: /opt/splunk
        user: splunk
        group: splunk
        exec: /opt/splunk/bin/splunk
        pid: /opt/splunk/var/run/splunk/splunkd.pid
        password: "{{ splunk_password | default(<password>) }}"
        svc_port: 8089
        s2s_port: 9997
        http_port: 8000
        hec_port: 8088
        hec_disabled: 0
        hec_enableSSL: 1
        #The hec_token here is used for INGESTION only. By that I mean receiving Splunk events.
        #Setting up your environment to forward events out of the cluster is another matter entirely
        hec_token: <default_hec_token>
```

|Variable Name| Description | Parent Object | Default Value | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|:---:|:---:|
|opt| Parent directory where Splunk is running | splunk | /opt | yes | yes | yes |
|home| Location of the Splunk Installation | splunk | /opt/splunk | yes | yes | yes |
|user| Operating System User to Run Splunk Enterprise As | splunk | splunk | yes | yes | yes |
|group| Operating System Group to Run Splunk Enterprise As | splunk | splunk | yes | yes | yes |
|exec| Path to the Splunk Binary | splunk | /opt/splunk/bin/splunk | yes | yes | yes |
|pid| Location to the Running PID File | splunk | /opt/splunk/var/run/splunk/splunkd.pid | yes | yes | yes
|password| Password for the admin account | splunk | **none** | yes | yes | yes |
|svc_port| Default Admin Port | splunk | 8089 | yes | yes | yes |
|s2s_port| Default Forwarding Port | splunk | 9997 | yes | yes | yes |
|http_port| Default SplunkWeb Port | splunk | 8000 | yes | yes | yes |
|hec_port| Default HEC Input Port | splunk | 8088 | no | no | no |
|hec_disabled| Enable / Disable HEC | splunk | 0 | no | no | no |
|hec_enableSSL| Force HEC to use encryption | splunk | 1 | no | no | no |
|hec_token| Token to enable for HEC inputs | splunk | **none** | no | no | no |

The app_paths section is located as part of the "splunk" parent object. The settings located in this section will directly influence how apps are installed inside the container. Example:
```
        app_paths:
            default: /opt/splunk/etc/apps
            shc: /opt/splunk/etc/shcluster/apps
            idxc: /opt/splunk/etc/master-apps
            httpinput: /opt/splunk/etc/apps/Splunk_httpinput
```

|Variable Name| Description | Parent Object | Default Value | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|:---:|:---:|
|default| Normal apps for standalone instances will be installed in this location | splunk.app_paths | **none** | no | no | no |
|shc| Apps for search head cluster instances will be installed in this location (usually only done on the deployer)| splunk.app_paths | **none** | no | no | no |
|idxc| Apps for index cluster instances will be installed in this location (usually only done on the cluster master)| splunk.app_paths | **none** | no | no | no |
|httpinput| App to use and configure when setting up HEC based instances.| splunk.app_paths | **none** | no | no | no |

Search Head Clustering can be configured using the "shc" sub-object. Example:
```
        # Search Head Clustering
        shc:
            enable: false
            secret: <secret_key>
            replication_factor: 3
            replication_port: 4001
```
|Variable Name| Description | Parent Object | Default Value | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|:---:|:---:|
|enable| Instructs the container to create a search head cluster | splunk.shc | false| no | yes | no |
|secret| A secret phrase to use for all SHC communication and binding. Please note, once set this can not be changed without rebuilding the cluster. | splunk.shc | **none** | no | yes | no |
|replication_factor| Consult docs.splunk.com for valid settings for your use case | splunk.shc | 3 | no | yes | no |
|replication_port| Default port for the SHC to communicate on | splunk.shc | 4001| no | yes | no |

Lastly, Index Clustering is configured with the `idxc` sub-object. Example:
```
        # Indexer Clustering
        idxc:
            secret: <secret_key>
            search_factor: 2
            replication_factor: 3
            replication_port: 9887
```
|Variable Name| Description | Parent Object | Default Value | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|:---:|:---:|
| secret | Secret used for transmission between the cluster master and indexers | splunk.idxc | **none** | no | no | yes |
| search_factor | Search factor to be used for search artifacts | splunk.idxc | 2 | no | no | yes |
| replication_factor | Bucket replication factor used between index peers | splunk.idxc | 3 | no | no | yes |
| replication_port | Bucket replication Port between index peers | splunk.idxc | 9887 | no | no | yes |


---

