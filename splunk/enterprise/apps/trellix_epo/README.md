# Trellix MVision EPO Add-on for Splunk

Trellix MVision EPO Add-on for Splunk was developed to solve the data ingest from Trellix MVision EPO (formerly McAfee EPO) API on Splunk to use cases in Splunk Enterprise and Splunk Enterprise Security. Trellix MVision EPO Add-on for Splunk is the Technical Add-on (TA) developed for ingest or map security data collected from Trellix MVision EPO API. Trellix MVision EPO Add-on for Splunk provides common information model (CIM) knowledge, to use with other Splunk Enterprise Apps such Splunk Enterprise Security.

## Release notes

- Version 1.0.0: Sep 01, 2023 App created. Creates integration between Trellix EPO and Splunk Enterprise to ingest data via API. Allows multiple accounts to create connections, and supports duplicated accounts with multiple tenants. Exclusive usage for Trellix EPO API, because Endpoint path is fixed in code. Allows to use regional-based Endpoint URL, refers to Trellix MVision EPO documentation in <https://docs.trellix.com/bundle/epolicy-orchestrator-saas-product-guide/>
- Version 1.0.1: Feb 29, 2024 Solved an issue related with timeformat that does not allow to ingest data into Splunk when receivedutc field value has not milliseconds in it. Now, timeformat function will check if the timestamp field has or not milliseconds and, with that, will apply the timeformat required.
- Version 1.0.2: Mar 11, 2024 Renamed the application to correct a misunderstanding of the name, since the application only applies to Trellix MVision EPO (formerly McAfee EPO) SaaS, and not to other SaaS or On-Prem Trellix products. Updated to make it Cloud-compatible, based on new Cloud Vetting Policies from Splunk.
- Version 1.0.3: May 01, 2024 Corrected Help information in Configuration page that has an issue for text length.
- Version 1.0.4: Mar 31, 2025 Updated Splunk Python Library to newest one based on Splunk Vetted Program.
- Version 1.0.5: Apr 10, 2025 Updated other Python libraries to latest versions. Added server.conf file to enable cluster replication.
- Version 1.0.6: May 16, 2025 Updated Trellix IAM URI because of Trellix changes, as documented in <https://docs.trellix.com/bundle/epolicy-orchestrator-saas-landing>

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

[MIT](https://choosealicense.com/licenses/mit/)
