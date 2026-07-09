RELEASE NOTES:

Version 1.0.6: May 16, 2025
Updated Trellix IAM URI because of Trellix changes, as documented in <https://docs.trellix.com/bundle/epolicy-orchestrator-saas-landing>

Version 1.0.5: Apr 10, 2025
Updated other Python libraries to latest versions. Added server.conf file to enable cluster replication.

Version 1.0.4: Mar 31, 2025
Updated Splunk Python Library to newest one based on Splunk Vetted Program.

Version 1.0.3: May 01, 2024
Corrected Help on URL field in Configuration page because of length exceeds maximum characters length

Version 1.0.2: Mar 11, 2024
Renamed the application to correct a misunderstanding of the name, since the application only applies to Trellix MVision EPO (formerly McAfee EPO) SaaS, and not to other SaaS or On-Prem Trellix products. Updated to make it Cloud-compatible, based on new Cloud Vetting Policies from Splunk.

Version 1.0.1: Feb 29, 2024
Solved an issue related with timeformat that does not allow to ingest data into Splunk when receivedutc field value has not milliseconds in it. Now, timeformat function will check if the timestamp field has or not milliseconds and, with that, will apply the timeformat required.

Version 1.0.0: Sep 01, 2023
App created.
Creates integration between Trellix EPO and Splunk Enterprise to ingest data via API.
Allows multiple accounts to create connections, and supports duplicated accounts with multiple tenants.
Exclusive usage for Trellix EPO API, because Endpoint path is fixed in code. Allows to use regional-based Endpoint URL, refers to Trellix documentation in <https://docs.trellix.com/bundle/epolicy-orchestrator-saas-product-guide/page/UUID-beb1dd85-b05c-ec11-5d94-b9b647f99a55.html>