# Technology Add-On for Microsoft Applocker

Forked from [secops4thewin/TA-Applocker](https://github.com/secops4thewin/TA-Applocker) with following improvements:

- Use [`WinEventLog`](https://docs.splunk.com/Documentation/Splunk/latest/Admin/Inputsconf#Windows_Event_Log_Monitor) stanza in [inputs.conf](./default/inputs.conf) (`XmlWinEventLog` stanza hasn't been functional for a while)
- Set proper source and sourcetype so that [Splunk_TA_windows](https://splunkbase.splunk.com/app/742) can help with some field extractions.
- Fix field extractions in [props.conf](./default/props.conf) & [transforms.conf](./default/transforms.conf)
- Add `EventDescription` field in [auto-lookup](./lookups/applockerevent.csv) and alias it to `signature` for CIM.

## Prerequisite

[Splunk_TA_windows](https://splunkbase.splunk.com/app/742)
