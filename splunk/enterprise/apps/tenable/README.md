# ABOUT THIS APP

* The Technology Add-on for Tenable is used to download data from TVM, do parsing and indexing on it. It also collects the data from TOT.
* Along with TVM and TOT, it is used to collect and index data from TSC and to parse data from Tenable NNM.
* This is an add-on powered by the Universal Configuration Console.
* This Add-on uses Splunk KV store for checkpoint mechanism.
* Author: Tenable Inc.
* Version: 8.0.0

# COMPATIBILITY MATRIX

* Browser: Google Chrome, Mozilla Firefox
* OS: Platform independent
* Splunk Enterprise version: 9.4.x and 9.3.x
* Supported Splunk Deployment: Splunk Cloud, Splunk Standalone, and Distributed Deployment

# REQUIREMENTS

* Appropriate access key and secret key for collecting data from TVM.
* Appropriate credentials or valid certificate for collecting data from TSC.
* Appropriate API Secret for collecting data from TOT (ICP).
* Python version: python3

# Release Notes

## Version 8.0.0

* Updated PyTenable to v1.6.2
* Added new input to collect TWAS data.
* Added new input to collect TASM data.
* Added support for providing the custom SSL certificate on the Account configuration page.
* Updated the alert actions by adding an option to select Tenable account that user wants to use.

## Version 7.0.0

* Migrated the Add-on to UCC framework.
* Added new input 'TVM Audit Logs'.
* Updated the Account and Input type labels.
* Updated the required permissions for TVM account.

## Version 6.4.7

- Resolve issue where asset_uuid is null in TVM Compliance data

## Version 6.4.6

- Resolve issue with TVM Compliance findings not converting correctly and erroring out

## Version 6.4.4

* Updated "Scan Machine for Tenable SC" alert action.

## Version 6.4.2

## Version 6.4.4
* Updated "Scan Machine for Tenable SC" alert action.

## Version 6.4.0
* Added new input to collect IO Compliance data.
* Updated pyTenable to v1.4.22
* Migrated to Add-on builder v4.2.0

## Version 6.3.6
* Resolve pyTenable dependency issue with Tenable.ot

## Version 6.3.5
* Added an option (Default off) to make TSC firstSeen and lastSeen timestamps report with milliseconds. Specifically we append .000 to the end of each timestamp.
* Set  `make_time_ms = True` in `local/inputs.conf` in the stanza section `[tenable_securitycenter://<name>]` for your specific TSC input.

## Version 6.3.1
* Added support of new module for collecting assets, vulnerabilities and plugins data from Tenable OT.
* Updated pyTenable to v1.4.16
* Removed "Verify SSL Certificate" checkbox from UI.
* Added CIM mapping for Tenable OT assets and plugins data.

## Version 6.1.4
* Updated SSL option as compulsory for cloud as per Splunk cloud compatibility.

## Version 6.1.3
* Updated SSL option as compulsory for tenable.io as per Splunk cloud compatibility.

## Version 6.1.2
* Fixed an certificate issue with T.sc

## Version 6.1.1
* Fixed an issue for adaptive response with T.sc
* vulns_indexed_buffer_interval(int) : Specifies the buffer indexed sync time for vulns call. It should more than 0.
* assets_buffer_interval(int) : Specifies the buffer sync time for assets call. It should more than 0.
* plugins_buffer_interval(int) : Specifies the buffer sync time for plugins call. It should more than 0.

## Version 6.1.0
* Replaced last_found and last_fixed filters with indexed_at while exporting vuln data from Tenable.io
* Resolved issue of missing vuln export data from Tenable.io

## Version 6.0.3
* Removed Host Audit Findings, Web Application Findings and Cloud Findings support

## Version 6.0.1
* Added support for Tenable.io Explore -> Assets (Cloud Resources, Web Applications) and Findings (Cloud Findings, Host Audits, Web Application Vulnerabilities)
* Fixed an issue with Tenable.sc, removed sort parameter while collecting vulnerabilities data by using analysis APIs
* Added configurable fields value support for two fields vulnerabilities number of asset and asset chunk size.\
  Path :TA-tenable/default/inputs.conf. Fields is mention in [tenable_io].\
  vuln_num_assets(int) : Specifies the number of assets used to chunk the vulnerabilities. The range is 50-5000.\
  assets_chunk_size(int) : Specifies the number of assets per exported chunk. The range is 100-10000.

## Version 5.2.4
* Added asset_hostname field in T.io vulns data
* Fixed an issue with how state of T.sc "reopened" vulns is changed

## Version 5.2.3
* Fixed an issue with how T.sc handles version checking

## Version 5.2.2
* Removed eventgen.conf from App package

## Version 5.2.1
* Fixed an issue with how T.sc plugin data was pulled
* Fixed an issue with how T.sc vulns with a "reopened" state are reported
* Fixed a python.version issue
* Fixed packaging process

## Version 5.2.0
* Upgraded AoB to v4.0.0
* Rectified code to support only python3

## Version 5.1.0
* Added support of Tenable.ad.


## Version 5.0.1
* Minor bug fixes.


## Version 5.0.0
* Added support to add port for Tenable.sc account type in the Configuration page.
* Added support for API Keys for Tenable.sc account type.
* Added deprecated tag to Tenable.sc Credentials account type.
* Hardcoded address field for Tenable.io account to cloud.tenable.com.
* Add new fields sc_uniqeness to tenable:sc:assets and tenable:sc:vulns sourcetypes to allow for easier deduplication of events over time.
* Add VPR and VPR drivers to tenable:*:vuln field alias.
* Add ACR and AES to tenable:io:assets to field alias.
* Add VPR and VPR drivers to tenable:*:plugin field alias.
* Added Parsing for Tenable.ot alert events.


## Version: 4.0.0
* Updated pytenable version
* Added hard-coded python 3 for Splunk Cloud support
* Fix eval-dest in props.conf for tenable:io:vuln
* Lower Tenable.io vulnerability download page size to 500 from 1000 to lower memory usage.


## Version: 3.2.3
* Resolve an issue with T.io accounts when used with a MITM proxy with non-valid certs

## Version: 3.2.2
* Resolve issue blocking Splunk cloud support

## Version: 3.2.1
* Make proxy test scripts easier to use

## Version: 3.2.0
* Improve Tenable.io asset event index time to make Tenable.io UI data comparison simpler
* Update pyTenable to v1.1.1
* Add scripts to allow a customer to test for proxy issues

## Version: 3.1.1
* Fixed an issue where in rare cases downloads could hang indefinitely
* Improved how unhandled exceptions are logged to improve debugging if they occur
* Update pytenable== 1.1.0
* Change T.io vuln export to num_page=1000
* Change T.sc vuln export default to 1500 from 1000
* v2.1.0 of the Tenable App for Splunk is required once you upgrade to 3.x.x of the Tenable Add-On for Splunk

## Version: 3.1.0
* Splunk 8 and Python 3 support
* Updated pyTenable to version 1.0.5
* Resolved an issue where tenable:io:plugin data was always pulling full set of data rather than a differential .

## Version: 3.0.0
* Migrated the add-on to pyTenable library
* Added "Sync Plugin Details" checkbox support for Tenable.io input
* Removed "Historical Fixed Vulnerability" checkbox support from Tenable.sc Mobile input

## Version: 2.0.4
* Fixed the issue with pulling deleted/terminated assets and fixed vulnerabilities

## Version: 2.0.3
* Fixed the issue of ingesting duplicate vulnerability events.
* Updated the checkpoint mechanism to store the latest time of an event for IO assets.

## Version: 2.0.2
* Fixed the validation issue while configuring cron interval with Splunk version less than 7.1.3 by adding dateutil python library.

## Version: 2.0.1
* Updated the checkpoint mechanism to store the latest time of an event for Vulnerability data.

## Version: 2.0.0
* Added data parsing for Tenable NNM
* Added support for proxy per account
* Added "Request Scan" and "Get Current Vulnerability" AR actions for Tenable.io
* Added support for mobile data

## Version: 1.0.6
* Moved macros from Technology Add-On For Tenable to Tenable App For Splunk.

# Upgrading to version 8.0.0

Follow the below steps to upgrade the Add-on to 8.0.0

* Disable all the inputs from the Inputs page of Tenable Add-on for Splunk.
* Install the Tenable Add-on for Splunk v8.0.0
* Restart the Splunk if required.
* Navigate to the Tenable Add-on for Splunk.
* From the Inputs page, enable the already created inputs or create new inputs with required fields.

# Upgrading to version 5.2.x

Follow the below steps to upgrade the Add-on to 5.2.x

* Disable all the inputs from the Inputs page of Tenable Add-on.
* Install the Tenable Add-on for Splunk v5.2.x
* Restart the Splunk if required and if prompt by Splunk.
* Navigate to the Tenable Add-on for Splunk.
* From the Configuration page, edit the existing created accounts and re-configure it.
* From the Inputs page, click on Disabled to enable already created inputs or click on Create New Input to create new inputs with required fields.

# Upgrade to version 2.0.0

* Delete $SPLUNK_HOME/etc/apps/TA-tenable/local/macros.conf file if exist.
* Update definition of "get_tenable_index" macro in the Tenable App For Splunk.
* Edit account and add appropriate proxy settings if proxy settings are previously configured.
* Remove proxy stanza from $SPLUNK_HOME/etc/apps/TA-tenable/local/ta_tenable_settings.conf
* Delete already configured inputs before upgrading the TA.

# OPEN SOURCE COMPONENTS AND LICENSES
* Some of the components included in Tenable Add-on for Splunk are licensed under free or open source licenses. We wish to thank the contributors to those projects.

  * dateutil version 2.8.2 https://pypi.org/project/python-dateutil/ (LICENSE https://github.com/dateutil/dateutil/blob/master/LICENSE)
  * croniter version 0.3.25 https://pypi.org/project/croniter/ (LICENSE https://github.com/kiorky/croniter/blob/master/docs/LICENSE)
  * pytz version 2018.3 https://pypi.org/project/pytz/ (LICENSE https://github.com/stub42/pytz/blob/master/src/LICENSE.txt)
  * tzlocal version 1.5.1 https://pypi.org/project/tzlocal/ (LICENSE https://github.com/regebro/tzlocal/blob/master/LICENSE.txt)
  * pyTenable version 1.4.14 https://pypi.org/project/pyTenable/ (LICENSE https://github.com/tenable/pyTenable/blob/master/LICENSE)
  * arrow 1.2.3 https://pypi.org/project/arrow/ (LICENSE https://github.com/crsmithdev/arrow/blob/master/LICENSE)

# RECOMMENDED SYSTEM CONFIGURATION

* Splunk forwarder system should have 12 GB of RAM and a six-core CPU to run this Technology Add-on smoothly.

# TOPOLOGY AND SETTING UP SPLUNK ENVIRONMENT

* This Add-On can be set up in two ways:
 1) **Standalone Mode**: Install the Add-on app on a single machine. This single machine would serve as a Search Head + Indexer + Heavy forwarder for this setup


 2) **Distributed Environment**: Install Add-on on search head and Add-on on Heavy forwarder (for REST API).

    * Add-on resides on search head machine and accounts need to be configured here.
    * Add-on needs to be installed and configured on the Heavy forwarder system.
    * Execute the following command on Heavy forwarder to forward the collected data to the indexer.
      /opt/splunk/bin/splunk add forward-server <indexer_ip_address>:9997
    * On Indexer machine, enable event listening on port 9997 (recommended by Splunk).
    * Add-on needs to be installed on search head for CIM mapping

# INSTALLATION OF APP

* This Add-on can be installed through UI using "Manage Apps" or extract zip file directly into /opt/splunk/etc/apps/ folder.

# CONFIGURATION OF APP

* Navigate to Tenable Add-on, click on "Configuration" page, go to "Account" tab and then click "Add", fill in "Account Name", "Tenable Account Type" and "Address" then select the appropriate "Tenable Account Type" and fill in either "Access Key" and "Secret Key" or "Username" and  "Password" or "Certificate Filename", "Key Filename" and "Key Password" or "API Secret" fields. The "Address" field value can be of the following format:
  * hostname:port eg. cloud.tenable.com:80
  * hostname eg. coud.tenable.com (In this case, port would be set to 443 by default)

* Navigate to Tenable Add-on, click on new input and then select "TWAS Assets & Vulns" and fill the "Name", "Interval", "Index", "Global Account" and "Lowest Severity to Store" fields.

* Navigate to Tenable Add-on, click on new input and then select "TVM Assets & Vulns" and fill the "Name", "Interval", "Index", "Global Account" and "Lowest Severity to Store" fields.

* Navigate to Tenable Add-on, click on new input and then select "TSC Assets & Vulns" and fill the "Name", "Interval", "Index", "Global Account", "Sync Plugin Details" fields.

* Navigate to Tenable Add-on, click on new input and then select "TSC Mobile Assets & Vulns" and fill the "Name", "Interval", "Index", "Global Account" fields.

* Navigate to Tenable Add-on, click on new input and then select "TOT (ICP) Assets & Vulns" and fill the "Name", "Interval", "Index", "Global Account" fields.

* Navigate to Tenable Add-on, click on new input and then select "TVM Compliance" and fill the "Name", "Interval", "Index", "Global Account", "Start Time" fields.

* Navigate to Tenable Add-on, click on new input and then select "TVM Audit Logs" and fill the "Name", "Interval", "Index", "Global Account", "Start Time" fields.

* Navigate to Tenable Add-on, click on new input and then select "TASM" and fill the "Name", "Interval", "Index", "Global Account", "Start Time" fields.

* To configure "Tenable NNM" navigate to Settings > Data Inputs > TCP/UDP > Add new > Add port > Next > Select Source type as "tenable:nnm:vuln" > Select Index > Review > Done

# SAMPLE EVENT GENERATOR

* The TA-tenable, comes with sample data files, which can be used to generate sample data for testing. In order to generate sample data, it requires the SA-Eventgen application.
* Typically eventgen is disabled for the TA and it will generate sample data at an interval of 1 hour. You can update this configuration from eventgen.conf.
* To collect sample data, the user needs to place eventgen.conf at the following location:
  * $SPLUNK_HOME/etc/apps/TA-tenable/local/eventgen.conf
* To get the required eventgen.conf, contact over provided support email below.

# ADAPTIVE RESPONSE ACTION

Following is the list of AR Actions for TVM and TSC provided by the Add-On that can be used from the Enterprise Security App.

### TVM
  1. **Get Vulnerability Summary from Tenable IO**: Get Current Vulnerability from Tenable IO.
  2. **Request Scan for Tenable IO**: Request a scan for Tenable IO asset.

### TSC
  1. **Get Vulnerability Summary from Tenable SC**: Get Current Vulnerability from Tenable SC server.
  2. **Launch Policy based Remediation Scan for Tenable SC**: Launch a policy based remediation scan on Tenable SC server.
  3. **Scan Machine for Tenable SC**: Start a scan for machine on Tenable SC server.


# TROUBLESHOOTING

* Environment variable SPLUNK_HOME must be set
* To troubleshoot TVM Assets & Vulns mod-input check $SPLUNK_HOME/var/log/splunk/ta_tenable_tenable_io.log file.
* To troubleshoot TSC Assets & Vulns mod-input check $SPLUNK_HOME/var/log/splunk/ta_tenable_tenable_securitycenter.log file.
* To troubleshoot TSC Mobile Assets & Vulns mod-input check $SPLUNK_HOME/var/log/splunk/ta_tenable_tenable_securitycenter_mobile.log file.
* To troubleshoot TOT (ICP) Assets & Vulns mod-input check $SPLUNK_HOME/var/log/splunk/ta_tenable_tenable_ot_security_icp.log file.
* To troubleshoot TVM Compliance mod-input check $SPLUNK_HOME/var/log/splunk/ta_tenable_tenable_io_compliance.log file.
* To troubleshoot TVM Audit Logs mod-input check $SPLUNK_HOME/var/log/splunk/ta_tenable_tenable_io_audit_logs.log file.
* To troubleshoot TASM mod-input check $SPLUNK_HOME/var/log/splunk/ta_tenable_tenable_asm.log file.
* To troubleshoot TWAS Assets & Vulns mod-input check $SPLUNK_HOME/var/log/splunk/ta_tenable_tenable_was.log file.
* For TSC Assets & Vulns and TSC Mobile Assets & Vulns if you have large number of data then it is recommended to update "page_size" in $SPLUNK_HOME/etc/apps/TA-tenable/default/inputs.conf and restart the Splunk.
* On distributed environment if events are getting dropped on forwarder then it is recommended to update "max_event_size" in $SPLUNK_HOME/etc/apps/TA-tenable/default/inputs.conf and restart the splunk.
* To troubleshoot "Get Vulnerability Summary from Tenable IO" AR Action check $SPLUNK_HOME/var/log/splunk/get_io_vulnerability_summary_modalert.log file.
* To troubleshoot "Request Scan for Tenable IO" AR Action check $SPLUNK_HOME/var/log/splunk/io_request_scan_modalert.log file.
* To troubleshoot "Get Vulnerability Summary from Tenable SC" AR Action check $SPLUNK_HOME/var/log/splunk/tenable_vulnerability_summary_modalert.log file.
* To troubleshoot "Launch Policy based Remediation Scan for Tenable SC" AR Action check $SPLUNK_HOME/var/log/splunk/launch_remediation_scan_modalert.log file.
* To troubleshoot "Scan Machine for Tenable SC" AR Action check $SPLUNK_HOME/var/log/splunk/activate_machine_scan_modalert.log file.
* To troubleshoot SSL Verification related error, make sure you have added a valid SSL Certificate and if SSL Verification is not needed then it can be set to `False` from the below mentioned path:
  - $SPLUNK_HOME/etc/apps/TA-tenable/bin/tenable_consts.py

# UNINSTALL & CLEANUP STEPS

* Remove $SPLUNK_HOME/etc/apps/TA-tenable
* Remove $SPLUNK_HOME/var/log/splunk/**ta_tenable_tenable_io.log**
* Remove $SPLUNK_HOME/var/log/splunk/**ta_tenable_tenable_securitycenter.log**
* Remove $SPLUNK_HOME/var/log/splunk/**ta_tenable_tenable_securitycenter_mobile.log**
* Remove $SPLUNK_HOME/var/log/splunk/**ta_tenable_tenable_ot_security_icp.log**
* Remove $SPLUNK_HOME/var/log/splunk/**ta_tenable_tenable_io_compliance.log**
* Remove $SPLUNK_HOME/var/log/splunk/**ta_tenable_tenable_io_audit_logs.log**
* Remove $SPLUNK_HOME/var/log/splunk/**ta_tenable_tenable_io_audit_logs.log**
* Remove $SPLUNK_HOME/var/log/splunk/**ta_tenable_tenable_asm.log**
* Remove $SPLUNK_HOME/var/log/splunk/**ta_tenable_tenable_was.log**
* Remove $SPLUNK_HOME/var/log/splunk/**get_io_vulnerability_summary_modalert.log**
* Remove $SPLUNK_HOME/var/log/splunk/**io_request_scan_modalert.log**
* Remove $SPLUNK_HOME/var/log/splunk/**tenable_vulnerability_summary_modalert.log**
* Remove $SPLUNK_HOME/var/log/splunk/**launch_remediation_scan_modalert.log**
* Remove $SPLUNK_HOME/var/log/splunk/**activate_machine_scan_modalert.log**
* To reflect the cleanup changes in UI, Restart Splunk Enterprise instance

# SUPPORT

* Support Offered: Yes
* Support Email: support@tenable.com

### Copyright 2025 Tenable, Inc.
