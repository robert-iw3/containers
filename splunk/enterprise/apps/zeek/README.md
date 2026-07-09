# Corelight Add-on for Zeek Documentation

The TA for Zeek allows a Splunk Enterprise administrator to parse open source Zeek data in JSON or TSV format, and map it into the Common Information Model for use by multiple Splunk security apps.

## About Corelight Add-on for Zeek

|                            |                   |
|----------------------------|-------------------|
| Author                     | Aplura, LLC       |
| App Version                | 1.0.10             |
| App Build                  | 18                |
| Creates an index           | False             |
| Implements summarization   | No                |
| Summary Indexing           | False             |
| Data Model Acceleration    | None              |
| Report Acceleration        | None              |
| Splunk Enterprise versions | 9.x, 8.x          |
| Platforms                  | Splunk Enterprise |

## Scripts and binaries

This App provides the following scripts:

- None

## Overview

## Lookups

Corelight Add-on for Zeek contains the following lookup files.

- bro_conn_state.csv

- bro_note_alert_type.csv

- bro_protocols.csv

- bro_status_action.csv

- bro_tc_flag.csv

- bro_vendor_info.csv

## Event Generator

Corelight Add-on for Zeek does not include an event generator.

## Acceleration

- Summary Indexing: No

- Data Model Acceleration: No

- Report Acceleration: No

## binary file declaration

- None


# Release Notes

## Version 1.0.10

- Updated the `bro` and `source::...bro.*.log` props stanzas to remove `FIELD_QUOTE` setting.

## Version 1.0.9

- POTENTIAL BREAKING Change

  - Due to enforcement of Splunk AppInspect `check check_props_conf_has_no_prohibited_characters_in_sourcetypes`, the "wildcard" properties in props.conf has been REMOVED.

  - The settings are included below for reference if needed.

  - NOTE: This will not be available in Splunk Cloud.

        [(?::){0}bro:*:json]
        TRUNCATE                = 0
        SHOULD_LINEMERGE        = false
        TIME_FORMAT             = %s.%6N
        MAX_TIMESTAMP_LOOKAHEAD = 20
        KV_MODE                 = JSON
        FIELDALIAS-dest0        = id.resp_h AS dest
        FIELDALIAS-dest_ip0     = id.resp_h AS dest_ip
        FIELDALIAS-src0         = id.orig_h AS src
        FIELDALIAS-src_ip0      = id.orig_h AS src_ip
        FIELDALIAS-src_port0    = id.orig_p AS src_port
        EVENT_BREAKER_ENABLE    = true

        [(?::){0}bro(_|:)*]
        TRUNCATE                      = 0
        SHOULD_LINEMERGE              = false
        TIME_FORMAT                   = %s.%6N
        MAX_TIMESTAMP_LOOKAHEAD       = 20
        REPORT-get_bytes_for_bro_conn = bytes_in_int, bytes_out_int
        LOOKUP-LookupTCFlag           = LookupTCFlag TC OUTPUT flag
        LOOKUP-VendorInfo             = bro_vendor_info_lookup sourcetype OUTPUT vendor,product,product as vendor_product
        LOOKUP-NoticeType             = bro_note_alert_type note OUTPUT type
        FIELDALIAS-dest_ip            = id_resp_h AS dest_ip
        FIELDALIAS-mailfrom           = mailfrom AS src_user
        FIELDALIAS-proxied            = proxied AS product
        FIELDALIAS-src                = id_orig_h AS src
        FIELDALIAS-src_ip             = id_orig_h AS src_ip
        FIELDALIAS-src_port           = id_orig_p AS src_port
        FIELDALIAS-uid                = uid AS flow_id
        FIELDALIAS-src_mac            = mac AS src_mac
        EVAL-sensor_name              = coalesce(system_name, host, "unknown")
        EVAL-is_broadcast             = if(src in("0.0.0.0", "255.255.255.255") OR dest in("255.255.255.255", "0.0.0.0"),"true","false")
        EVAL-direction                = case(local_orig="true" AND local_resp="true", "internal", local_orig="true" and local_resp="false", "outbound", local_orig="false" and local_resp="false", "external", local_orig="false" and local_resp="true", "inbound", 1=1, "unknown")
        EVAL-is_src_internal_ip       = if(cidrmatch("10.0.0.0/8",src) OR cidrmatch("172.16.0.0/12",src) OR cidrmatch("192.168.0.0/16", src), "true", "false")
        EVAL-is_dest_internal_ip      = if(cidrmatch("10.0.0.0/8",dest) OR cidrmatch("172.16.0.0/12",dest) OR cidrmatch("192.168.0.0/16", dest), "true", "false")
        EVAL-id_resp_h                = dest
        EVAL-id_resp_p                = dest_port
        EVAL-id_orig_h                = src
        EVAL-id_orig_p                = src_port
        EVAL-bytes                    = if(isnum(bytes),bytes,bytes_in+bytes_out)
        EVAL-packets                  = if(isnum(packets),packets,packets_in+packets_out)
        EVAL-duration                 = if(isnum(duration),duration,null())
        EVAL-dest_port                = coalesce('id.resp_p',id_resp_p)
        EVAL-dvc                      = coalesce(extracted_host, host, hostname)
        EVAL-dest_host                = coalesce(extracted_host, host, hostname)
        EVAL-vendor_action            = split(actions, ",")
        EVENT_BREAKER_ENABLE          = true

## Version 1.0.8

- Bug

  - \[DESK-1539\] - Updated `props.conf` for `zeek:files` to remove an incorrect evaluator (`!==`) from an eval statement.

## Version 1.0.7

- Bug

  - \[DESK-1537\] - Updated `props.conf` for `zeek:ssl` to include the proper lookup definition.

## Version 1.0.6

- CIM Updates for v5.2

# Installation, Prerequisites, and Configuration

Because this App runs on Splunk Enterprise, all the [Splunk Enterprise system requirements](https://docs.splunk.com/Documentation/Splunk/latest/Installation/Systemrequirements) apply.

## Download

Download Corelight Add-on for Zeek on [Splunkbase](https://splunkbase.splunk.com/app/5446).

### Deploy to single server instance

Follow these steps to install the app in a single server instance of Splunk Enterprise:

- Deploy as you would any App, and restart Splunk.

- Configure.

### Deploy to Splunk Cloud

- Install via the Apps Browser in Splunk Cloud.

- If there are issues, or you need help, have your Splunk Cloud Support handle this installation.

### Deploy to a Distributed Environment

- For each Search Head in the environment, deploy a copy of the App.

## Permissions Update

<div class="note">

By default, the TA is **not** exported to the system. This is a best practice to give the Splunk Administrator a chance to review configurations prior to exporting system wide.

</div>

- [Splunk Cloud ACS](https://docs.splunk.com/Documentation/SplunkCloud/9.3.2411/Config/ManageAppPermissions)

- [Splunk Enterprise/Cloud Web](https://docs.splunk.com/Documentation/Splunk/9.4.1/Admin/Managingappconfigurationsandproperties)

# Troubleshooting and Support

## Questions and answers

Access questions and answers specific to Corelight Add-on for Zeek at <https://answers.splunk.com>. Be sure to tag your question with the App.

## Support

- Support Email: <appsupport@corelight.com>

- Support Website: <https://www.corelight.com/support>

- Support Offered: Email, Web

## Known Issues

Version 1.0.10 of Corelight Add-on for Zeek has the following known issues:

- None
