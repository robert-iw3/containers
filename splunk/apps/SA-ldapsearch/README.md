# Patches for [SA-ldapsearch](https://splunkbase.splunk.com/app/1151)

## msDS-User-Account-Control-Computed

Parse flags (e.g.`LOCKOUT` and `PASSWORD_EXPIRED`) in the [msDS-User-Account-Control-Computed](https://learn.microsoft.com/en-gb/windows/win32/adschema/a-msds-user-account-control-computed) attribute. ([link](https://mdleom.com/blog/2023/10/01/splunk-ldapsearch-useraccountcontrol/))

`$ python build.py -i /path/to/splunk-supporting-add-on-for-active-directory_*.tgz`
