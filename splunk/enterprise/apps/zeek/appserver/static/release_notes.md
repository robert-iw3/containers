
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
