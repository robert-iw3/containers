# Patches for [Splunk_TA_esxilogs](https://splunkbase.splunk.com/app/5603)

## Additional fields extraction

Field extraction/transformation on UDP syslog.

TCP Syslog:

```
<505>2023-01-02T12:34:56.789Z esxihostname Hostd: info hostd[A1B2C3] [Originator@6789 sub=VsanSimsStubImpl opID=f9e8d7c6] Calling vim.host.VsanSystemEx.GetVsanRuntimeInfo
```

UDP Syslog:

```
Jan 2 13:34:56 10.100.101.102 2023-01-02T12:34:56.789Z esxihostname Hostd: info hostd[A1B2C3] [Originator@6789 sub=VsanSimsStubImpl opID=f9e8d7c6] Calling vim.host.VsanSystemEx.GetVsanRuntimeInfo
```

"Jan 2 13:34:56" is in local time, whereas "2023-01-02T12:34:56.789Z" is in UTC.

## Build

```
build.py [--input] /path/to/splunk-add-on-for-vmware-esxi-logs_*.tgz [--cloud]
```

Options:

- **input**: Path to Splunk app. (default: "splunk-add-on-for-vmware-esxi-logs\_\*.tgz" in the current directory)
- **cloud**: Create Splunk Cloud-compatible app.

Outputs:

- Splunk_TA_esxilogs\_\*.tgz
- custom-Splunk_TA_esxilogs\_\*.tgz (if `--cloud` is specified)
