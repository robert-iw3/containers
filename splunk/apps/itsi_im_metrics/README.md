# Guide to use [itsi_im_metrics](https://splunkbase.splunk.com/app/1841) index

This folder contains a collection of configurations needed to collect performance metrics (CPU, RAM, disk, network bandwidth) and consume those metrics. Note the [index names](./indexes.conf) given here are not mandatory, they can be renamed to anything else. If you prefer to use other names, remember to update all occurrences of windows-metrics and linux-metrics. Windows and Linux metrics can share the same index.

## Collect metrics

- Create [metrics indexes](./indexes.conf): windows-metrics and linux-metrics. [Additional configuration](https://docs.splunk.com/Documentation/ITSI/latest/Entity/CustomIndexes) is required to use ITSI default dashboards.
- Windows: Append content of [windows-inputs.conf](./windows-inputs.conf) to $SPLUNK_HOME/etc/apps/[Splunk_TA_windows](https://splunkbase.splunk.com/app/742)/local/inputs.conf
- Linux: Append content of [linux-inputs.conf](./linux-inputs.conf) to $SPLUNK_HOME/etc/apps/[Splunk_TA_nix](https://splunkbase.splunk.com/app/833)/local/inputs.conf

## Dashboards

- [windows_chart.xml](./windows_chart.xml)
- [windows_table.xml](./windows_table.xml)
- [linux_chart.xml](./linux_chart.xml)
- [linux_table.xml](./linux_table.xml)
- [splunk_usage.xml](./splunk_usage.xml). _Requires [custom](./internal_server.json) data model._

## Alert

- [Disk Monitor](./savedsearches.conf)

## Prerequisite

[ITSI](https://splunkbase.splunk.com/app/1841) addon should be installed in the indexer, either heavy forwarder or Splunk Cloud (if universal forwarder forwards directly). Even if you don't use its bundled dashboards, the addon is required to process the data before it can be saved into [metrics index](https://docs.splunk.com/Documentation/SplunkCloud/latest/Metrics/Overview).
