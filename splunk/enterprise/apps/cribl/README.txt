# Cribl Logging for Splunk

This add-on collects and ingests Cribl Stream notifications, access and/or audit logs. (Currently Cribl.Cloud is not supported)

For installation of the add-on follow Splunk docs, https://docs.splunk.com/Documentation/AddOns/released/Overview/Installingadd-ons

Note you will have to configure notifications in Cribl first, https://docs.cribl.io/stream/notifications

Configurations

- Navigate to Configuration of the add-on and add a new account to use (user must have admin access to Cribl)
- Navigate to Configuration --> Proxy of the add-on and configure the Proxy settings
- Go to Inputs tab and click on Create New Input button
- - Name: Enter a unique name for the data input
- - Interval: recommended is 60 seconds
- - Index: Search for the destination index
- - Global Account: Select the account you wish to use for the collection
- - Cribl Url: Enter your Cribl url with your port number at the end, Note the url must use https protocol (e.g https://cribl.example:9000)
- - Log ID: Select the Log ID to be collected. (Notifications, Audit or Access)
- - Earliest: If you wish to collect logs older than 30 days, enter the earliest epoch time to start from. By default the add-on will backfill by 30 days
- - Click add to save your input.

# Binary File Declaration
/opt/development/splunk/var/data/tabuilder/package/TA-cribl-logging-for-splunk/bin/ta_cribl_logging_for_splunk/aob_py3/markupsafe/_speedups.cpython-37m-x86_64-linux-gnu.so: this file does not require any source code
