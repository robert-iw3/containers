---
title: "Security Requirements Applicability Matrix"
subtitle: "Splunk Enterprise 10.4.2 — application configuration"
author: "Security Control Assessment"
date: "2026-11-09"
---

<!-- Generated from inventory/ by bin/build-matrix.py. Regenerate rather than editing. -->
\newpage

## Document Control

| Field | Value |
|---|---|
| Document title | Security Requirements Applicability Matrix |
| System | Splunk Enterprise 10.4.2, application configuration |
| Baseline | NIST SP 800-53 Revision 5 |
| Governing baseline | Central Log Server SRG V3R5 |
| Governing baseline | Web Server SRG V4R5 |
| Product reference | Splunk Enterprise 8.x for Linux STIG V2R3, sunsetted |
| Requirements determined | 253 of 253 |
| Controls answered | 45 |
| Version | 2.0 |
| Date | 2026-11-09 |
| Classification | Unclassified |

**Purpose.** This matrix records, for every requirement in the governing Security Requirements Guides, whether the requirement applies to Splunk Enterprise as an application, what mechanism implements it, and what weight the determination carries. It answers each NIST SP 800-53 Revision 5 control the requirements cite, so the determinations can be read against the control catalog.

**Audience.** Information System Security Officer, Information System Security Manager, Security Control Assessor, and Authorizing Official.

**Scope.** The application configuration of Splunk Enterprise. Where a requirement is implemented by a baseline other than the application, the providing baseline is named; an inherited control with no named provider is recorded as a finding rather than an inheritance.

### What this document does not state

This matrix records **applicability**, which is a property of the requirement and the product. It records no instance's configured state, and the word satisfied appears in it only as the name of a finding category. Whether a given instance satisfies an applicable requirement is established by an assessment of that instance and reported in its checklist. A determination of Applicable here is therefore not a finding against any system; it states that the requirement is in scope and names what an assessment examines.

**Related documents.** Splunk for Assessors (docs/01-splunk-for-assessors.md).

\newpage

## Assessment method

Three benchmarks govern this system. There is no current Splunk Enterprise STIG. The sunsetted Splunk Enterprise 8.x for Linux STIG V2R3 is used as the product-specific implementation published by the benchmark authority, and every setting it names was re-examined against version 10.4.2. Findings raised against that reference are recorded in their own section, because a site following it verbatim would configure settings that no longer exist.

| Benchmark | Requirements | Role |
|---|---|---|
| Central Log Server SRG V3R5 | 127 | Governing requirements |
| Web Server SRG V4R5 | 126 | Governing requirements |
| Splunk Enterprise 8.x STIG V2R3 | 37 | Product reference, re-verified |

**Traceability.** Each requirement cites one or more Control Correlation Identifiers, and the published CCI list maps each identifier to an 800-53 control. That composition, not the assessor's judgment, determines which controls this system answers.

**Assessment methods applied.** Examine: the 128 configuration specification files shipped with Splunk Enterprise 10.4.2, which constitute the complete configuration surface of the product; and the benchmark check and fix text. Test: configuration read back from a reference instance through the configuration inspection utility to establish that a named mechanism exists and is readable.

### Evidence grading

Every determination carries an evidence grade. The grade states what the assessor did, and it is what gives the determination its weight.

| Grade | Basis | Supports |
|---|---|---|
| A | Capability absent. An exhaustive search of the complete specification set establishes... | Not Applicable |
| B | Benchmark clause met. The requirement's own check text carries a Not Applicable... | Not Applicable |
| C | Mechanism named. A specific configuration file, stanza and key implements the... | Applicable |
| D | Outside the application boundary. The control is implemented by a named baseline other... | Applicable, inherited |
| E | Undetermined. Applicability could not be established; the probe that would settle it... | Undetermined |

A determination of Not Applicable is admissible only at grade A or B. That a control is implemented by the operating system is grade D: the requirement still applies to the system and only the implementing component differs. Absence of documentation is not absence of capability.

### Independent challenge

Every determination of Not Applicable and every determination that a control is implemented outside the application boundary was submitted to an independent reviewer acting for the Authorizing Official, instructed to refute rather than confirm it. Those two dispositions each assert that no further work is owed, and an Authorizing Official examines them first.

**18 determinations were revised** as a result, each recorded in its own section below. After challenge, no requirement in either governing baseline is determined Not Applicable to Splunk Enterprise.

| Integrity check | Result |
|---|---|
| Requirements determined | 253 of 253 |
| Not Applicable below grade B | 0 |
| Inherited with no named provider | 0 |

\newpage

## Summary of determinations

| Determination | Finding category | Control origination | Count |
|---|---|---|---|
| Applicable | Applicable | system-specific | 236 |
| Organizational | Applicable | common | 16 |
| Undetermined | Undetermined | system-specific | 1 |
| **Total** | | | **253** |

| Evidence grade | Count |
|---|---|
| C | 240 |
| D | 12 |
| E | 1 |

| Severity | Count |
|---|---|
| CAT I (high) | 19 |
| CAT II (medium) | 188 |
| CAT III (low) | 46 |

| Product reference status | Count |
|---|---|
| no reference | 152 |
| confirmed in 10 4 2 | 75 |
| withdrawn | 21 |
| renamed | 5 |

\newpage

## Control answers

Each control is cited by at least one requirement in the governing baselines. The applicability of a control follows the requirements that answer it. Where every requirement answering a control is applicable, the control is in scope for the application in full.

| Control | Requirements | Applicability | Origination |
|---|---|---|---|
| AC-10 | 2 | In scope | system-specific |
| AC-12 | 5 | In scope | system-specific |
| AC-17 | 6 | In scope | system-specific |
| AC-2 | 12 | In scope | system-specific |
| AC-3 | 2 | In scope | system-specific |
| AC-4 | 1 | In scope | system-specific |
| AC-6 | 1 | In scope | system-specific |
| AC-7 | 2 | In scope | system-specific |
| AC-8 | 2 | In scope | system-specific |
| AU-10 | 1 | In scope | system-specific |
| AU-11 | 1 | In scope | common |
| AU-12 | 10 | In scope | system-specific |
| AU-14 | 2 | In scope | system-specific |
| AU-3 | 14 | In scope | system-specific |
| AU-4 | 5 | In scope | system-specific |
| AU-5 | 4 | In scope | system-specific |
| AU-6 | 3 | In scope | system-specific |
| AU-7 | 20 | In scope | system-specific |
| AU-8 | 6 | In scope | system-specific |
| AU-9 | 14 | In scope | common/system-specific |
| CM-14 | 3 | In scope | common/system-specific |
| CM-5 | 3 | In scope | system-specific |
| CM-6 | 11 | In scope | system-specific |
| CM-7 | 15 | In scope | system-specific |
| IA-11 | 1 | In scope | system-specific |
| IA-2 | 13 | In scope | system-specific |
| IA-5 | 34 | In scope | common/system-specific |
| IA-6 | 1 | In scope | system-specific |
| IA-7 | 4 | In scope | system-specific |
| MA-4 | 1 | In scope | system-specific |
| SA-22 | 2 | In scope | common |
| SC-13 | 2 | In scope | system-specific |
| SC-17 | 2 | In scope | system-specific |
| SC-18 | 1 | In scope | system-specific |
| SC-2 | 3 | In scope | system-specific |
| SC-23 | 12 | In scope | system-specific |
| SC-24 | 3 | In scope | system-specific |
| SC-28 | 4 | In scope | system-specific |
| SC-3 | 1 | In scope | system-specific |
| SC-45 | 4 | In scope | system-specific |
| SC-5 | 3 | In scope | system-specific |
| SC-8 | 13 | In scope | system-specific |
| SI-10 | 3 | In scope, with undetermined requirements | system-specific |
| SI-11 | 3 | In scope | system-specific |
| SI-2 | 2 | In scope | common |

\newpage

## Applicable requirements

These requirements are in scope for the Splunk application and are implemented by its own configuration. The mechanism column names the configuration that implements the requirement; Appendix A records the basis, the citation and what an assessment of an instance examines.

| Requirement | Severity | Grade | Requirement | Mechanism |
|---|---|---|---|---|
| SRG-APP-000033-AU-001610 | CAT I | C | The Central Log Server must be configured to enforce approved authorizations... | authorize.conf [role_<roleName>] with importRoles, grantableRoles, srchFilter,... |
| SRG-APP-000148-AU-002270 | CAT I | C | The Central Log Server must be configured to uniquely identify and... | authentication.conf [authentication] authType, authSettings;... |
| SRG-APP-000171-AU-002540 | CAT I | C | For accounts using password authentication, the Central Log Server must be... | authentication.conf [authentication] passwordHashAlgorithm |
| SRG-APP-000172-AU-002550 | CAT I | C | For accounts using password authentication, the Central Log Server must use... | splunk-launch.conf SPLUNK_FIPS; authentication.conf [authentication]... |
| SRG-APP-000172-WSR-000104 | CAT I | C | The web server must encrypt passwords during transmission. | web.conf [settings] enableSplunkWebSSL, serverCert, privKeyPath,... |
| SRG-APP-000175-AU-002630 | CAT I | C | The Central Log Server, when using PKI-based authentication, must validate... | web.conf [settings] sslRootCAPath, requireClientCert; server.conf [sslConfig]... |
| SRG-APP-000176-AU-002640 | CAT I | C | The Central Log Server, when using PKI-based authentication, must enforce... | web.conf [settings] privKeyPath, sslPassword; server.conf [sslConfig]... |
| SRG-APP-000178-AU-002660 | CAT I | C | The Central Log Server must obfuscate authentication information during the... | web.conf [settings] enable_insecure_login, enableSplunkWebSSL; limits.conf... |
| SRG-APP-000179-AU-002670 | CAT I | C | The Central Log Server must use FIPS-validated SHA-1 or higher hash function... | splunk-launch.conf SPLUNK_FIPS; server.conf [sslConfig] sslVersions,... |
| SRG-APP-000179-WSR-000110 | CAT I | C | The web server must use cryptographic modules that meet the requirements of... | splunk-launch.conf SPLUNK_FIPS; authentication.conf [authentication]... |
| SRG-APP-000224-WSR-000135 | CAT I | C | The web server must generate a unique session identifier for each session... | splunk-launch.conf SPLUNK_FIPS (the launch file carries no stanzas) |
| SRG-APP-000429-WSR-000113 | CAT I | C | The web server must encrypt user identifiers and passwords. | authentication.conf [authentication] authType, passwordHashAlgorithm;... |
| SRG-APP-000439-AU-004310 | CAT I | C | The Central Log Server must be configured to protect the confidentiality and... | inputs.conf [splunktcp-ssl:<port>] and [SSL] serverCert, sslPassword,... |
| SRG-APP-000439-WSR-000151 | CAT I | C | The web server must employ cryptographic mechanisms (TLS/DTLS/SSL) preventing... | web.conf [settings] enableSplunkWebSSL, serverCert, privKeyPath, sslPassword,... |
| SRG-APP-000514-AU-002890 | CAT I | C | The Central Log Server must implement NIST FIPS-validated cryptography for the... | splunk-launch.conf, SPLUNK_FIPS = 1, set before the instance is first started |
| SRG-APP-000610-AU-000050 | CAT I | C | The Central Log Server must use FIPS-validated SHA-2 or higher hash function... | splunk-launch.conf: SPLUNK_FIPS; authentication.conf [authentication]:... |
| SRG-APP-000001-WSR-000001 | CAT II | C | The web server must limit the number of allowed simultaneous session requests. | web.conf [settings] maxSockets, maxThreads, server.thread_pool,... |
| SRG-APP-000001-WSR-000002 | CAT II | C | The web server must perform server-side session management. | web.conf [settings] tools.sessions.on, tools.sessions.storage_type,... |
| SRG-APP-000014-WSR-000006 | CAT II | C | The web server must use encryption strength in accordance with the... | web.conf [settings] enableSplunkWebSSL, sslVersions, cipherSuite, ecdhCurves;... |
| SRG-APP-000015-WSR-000014 | CAT II | C | The web server must use cryptography to protect the integrity of remote... | web.conf [settings] enableSplunkWebSSL, serverCert, privKeyPath,... |
| SRG-APP-000016-WSR-000005 | CAT II | C | The web server must generate information to be used by external applications... | web.conf [settings] log.access_file; audit.conf [auditTrail] queueing;... |
| SRG-APP-000026-AU-000580 | CAT II | C | The Central Log Server must automatically audit account creation. | audit.conf [auditTrail] queueing, with account creation recorded to the _audit... |
| SRG-APP-000027-AU-000590 | CAT II | C | The Central Log Server must automatically audit account modification. | audit.conf [auditTrail] queueing, with account and role modification recorded... |
| SRG-APP-000028-AU-000600 | CAT II | C | The Central Log Server must automatically audit account disabling actions. | audit.conf [auditTrail] queueing, with the role-removal or account-removal... |
| SRG-APP-000029-AU-000610 | CAT II | C | The Central Log Server must automatically audit account removal actions. | audit.conf [auditTrail] queueing, with account removal recorded to the _audit... |
| SRG-APP-000033-WSR-000169 | CAT II | C | The web server must enforce approved authorizations for logical access to... | web.conf [settings] requireClientCert, enableCertBasedUserAuth,... |
| SRG-APP-000065-AU-000240 | CAT II | C | The Central Log Server must enforce the limit of three consecutive invalid... | authentication.conf [splunk_auth] lockoutUsers, lockoutAttempts,... |
| SRG-APP-000080-AU-000010 | CAT II | C | The Central Log Server must be configured to protect the data sent from hosts... | indexes.conf, per-index stanza [<index name>], key enableDataIntegrityControl;... |
| SRG-APP-000086-AU-000390 | CAT II | C | Where multiple log servers are installed in the enclave, each log server must... | outputs.conf [tcpout] defaultGroup, [tcpout:<target_group>] server,... |
| SRG-APP-000089-AU-000400 | CAT II | C | The Central Log Server must be configured to retain the DoW-defined attributes... | props.conf per-sourcetype stanzas: DATETIME_CONFIG, TIME_PREFIX, TIME_FORMAT,... |
| SRG-APP-000089-WSR-000047 | CAT II | C | The web server must generate, at a minimum, log records for system startup and... | web.conf log.access_file, log.access_maxsize, log.access_maxfiles,... |
| SRG-APP-000092-WSR-000055 | CAT II | C | The web server must initiate session logging upon start up. | web.conf log.access_file, log.error_maxsize, appServerPorts; restmap.conf... |
| SRG-APP-000095-WSR-000056 | CAT II | C | The web server must produce log records containing sufficient information to... | web.conf log.access_file, log.access_maxsize, log.access_maxfiles,... |
| SRG-APP-000096-WSR-000057 | CAT II | C | The web server must produce log records containing sufficient information to... | web.conf log.access_file and log.error_maxsize; props.conf TIME_PREFIX,... |
| SRG-APP-000097-WSR-000058 | CAT II | C | The web server must produce log records containing sufficient information to... | restmap.conf per-endpoint stanzas with includeInAccessLog; web.conf... |
| SRG-APP-000098-WSR-000059 | CAT II | C | The web server must produce log records containing sufficient information to... | web.conf log.access_file, tools.proxy.on, tools.proxy.base, trustedIP;... |
| SRG-APP-000098-WSR-000060 | CAT II | C | A web server, behind a load balancer or proxy server, must produce log records... | web.conf tools.proxy.on with tools.proxy.base, and trustedIP to bound the... |
| SRG-APP-000099-WSR-000061 | CAT II | C | The web server must produce log records that contain sufficient information to... | web.conf log.access_file and log.error_maxsize; restmap.conf per-endpoint... |
| SRG-APP-000100-WSR-000064 | CAT II | C | The web server must produce log records containing sufficient information to... | web.conf log.access_file, remoteUser, remoteUserMatchExact, trustedIP;... |
| SRG-APP-000108-WSR-000166 | CAT II | C | The web server must use a logging mechanism that is configured to alert the... | health.conf [health_reporter] and [feature:<name>] with alert.disabled,... |
| SRG-APP-000116-WSR-000066 | CAT II | C | The web server must use the internal system clock to generate time stamps for... | web.conf [settings] log.access_file names the web access log; props.conf... |
| SRG-APP-000118-AU-000100 | CAT II | C | The Central Log Server must protect audit information from any type of... | authorize.conf [role_<roleName>] srchIndexesAllowed, srchIndexesDefault,... |
| SRG-APP-000118-WSR-000068 | CAT II | C | Web server log files must only be accessible by privileged users. | authorize.conf [role_<roleName>] srchIndexesAllowed and srchIndexesDisallowed... |
| SRG-APP-000119-AU-000110 | CAT II | C | The Central Log Server must protect audit information from unauthorized... | authorize.conf [capability::delete_by_keyword] with [role_<roleName>]... |
| SRG-APP-000119-WSR-000069 | CAT II | C | The log information from the web server must be protected from unauthorized... | authorize.conf [capability::delete_by_keyword] with [role_<roleName>]... |
| SRG-APP-000120-AU-000120 | CAT II | C | The Central Log Server must protect audit information from unauthorized... | authorize.conf [capability::delete_by_keyword] with [role_<roleName>]... |
| SRG-APP-000120-WSR-000070 | CAT II | C | The log information from the web server must be protected from unauthorized... | authorize.conf [capability::delete_by_keyword] with [role_<roleName>]... |
| SRG-APP-000121-AU-000130 | CAT II | C | The Central Log Server must protect audit tools from unauthorized access. | default.meta [views], [savedsearches] and per-object stanzas with access =... |
| SRG-APP-000122-AU-000140 | CAT II | C | The Central Log Server must protect audit tools from unauthorized modification. | default.meta access write list on the object, its app and its category;... |
| SRG-APP-000123-AU-000150 | CAT II | C | The Central Log Server must protect audit tools from unauthorized deletion. | default.meta access write list on the containing app; authorize.conf... |
| SRG-APP-000125-WSR-000071 | CAT II | C | The log data and records from the web server must be backed up onto a... | indexes.conf remotePath, coldToFrozenDir and coldToFrozenScript over the... |
| SRG-APP-000131-WSR-000051 | CAT II | C | All web server files must be verified for their integrity (e.g., checksums and... | limits.conf [system_checks] installed_files_integrity,... |
| SRG-APP-000141-AU-000090 | CAT II | C | The Central Log Server must be configured to disable non-essential capabilities. | app.conf [install] state = disabled ... |
| SRG-APP-000141-WSR-000015 | CAT II | C | The web server must not perform user management for hosted applications. | authentication.conf [authentication] authType = [Splunk ... |
| SRG-APP-000141-WSR-000075 | CAT II | C | The web server must only contain services and functions necessary for operation. | app.conf [install] state = disabled ... |
| SRG-APP-000141-WSR-000076 | CAT II | C | The web server must not be a proxy server. | web.conf [settings] enable_proxy_write, tools.proxy.on, tools.proxy.base;... |
| SRG-APP-000141-WSR-000077 | CAT II | C | The web server must provide install options to exclude the installation of... | app.conf [install] state = disabled ... |
| SRG-APP-000141-WSR-000078 | CAT II | C | Web server accounts not used by installed features (i.e., tools, utilities,... | authentication.conf [authentication] authType and the native user store;... |
| SRG-APP-000141-WSR-000080 | CAT II | C | The web server must provide install options to exclude installation of utility... | app.conf [install] state = disabled ... |
| SRG-APP-000141-WSR-000081 | CAT II | C | The web server must have Multipurpose Internet Mail Extensions (MIME) that... | authorize.conf [capability::edit_scripted], [capability::run_custom_command],... |
| SRG-APP-000141-WSR-000082 | CAT II | C | The web server must allow the mappings to unused and vulnerable scripts to be... | commands.conf [<STANZA_NAME>] with filename, type and python.version;... |
| SRG-APP-000141-WSR-000083 | CAT II | C | The web server must have resource mappings set to disable the serving of... | web.conf [settings] static_endpoint, static_dir, root_endpoint,... |
| SRG-APP-000141-WSR-000085 | CAT II | C | The web server must have Web Distributed Authoring (WebDAV) disabled. | web.conf [settings] enable_secure_entity_move, enable_insecure_login,... |
| SRG-APP-000141-WSR-000086 | CAT II | C | The web server must protect system resources and privileged operations from... | authorize.conf [capability::<capability>] and [role_<roleName>] with... |
| SRG-APP-000141-WSR-000087 | CAT II | C | Users and scripts running on behalf of users must be contained to the document... | web.conf [settings] root_endpoint, static_endpoint, static_dir,... |
| SRG-APP-000142-WSR-000089 | CAT II | C | The web server must be configured to use a specified IP address and port. | web.conf [settings] server.socket_host, httpport, mgmtHostPort, listenOnIPv6;... |
| SRG-APP-000149-AU-002280 | CAT II | C | The Central Log Server must use multifactor authentication for network access... | authentication.conf [authentication] externalTwoFactorAuthVendor,... |
| SRG-APP-000150-AU-002320 | CAT II | C | The Central Log Server must use multifactor authentication for network access... | authentication.conf [authentication] externalTwoFactorAuthVendor,... |
| SRG-APP-000151-AU-002330 | CAT II | C | The Central Log Server must use multifactor authentication for local access... | authentication.conf [<duo-externalTwoFactorAuthSettings-key>]... |
| SRG-APP-000154-AU-002360 | CAT II | C | The Central Log Server must be configured to use multifactor authentication... | web.conf [settings] enableCertBasedUserAuth, certBasedUserAuthMethod,... |
| SRG-APP-000156-AU-002380 | CAT II | C | The Central Log Server must use FIPS-validated SHA-1 or higher hash function... | web.conf [settings] enableSplunkWebSSL, serverCert, privKeyPath, sslVersions,... |
| SRG-APP-000163-AU-002470 | CAT II | C | The Central Log Server must disable accounts (individuals, groups, roles, and... | server.conf [teleport_supervisor] disabled; web-features.conf... |
| SRG-APP-000164-AU-002480 | CAT II | C | The Central Log Server must be configured to enforce a minimum 15-character... | authentication.conf [splunk_auth] minPasswordLength |
| SRG-APP-000175-WSR-000095 | CAT II | C | The web server must perform RFC 5280-compliant certification path validation. | web.conf [settings] enableCertBasedUserAuth, requireClientCert, sslRootCAPath;... |
| SRG-APP-000176-WSR-000096 | CAT II | C | Only authenticated system administrators or the designated PKI Sponsor for the... | web.conf, [settings]: privKeyPath names the Splunk Web private key and... |
| SRG-APP-000179-WSR-000111 | CAT II | C | The web server must use cryptographic modules that meet the requirements of... | splunk-launch.conf SPLUNK_FIPS; authentication.conf [authentication]... |
| SRG-APP-000181-AU-000200 | CAT II | C | The Central Log Server must be configured to perform audit reduction that... | savedsearches.conf [<stanza name>] search with dispatch.earliest_time and... |
| SRG-APP-000206-WSR-000128 | CAT II | C | A web server using mobile code must meet DoD-defined mobile code requirements. | web-features.conf [feature:dashboards_csp]... |
| SRG-APP-000211-WSR-000030 | CAT II | C | Web server accounts accessing the directory tree, the shell, or other... | authorize.conf [role_<roleName>] capability assignment, importRoles,... |
| SRG-APP-000211-WSR-000031 | CAT II | C | Anonymous user access to the web server application directories must be... | restmap.conf [<rest endpoint name>:<description>] requireAuthentication,... |
| SRG-APP-000211-WSR-000129 | CAT II | C | The web server must separate the hosted applications from hosted web server... | server.conf [httpServer] (management listener, acceptFrom); web.conf... |
| SRG-APP-000219-WSR-000190 | CAT II | C | The web server must restrict a consistent inbound source IP for the entire... | server.conf [sslConfig] requireClientCert; server.conf [general]... |
| SRG-APP-000219-WSR-000191 | CAT II | C | The web server must restrict a consistent inbound source IP for the entire... | web.conf [settings] requireClientCert, enableCertBasedUserAuth,... |
| SRG-APP-000220-WSR-000201 | CAT II | C | The web server must invalidate session identifiers upon hosted application... | server.conf [general] sessionTimeout, invalidateSessionTokensOnLogout,... |
| SRG-APP-000223-WSR-000011 | CAT II | C | Cookies exchanged between the web server and client, such as session cookies,... | web.conf [settings] tools.sessions.httponly, tools.sessions.secure,... |
| SRG-APP-000223-WSR-000145 | CAT II | C | The web server must accept only system-generated session identifiers. | web.conf [settings] tools.sessions.on, tools.sessions.storage_type,... |
| SRG-APP-000224-WSR-000136 | CAT II | C | The web server must generate unique session identifiers that cannot be... | splunk-launch.conf SPLUNK_FIPS; web.conf [settings] tools.sessions.on (no key... |
| SRG-APP-000224-WSR-000137 | CAT II | C | The web server must generate a session ID long enough that it cannot be... | web.conf [settings] tools.sessions.on (session layer); no key in the... |
| SRG-APP-000224-WSR-000138 | CAT II | C | The web server must generate a session ID using as much of the character set... | web.conf [settings] tools.sessions.on (session layer); no key in the... |
| SRG-APP-000224-WSR-000139 | CAT II | C | The web server must generate unique session identifiers with definable entropy. | splunk-launch.conf SPLUNK_FIPS (random number generator and algorithm... |
| SRG-APP-000225-WSR-000074 | CAT II | C | The web server must augment re-creation to a stable and known baseline. | The conf-file layering system (shipped default layer plus site local layer)... |
| SRG-APP-000225-WSR-000140 | CAT II | C | The web server must be built to fail to a known safe state if system... | server.conf [diskUsage] minFreeSpace, pollingFrequency, pollingTimerFrequency;... |
| SRG-APP-000225-WSR-000141 | CAT II | C | The web server must provide a clustering capability. | server.conf [clustering] mode, manager_uri, manager_switchover_mode,... |
| SRG-APP-000231-WSR-000144 | CAT II | C | Information at rest must be encrypted using a DOD-accepted algorithm to... | indexes.conf [volume:<volume_name>] remote.s3.encryption,... |
| SRG-APP-000233-WSR-000146 | CAT II | C | The web server document directory must be in a separate partition from the web... | splunk-launch.conf SPLUNK_DB; indexes.conf homePath, coldPath, thawedPath,... |
| SRG-APP-000246-WSR-000149 | CAT II | C | The web server must restrict the ability of users to launch Denial of Service... | alert_actions.conf [webhook] enable_allowlist, allowlist.<name>;... |
| SRG-APP-000251-WSR-000157 | CAT II | C | The web server must limit the character set used for data entry. | web.conf [settings] tools.decode.on, tools.encode.on, tools.encode.encoding,... |
| SRG-APP-000251-WSR-000194 | CAT II | C | The web server must interpret and normalize ambiguous HTTP requests or... | web.conf [settings] forceHttp10, max_upload_size, tools.proxy.on,... |
| SRG-APP-000266-WSR-000142 | CAT II | C | The web server must display a default hosted application web page, not a... | web.conf [settings] tools.staticdir.generate_indexes; scoping and supporting... |
| SRG-APP-000266-WSR-000159 | CAT II | C | Warning and error messages displayed to clients must be modified to minimize... | web.conf [settings] simple_error_page, request.show_tracebacks,... |
| SRG-APP-000266-WSR-000160 | CAT II | C | Debugging and trace information used to diagnose the web server must be... | web.conf [settings] enableWebDebug, request.show_tracebacks, js_logger_mode,... |
| SRG-APP-000295-AU-000190 | CAT II | C | The Central Log Server must automatically terminate a user session after... | web.conf [settings]: tools.sessions.timeout, ui_inactivity_timeout;... |
| SRG-APP-000295-WSR-000012 | CAT II | C | The web server must set an absolute session timeout value of eight hours or... | server.conf [general]: sessionTimeout; web.conf [settings]:... |
| SRG-APP-000295-WSR-000134 | CAT II | C | The web server must set an inactive timeout for sessions. | web.conf [settings]: tools.sessions.timeout, ui_inactivity_timeout |
| SRG-APP-000296-AU-000560 | CAT II | C | The Central Log Server must provide a logout capability for user initiated... | server.conf [general]: invalidateSessionTokensOnLogout,... |
| SRG-APP-000315-WSR-000003 | CAT II | C | Remote access to the web server must follow access policy or work in... | web.conf [settings]: enableSplunkWebSSL, privKeyPath, serverCert,... |
| SRG-APP-000315-WSR-000004 | CAT II | C | The web server must restrict inbound connections from nonsecure zones. | web.conf [settings]: acceptFrom; server.conf [httpServer]: acceptFrom;... |
| SRG-APP-000316-WSR-000170 | CAT II | C | The web server must provide the capability to immediately disconnect or... | web.conf [settings]: startwebserver, httpport, acceptFrom; server.conf... |
| SRG-APP-000334-WSR-000024 | CAT II | C | The web server must uniquely identify and authenticate source by organization,... | inputs.conf [splunktcp-ssl:<port>] and [SSL]: serverCert, sslPassword,... |
| SRG-APP-000340-WSR-000029 | CAT II | C | Non-privileged accounts on the hosting system must only access web server... | authorize.conf [role_<roleName>]: capability assignments, importRoles,... |
| SRG-APP-000345-AU-000400 | CAT II | C | The Central Log Server must automatically lock the account until the locked... | authentication.conf [splunk_auth]: lockoutUsers, lockoutAttempts,... |
| SRG-APP-000357-WSR-000150 | CAT II | C | The web server must use a logging mechanism that is configured to allocate log... | web.conf [settings] log.access_maxsize, log.access_maxfiles,... |
| SRG-APP-000358-AU-000100 | CAT II | C | The Central Log Server must be configured to off-load log records onto a... | outputs.conf [tcpout] and [tcpout:<target_group>] server, and... |
| SRG-APP-000358-WSR-000063 | CAT II | C | The web server must not impede the ability to write specified log record... | outputs.conf [tcpout:<target_group>] server and [syslog:<target_group>]... |
| SRG-APP-000358-WSR-000163 | CAT II | C | The web server must be configurable to integrate with an organizations... | outputs.conf [tcpout:<target_group>] and [syslog:<target_group>] for record... |
| SRG-APP-000359-WSR-000065 | CAT II | C | The web server must use a logging mechanism that is configured to provide a... | server.conf [diskUsage] minFreeSpace with health.conf [feature:disk_space]... |
| SRG-APP-000364-AU-000190 | CAT II | C | The Central Log Server must be configured to perform audit reduction that... | savedsearches.conf auto_summarize with auto_summarize.timespan and... |
| SRG-APP-000374-WSR-000172 | CAT II | C | The web server must generate log records that can be mapped to Coordinated... | web.conf [settings] log.access_file; splunk-launch.conf process environment;... |
| SRG-APP-000375-WSR-000171 | CAT II | C | The web server must record time stamps for log records to a minimum... | web.conf [settings] log.access_file; props.conf [splunk_web_access]... |
| SRG-APP-000380-WSR-000072 | CAT II | C | The web server application, libraries, and configuration files must only be... | authorize.conf [role_<roleName>] with importRoles, and... |
| SRG-APP-000383-WSR-000175 | CAT II | C | The web server must prohibit or restrict the use of nonsecure or unnecessary... | web.conf [settings] startwebserver, httpport, enableSplunkWebSSL; server.conf... |
| SRG-APP-000391-AU-002290 | CAT II | C | The Central Log Server must be configured to accept the DoW common access card... | web.conf [settings]: enableCertBasedUserAuth, requireClientCert,... |
| SRG-APP-000392-AU-002300 | CAT II | C | The Central Log Server must be configured to electronically verify the DoW... | web.conf [settings]: requireClientCert, sslRootCAPath,... |
| SRG-APP-000416-WSR-000118 | CAT II | C | The web server must implement required cryptographic protections using... | splunk-launch.conf SPLUNK_FIPS; server.conf [sslConfig] cipherSuite,... |
| SRG-APP-000427-AU-000040 | CAT II | C | The Central Log Server must only allow the use of DoW Public Key... | server.conf [sslConfig] sslRootCAPath, caCertFile, serverCert,... |
| SRG-APP-000427-WSR-000186 | CAT II | C | The web server must only accept client certificates (user and machine) issued... | web.conf [settings] requireClientCert, enableCertBasedUserAuth,... |
| SRG-APP-000435-WSR-000147 | CAT II | C | The web server must be protected from being stopped by a non-privileged user. | authorize.conf, [capability::restart_splunkd] and [capability::edit_server],... |
| SRG-APP-000435-WSR-000148 | CAT II | C | The web server must be tuned to handle the operational requirements of the... | web.conf [settings] maxThreads, maxSockets; server.conf [httpServer]... |
| SRG-APP-000439-WSR-000152 | CAT II | C | Web server session IDs must be sent to the client using SSL/TLS. | web.conf [settings] enableSplunkWebSSL, tools.sessions.secure,... |
| SRG-APP-000439-WSR-000153 | CAT II | C | Web server cookies, such as session cookies, sent to the client using SSL/TLS... | web.conf [settings] allowSslCompression and enable_gzip; server.conf... |
| SRG-APP-000439-WSR-000154 | CAT II | C | Cookies exchanged between the web server and the client, such as session... | web.conf [settings] tools.sessions.httponly; server.conf [httpServer]... |
| SRG-APP-000439-WSR-000155 | CAT II | C | Cookies exchanged between the web server and the client, such as session... | web.conf [settings] tools.sessions.secure, tools.sessions.forceSecure,... |
| SRG-APP-000439-WSR-000156 | CAT II | C | A web server must maintain the confidentiality of controlled information... | web.conf [settings] sslVersions; server.conf [sslConfig] sslVersions and... |
| SRG-APP-000439-WSR-000188 | CAT II | C | The web server must remove all export ciphers to protect the confidentiality... | server.conf [sslConfig] cipherSuite, ecdhCurves, dhFile; web.conf [settings]... |
| SRG-APP-000439-WSR-000192 | CAT II | C | The web server must use HTTP/2, at a minimum. | web.conf [settings] forceHttp10 (web.conf.spec:1129), server.conf [httpServer]... |
| SRG-APP-000439-WSR-000193 | CAT II | C | The web server must disable HTTP/1.x downgrading. | web.conf [expose:<unique_name>] allowRemoteProxy (web.conf.spec:1545) and... |
| SRG-APP-000439-WSR-000196 | CAT II | C | The web server must only use forward proxies that route HTTP/2 requests... | server.conf [proxyConfig] http_proxy (server.conf.spec:1206), https_proxy... |
| SRG-APP-000441-WSR-000181 | CAT II | C | The web server must maintain the confidentiality and integrity of information... | outputs.conf [tcpout:<group>] clientCert, sslPassword, sslVersions,... |
| SRG-APP-000442-WSR-000182 | CAT II | C | The web server must maintain the confidentiality and integrity of information... | inputs.conf [splunktcp-ssl:<port>], [tcp-ssl:<port>] and [SSL] serverCert,... |
| SRG-APP-000503-AU-000280 | CAT II | C | The Central Log Server must generate audit records when... | audit.conf [auditTrail] queueing, logging_format; audit.conf... |
| SRG-APP-000516-AU-000330 | CAT II | C | The Central Log Server must be configured to retain the identity of the... | inputs.conf connection_host = [ip ... |
| SRG-APP-000516-AU-000340 | CAT II | C | The Central Log Server that aggregates log records from hosts and devices must... | inputs.conf [splunktcp], [splunktcp://[<remote server>]:<port>],... |
| SRG-APP-000516-AU-000350 | CAT II | C | The Central Log Server must be configured to notify the System Administrator... | savedsearches.conf enableSched, cron_schedule, counttype, alert_condition,... |
| SRG-APP-000516-AU-000360 | CAT II | C | The Central Log Server must be configured to automatically create trouble... | savedsearches.conf action.<action_name> and action.<action_name>.<parameter>,... |
| SRG-APP-000516-AU-000370 | CAT II | C | For devices and hosts within the scope of coverage, the Central Log Server... | props.conf TRANSFORMS-<class> paired with transforms.conf DEST_KEY = queue and... |
| SRG-APP-000516-AU-000380 | CAT II | C | The Central Log Server must be configured with the organization-defined... | savedsearches.conf alert.severity; props.conf EVAL-<fieldname>,... |
| SRG-APP-000516-AU-000410 | CAT II | C | Analysis, viewing, and indexing functions, services, and applications used as... | web.conf [settings] enableSplunkWebSSL, privKeyPath, serverCert; server.conf... |
| SRG-APP-000516-WSR-000079 | CAT II | C | All accounts installed with the web server software and tools must have... | user-seed.conf [user_info] USERNAME, PASSWORD, HASHED_PASSWORD;... |
| SRG-APP-000516-WSR-000174 | CAT II | C | The web server must be configured in accordance with the security... | The product's layered configuration surface in aggregate - server.conf,... |
| SRG-APP-000700-WSR-000100 | CAT II | C | The web server must disable accounts when the accounts have expired. | server.conf [teleport_supervisor] disabled; web-features.conf... |
| SRG-APP-000705-AU-000110 | CAT II | C | The Central Log Server must disable accounts when the accounts are no longer... | server.conf [teleport_supervisor] disabled; web-features.conf... |
| SRG-APP-000705-WSR-000110 | CAT II | C | The web server must disable accounts when the accounts are no longer... | web-features.conf [feature:identity_sidecar_scim] enabled for the web tier;... |
| SRG-APP-000745-AU-000120 | CAT II | C | The Central Log Server must implement the capability to centrally review and... | inputs.conf [splunktcp], [splunktcp-ssl:<port>], [http]; distsearch.conf... |
| SRG-APP-000745-WSR-000120 | CAT II | C | The web server must implement the capability to centrally review and analyze... | web.conf [settings] startwebserver; distsearch.conf [distributedSearch]... |
| SRG-APP-000750-AU-000130 | CAT II | C | The Central Log Server must implement an audit reduction capability that... | props.conf [<source type>] REPORT-<class>, EXTRACT-<class>,... |
| SRG-APP-000755-AU-000140 | CAT II | C | The Central Log Server must implement an audit reduction capability that... | props.conf REPORT-<class>, LOOKUP-<class>; macros.conf definition;... |
| SRG-APP-000760-AU-000150 | CAT II | C | The Central Log Server must implement an audit reduction capability that... | props.conf REPORT-<class>, EXTRACT-<class>, LOOKUP-<class>; indexes.conf... |
| SRG-APP-000765-AU-000160 | CAT II | C | The Central Log Server must implement a report generation capability that... | savedsearches.conf [<stanza name>] search, dispatch.earliest_time,... |
| SRG-APP-000770-AU-000170 | CAT II | C | The Central Log Server must implement a report generation capability that... | savedsearches.conf [<stanza name>] enableSched, cron_schedule,... |
| SRG-APP-000775-AU-000180 | CAT II | C | The Central Log Server must implement a report generation capability that... | savedsearches.conf [<stanza name>] search, dispatch.earliest_time,... |
| SRG-APP-000780-AU-000190 | CAT II | C | The Central Log Server must implement an audit reduction capability that does... | props.conf SEDCMD-<class> and TRANSFORMS-<class>; transforms.conf DEST_KEY =... |
| SRG-APP-000785-AU-000200 | CAT II | C | The Central Log Server must implement a report generation capability that does... | savedsearches.conf [<stanza name>] search; props.conf SEDCMD-<class>,... |
| SRG-APP-000790-AU-000210 | CAT II | C | The Central Log Server must implement the capability to process, sort, and... | props.conf EXTRACT-<class>, REPORT-<class>, FIELDALIAS-<class>,... |
| SRG-APP-000795-AU-000220 | CAT II | C | The Central Log Server must alert organization-defined personnel or roles upon... | savedsearches.conf [<stanza name>] search, alert_condition, counttype,... |
| SRG-APP-000795-WSR-000130 | CAT II | C | The web server must alert organization-defined personnel or roles upon... | savedsearches.conf [<stanza name>] alert_condition, action.email,... |
| SRG-APP-000800-AU-000230 | CAT II | C | The Central Log Server must implement the capability for organization-defined... | audit.conf [auditconfig:/path] enabled, disabled, sampling.<action>;... |
| SRG-APP-000805-AU-000240 | CAT II | C | The Central Log Server must automatically generate audit records of the... | server.conf [config_change_tracker] disabled, mode = [auto ... |
| SRG-APP-000805-WSR-000140 | CAT II | C | The web server must automatically generate audit records of the enforcement... | server.conf [config_change_tracker] disabled, mode = [auto ... |
| SRG-APP-000810-AU-000250 | CAT II | C | The Central Log Server must prevent the installation of organization-defined... | authorize.conf [capability::install_apps], [capability::edit_local_apps],... |
| SRG-APP-000815-AU-000260 | CAT II | C | The Central Log Server must require users to be individually authenticated... | authentication.conf [authentication]: authType; authorize.conf... |
| SRG-APP-000815-WSR-000160 | CAT II | C | The web server must require users to be individually authenticated before... | web.conf [settings]: tools.sessions.*; authentication.conf [authentication]:... |
| SRG-APP-000820-WSR-000170 | CAT II | C | The web server must implement multifactor authentication for local; network;... | authentication.conf [authentication]: externalTwoFactorAuthVendor,... |
| SRG-APP-000825-AU-000280 | CAT II | C | The Central Log Server must implement multifactor authentication for local;... | authentication.conf [authentication]: externalTwoFactorAuthVendor,... |
| SRG-APP-000825-WSR-000180 | CAT II | C | The web server must implement multifactor authentication for local; network;... | web.conf [settings]: enableCertBasedUserAuth, requireClientCert,... |
| SRG-APP-000845-AU-000320 | CAT II | C | The Central Log Server must for password-based authentication, verify when... | authentication.conf [splunk_auth]: enablePasswordHistory,... |
| SRG-APP-000845-WSR-000220 | CAT II | C | The web server must, for password-based authentication, verify when users... | authentication.conf [splunk_auth]: enablePasswordHistory,... |
| SRG-APP-000850-WSR-000230 | CAT II | C | The web server must, for password-based authentication, store passwords using... | authentication.conf [authentication]: passwordHashAlgorithm |
| SRG-APP-000860-AU-000350 | CAT II | C | The Central Log Server must for password-based authentication, allow user... | authentication.conf [splunk_auth]: minPasswordLength |
| SRG-APP-000860-WSR-000250 | CAT II | C | The web server must, for password-based authentication, allow user selection... | authentication.conf [splunk_auth]: minPasswordLength |
| SRG-APP-000870-WSR-000270 | CAT II | C | The web server must, for password-based authentication, enforce... | authentication.conf [splunk_auth]: minPasswordLength, minPasswordUppercase,... |
| SRG-APP-000875-AU-000380 | CAT II | C | The Central Log Server must for public key-based authentication, implement a... | server.conf [sslConfig]: certificateStatusValidationMethod; server.conf... |
| SRG-APP-000875-WSR-000280 | CAT II | C | The web server must, for public key-based authentication, implement a local... | server.conf [sslConfig]: certificateStatusValidationMethod; web.conf... |
| SRG-APP-000880-WSR-000290 | CAT II | C | The web server must protect nonlocal maintenance sessions by separating the... | web.conf [settings]: mgmtHostPort, httpport, enableSplunkWebSSL,... |
| SRG-APP-000910-AU-000390 | CAT II | C | The Central Log Server must include only approved trust anchors in trust... | server.conf [sslConfig] sslRootCAPath, caTrustStore, caTrustStorePath,... |
| SRG-APP-000910-WSR-000300 | CAT II | C | The web server must include only approved trust anchors in trust stores or... | web.conf [settings] sslRootCAPath, requireClientCert; server.conf [sslConfig]... |
| SRG-APP-000915-AU-000400 | CAT II | C | The Central Log Server must provide protected storage for cryptographic keys... | server.conf [sslConfig] serverCert, sslPassword, sslRootCAPath; inputs.conf... |
| SRG-APP-000915-WSR-000310 | CAT II | C | The web server must provide protected storage for cryptographic keys with... | web.conf [settings] privKeyPath, serverCert, sslPassword |
| SRG-APP-000920-AU-000410 | CAT II | C | The Central Log Server must synchronize system clocks within and between... | limits.conf [search] max_tolerable_skew (limits.conf.spec:529) and... |
| SRG-APP-000920-WSR-000320 | CAT II | C | The web server must synchronize system clocks within and between systems or... | limits.conf [search] max_tolerable_skew (limits.conf.spec:529) and... |
| SRG-APP-000925-AU-000420 | CAT II | C | The Central Log Server must compare the internal system clocks on an... | limits.conf [search] max_tolerable_skew (limits.conf.spec:529) and... |
| SRG-APP-000925-WSR-000330 | CAT II | C | The web server must compare the internal system clocks on an... | limits.conf [search] max_tolerable_skew (limits.conf.spec:529) and... |
| SRG-APP-000068-AU-000035 | CAT III | C | The Central Log Server must display the Standard Mandatory DoW Notice and... | web.conf [settings] login_content |
| SRG-APP-000069-AU-000420 | CAT III | C | The Central Log Server must retain the Standard Mandatory DoW Notice and... | web.conf [settings] login_content |
| SRG-APP-000086-AU-000020 | CAT III | C | The Central Log Server must be configured to aggregate log records from... | inputs.conf receiving stanzas [splunktcp], [splunktcp://[<remote... |
| SRG-APP-000086-AU-000030 | CAT III | C | Time stamps recorded on the log records in the Central Log Server must be... | props.conf [<spec>] DATETIME_CONFIG, TZ, TZ_ALIAS, TIME_PREFIX, TIME_FORMAT,... |
| SRG-APP-000090-AU-000070 | CAT III | C | The Central Log Server must be configured to allow only the Information System... | authorize.conf [role_<roleName>] with <capability> = enabled, restricting... |
| SRG-APP-000092-AU-000670 | CAT III | C | The Central Log Server must initiate session auditing upon startup. | audit.conf [auditTrail] queueing and logging_format; audit.conf... |
| SRG-APP-000095-AU-000050 | CAT III | C | The System Administrator (SA) and Information System Security Manager (ISSM)... | indexes.conf per-index frozenTimePeriodInSecs, maxTotalDataSizeMB,... |
| SRG-APP-000095-AU-000680 | CAT III | C | The Central Log Server must produce audit records containing information to... | audit.conf [auditTrail] logging_format and [auditconfig:/path] enabled /... |
| SRG-APP-000096-AU-000690 | CAT III | C | The Central Log Server must produce audit records containing information to... | props.conf per-sourcetype DATETIME_CONFIG, TIME_PREFIX,... |
| SRG-APP-000097-AU-000700 | CAT III | C | The Central Log Server must produce audit records containing information to... | inputs.conf per-stanza host, index, sourcetype, host_regex, host_segment;... |
| SRG-APP-000098-AU-000710 | CAT III | C | The Central Log Server must produce audit records containing information to... | inputs.conf per-input connection_host (ip, dns, none; and proxied_ip on the... |
| SRG-APP-000099-AU-000720 | CAT III | C | The Central Log Server must produce audit records that contain information to... | audit.conf [auditTrail] logging_format and [auditconfig:/path] enabled /... |
| SRG-APP-000100-AU-000730 | CAT III | C | The Central Log Server must generate audit records containing information that... | audit.conf [auditTrail] queueing and logging_format; authorize.conf... |
| SRG-APP-000111-AU-000150 | CAT III | C | The Central Log Server must be configured to perform analysis of log records... | distsearch.conf [distributedSearch] servers and... |
| SRG-APP-000115-AU-000160 | CAT III | C | The Central Log Server must be configured to perform on-demand filtering of... | savedsearches.conf [<stanza name>] search and counttype; eventtypes.conf... |
| SRG-APP-000116-AU-000270 | CAT III | C | The Central Log Server must be configured to use internal system clocks to... | props.conf [<source type>] DATETIME_CONFIG (value CURRENT), with TIME_FORMAT... |
| SRG-APP-000125-AU-000300 | CAT III | C | The Central Log Server must be configured to back up the log records... | indexes.conf remotePath, coldToFrozenDir, coldToFrozenScript and... |
| SRG-APP-000166-AU-002490 | CAT III | C | The Central Log Server must be configured to enforce password complexity by... | authentication.conf [splunk_auth] minPasswordUppercase |
| SRG-APP-000167-AU-002500 | CAT III | C | The Central Log Server must be configured to enforce password complexity by... | authentication.conf [splunk_auth] minPasswordLowercase |
| SRG-APP-000168-AU-002510 | CAT III | C | The Central Log Server must be configured to enforce password complexity by... | authentication.conf [splunk_auth] minPasswordDigit |
| SRG-APP-000169-AU-002520 | CAT III | C | The Central Log Server must be configured to enforce password complexity by... | authentication.conf [splunk_auth] minPasswordSpecial |
| SRG-APP-000170-AU-002530 | CAT III | C | The Central Log Server must be configured to require the change of at least... | authentication.conf, [splunk_auth]: minPasswordLength, minPasswordUppercase,... |
| SRG-APP-000173-AU-002560 | CAT III | C | The Central Log Server must be configured to enforce 24 hours/1 day as the... | authentication.conf, [splunk_auth]: expirePasswordDays governs native password... |
| SRG-APP-000174-AU-002570 | CAT III | C | The Central Log Server must be configured to enforce a 180-day maximum... | authentication.conf [splunk_auth] expirePasswordDays, expireUserAccounts |
| SRG-APP-000177-AU-002650 | CAT III | C | The Central Log Server must map the authenticated identity to the individual... | web.conf [settings] certBasedUserAuthMethod, certBasedUserAuthPivOidList;... |
| SRG-APP-000291-AU-000200 | CAT III | C | The Central Log Server must notify system administrators and ISSO when... | savedsearches.conf [<search name>] enableSched, cron_schedule, counttype or... |
| SRG-APP-000292-AU-000420 | CAT III | C | For devices and hosts within its scope of coverage, the Central Log Server... | savedsearches.conf [<search name>] enableSched, cron_schedule,... |
| SRG-APP-000293-AU-000430 | CAT III | C | For devices and hosts within its scope of coverage, the Central Log Server... | savedsearches.conf [<search_name>]: enableSched, cron_schedule,... |
| SRG-APP-000294-AU-000440 | CAT III | C | For devices and hosts within its scope of coverage, the Central Log Server... | savedsearches.conf [<search_name>]: enableSched, cron_schedule,... |
| SRG-APP-000297-AU-000570 | CAT III | C | The Central Log Server must display an explicit logout message to users... | messages.conf [<component>:<key>]: message, action, target (overriding the... |
| SRG-APP-000359-AU-000120 | CAT III | C | The Central Log Server must be configured to send an immediate alert to the... | server.conf [diskUsage] minFreeSpace sets the threshold; health.conf... |
| SRG-APP-000360-AU-000130 | CAT III | C | For the host and devices within its scope of coverage, the Central Log Server... | savedsearches.conf [<stanza name>] search with realtime_schedule,... |
| SRG-APP-000362-AU-000170 | CAT III | C | The Central Log Server must be configured to perform on-demand sorting of log... | savedsearches.conf [<stanza name>] search carrying the sort expression with... |
| SRG-APP-000363-AU-000180 | CAT III | C | The Central Log Server must be configured to perform on-demand searches of log... | authorize.conf [capability::search] with [role_<roleName>] srchIndexesDefault... |
| SRG-APP-000365-AU-000210 | CAT III | C | The Central Log Server must be configured to perform audit reduction that... | indexes.conf frozenTimePeriodInSecs with coldToFrozenDir or coldToFrozenScript... |
| SRG-APP-000366-AU-000220 | CAT III | C | The Central Log Server must be configured to generate on-demand audit review... | savedsearches.conf [<stanza name>] search, dispatch.earliest_time,... |
| SRG-APP-000367-AU-000230 | CAT III | C | The Central Log Server must be configured to generate reports that support... | savedsearches.conf [<stanza name>] search, enableSched, cron_schedule,... |
| SRG-APP-000368-AU-000240 | CAT III | C | The Central Log Server must be configured to generate reports that support... | savedsearches.conf [<stanza name>] search, dispatch.earliest_time,... |
| SRG-APP-000369-AU-000250 | CAT III | C | The Central Log Server must be configured to perform audit reduction that does... | props.conf REPORT-<class>, EXTRACT-<class> (search-time, non-altering);... |
| SRG-APP-000370-AU-000260 | CAT III | C | The Central Log Server must be configured to generate reports that do not... | savedsearches.conf [<stanza name>] search; field_filters.conf... |
| SRG-APP-000374-AU-000290 | CAT III | C | Upon receipt of the log record from hosts and devices, the Central Log Server... | props.conf [<source type>] DATETIME_CONFIG, TIME_FORMAT, TZ, TZ_ALIAS;... |
| SRG-APP-000375-AU-000280 | CAT III | C | The Central Log Server must be configured to record time stamps for when log... | props.conf [<source type>] TIME_FORMAT, ADD_EXTRA_TIME_FIELDS |
| SRG-APP-000389-AU-000180 | CAT III | C | The Central Log Server must require users to reauthenticate when... | web.conf [settings] tools.sessions.timeout, ui_inactivity_timeout,... |
| SRG-APP-000515-AU-000110 | CAT III | C | The Central Log Server must be configured to off-load interconnected systems... | outputs.conf [tcpout], [tcpout:<target_group>] server; indexes.conf [<index>]... |
| SRG-APP-000516-AU-000060 | CAT III | C | The Central Log Server must be configured so changes made to the level and... | app.conf [triggers] reload.<conf_file_name>,... |

\newpage

## Applicable, satisfied by documented procedure

In scope, but not implemented by configuration. Each requires an artifact, and that artifact is the evidence an assessor retrieves.

| Requirement | Severity | Artifact that satisfies it |
|---|---|---|
| SRG-APP-000456-AU-000270 | CAT I | The organization's flaw remediation procedure for Splunk Enterprise, naming the... |
| SRG-APP-001035-AU-000430 | CAT I | Current Splunk Enterprise software maintenance and support entitlement, together with... |
| SRG-APP-001035-WSR-000340 | CAT I | Current Splunk Enterprise software maintenance and support entitlement covering the... |
| SRG-APP-000131-WSR-000073 | CAT II | Documented app and add-on review, test and approval record for each Splunk app or... |
| SRG-APP-000456-WSR-000187 | CAT II | The organization's flaw remediation procedure covering the Splunk Web component of... |
| SRG-APP-000830-AU-000290 | CAT II | The organization's list of commonly used, expected and compromised passwords, with its... |
| SRG-APP-000830-WSR-000190 | CAT II | The organization's list of commonly used, expected and compromised passwords, with its... |
| SRG-APP-000835-AU-000300 | CAT II | The password deny list's revision history and review record, showing updates at the... |
| SRG-APP-000835-WSR-000200 | CAT II | The password deny list's revision history and review record, showing updates at the... |
| SRG-APP-000840-AU-000310 | CAT II | The procedure tying password deny list revision to the incident response plan, with... |
| SRG-APP-000840-WSR-000210 | CAT II | The procedure tying password deny list revision to the incident response plan, with... |
| SRG-APP-000855-AU-000340 | CAT II | The account management and password reset procedure, specifying issuance of a... |
| SRG-APP-000855-WSR-000240 | CAT II | The account management and password reset procedure, specifying issuance of a... |
| SRG-APP-000865-AU-000360 | CAT II | The organization-approved password or passphrase generation tool and the procedure... |
| SRG-APP-000865-WSR-000260 | CAT II | The organization-approved password or passphrase generation tool and the procedure... |
| SRG-APP-000125-AU-000310 | CAT III | The System Security Plan entry recording the log-record retention period and the SAMI... |

\newpage

## Undetermined

Applicability could not be established. Each row names the probe that would settle it. Recorded as undetermined rather than defaulted to any disposition.

| Requirement | Severity | Grade | Justification |
|---|---|---|---|
| SRG-APP-000251-WSR-000195 | CAT II | E | This requirement concerns the behavior of the HTTP server when an exception is raised... |

\newpage

## Determinations revised on independent challenge

Each of the following was first determined Not Applicable or implemented outside the application boundary, and was revised when challenged. They are recorded because a revised determination marks where the original reading was not supportable, and an Authorizing Official reviewing this matrix is entitled to see it.

| Requirement | Revised to | Grade |
|---|---|---|
| SRG-APP-000163-AU-002470 | Applicable | C |
| SRG-APP-000700-WSR-000100 | Applicable | C |
| SRG-APP-000705-AU-000110 | Applicable | C |
| SRG-APP-000705-WSR-000110 | Applicable | C |
| SRG-APP-000170-AU-002530 | Applicable | C |
| SRG-APP-000173-AU-002560 | Applicable | C |
| SRG-APP-000176-WSR-000096 | Applicable | C |
| SRG-APP-000086-AU-000030 | Applicable | C |
| SRG-APP-000141-WSR-000085 | Applicable | C |
| SRG-APP-000439-WSR-000192 | Applicable | C |
| SRG-APP-000439-WSR-000193 | Applicable | C |
| SRG-APP-000439-WSR-000196 | Applicable | C |
| SRG-APP-000920-AU-000410 | Applicable | C |
| SRG-APP-000920-WSR-000320 | Applicable | C |
| SRG-APP-000925-AU-000420 | Applicable | C |
| SRG-APP-000925-WSR-000330 | Applicable | C |
| SRG-APP-000219-WSR-000190 | Applicable | C |
| SRG-APP-000219-WSR-000191 | Applicable | C |

**SRG-APP-000163-AU-002470.** The OUTSIDE_BOUNDARY determination fails on three independent grounds. First, the benchmark scopes its own remediation to the application's local accounts: the fix text reads "For local accounts (except for the account of last resort), configure the Central Log Server to disable accounts (individuals, groups, roles, and devices) after 35 days of inactivity." A directory service or SAML identity provider does not hold the accounts in the Splunk native account store, so the named provider cannot discharge a requirement whose remediation is directed at local accounts. The native store persists under every authentication binding - authType accepts Splunk, LDAP, Scripted, SAML and ProxySSO (authentication.conf.spec:30), the [splunk_auth] stanza (authentication.conf.spec:458) is independent of any external binding, and authTypePreferredForUserCollision exists precisely because native accounts coexist with identity-provider accounts - so local accounts are present at every site and the requirement follows them into the application boundary. Second, the prior basis made applicability conditional on a site's binding choice, conceding that where a site relies on native local accounts "there is no mechanism." A disposition asserting that the Splunk team owes nothing cannot rest on a basis conceding it may owe everything; applicability is a property of the product and the requirement, not of one site's authentication selection. Third, the capability claim is unsound. Splunk Enterprise 10.4.2 exposes inbound automated user management over SCIM - the configuration path by which an identity provider that detects account inactivity applies deactivation or removal to the account held by the Splunk instance. That mechanism is present in the specification set the prior assessor searched and the search missed it, because the search enumerated invented setting names rather than the capability. The implementation is shared: the identity provider makes the inactivity determination, and the Splunk application owes the configuration of the provisioning path that applies it, which is work inside the boundary. The native account store exposes no inactivity timer - expirePasswordDays (authentication.conf.spec:508) and expireUserAccounts (authentication.conf.spec:525) govern password expiry, which the prior assessor had right - and the SCIM integration is bounded to the identity-provider domains named by scimSupportedDomains (authentication.conf.spec:95), a setting the specification instructs the operator not to modify. Those are capability limits to be recorded against the requirement and tested against an instance later; they are not grounds to move the requirement outside the application boundary.

**SRG-APP-000700-WSR-000100.** The prior determination rests on two claims, and neither holds. First, it places the account objects with an external provider. Splunk Enterprise is its own authentication authority by default and maintains its own account store: authentication.conf authType accepts Splunk and defaults to Splunk, [splunk_auth] is described in the specification as Splunk's internal authentication system, passwordHashAlgorithm governs how hashed passwords are written to the product's own passwd file, and authTypePreferredForUserCollision exists specifically to resolve username collisions between native authentication users and SAML users, which establishes that native accounts persist alongside provider accounts rather than being displaced by them. A providing baseline that does not hold all accounts in scope cannot carry the control, so grade D fails on its own terms. Second, the claim that the product exposes no mechanism keyed to account expiry is contradicted by the specification set. Splunk Enterprise 10.4.2 implements the service-provider side of System for Cross-Domain Identity Management, the protocol by which an identity provider applies account expiration and deactivation to the account objects a service holds: splunkd launches a supervisor process that handles authorization tokens for SCIM operations, Splunk Web exposes Automated User Management controls for SCIM, and the authentication configuration carries a SCIM provider domain allowlist together with a boolean governing synchronization of user deletions. The expiration decision may originate with an identity provider, but this requirement directs that the Splunk instance disable the account, and the mechanism that applies disablement to the Splunk account object is the application's own configuration. The requirement is therefore APPLICABLE and its result is obtained from the application. The prior evidence is additionally defective in method: the specification set contains 71 specification files, not 128 (that count includes 56 example configuration files and one XML file shipped beside them), and two account lifecycle settings resolve in authentication.conf on a 10.4.2 instance while appearing in no specification file, so a search over a guessed term list cannot establish capability absence. The prior reading of expireUserAccounts as password expiration is correct and is retained; it is not the only relevant mechanism.

**SRG-APP-000705-AU-000110.** The prior determination asserts that the product exposes no de-association trigger anywhere in its configuration surface, and the specification set contradicts this twice over. First, Splunk Enterprise 10.4.2 implements the service-provider side of System for Cross-Domain Identity Management, which is the protocol an identity provider uses to deactivate and delete the account objects a service holds when the holder departs or the account no longer maps to an individual: splunkd launches a supervisor process handling authorization tokens for SCIM operations, Splunk Web exposes Automated User Management controls for SCIM, and the authentication configuration carries a SCIM provider domain allowlist together with a boolean governing synchronization of user deletions. Second, the prior evidence cites the orphaned scheduled search check as proof of absence, but the specification text it cites describes the product recognizing exactly the de-association condition this requirement names: the check exists for the case where a user creates scheduled searches and then departs the organization, causing that account to be deactivated, and the product raises an administrative notification on a recurring basis as a result. That is a configurable application mechanism keyed to the de-association condition, not evidence of its absence. The check notifies rather than disables, so it does not satisfy the requirement on its own, but it defeats the claim on which the prior grade rests. The boundary claim fails independently: the application maintains its own account store and is its own authentication authority by default, so the named provider does not hold all accounts in scope and cannot carry the control.

**SRG-APP-000705-WSR-000110.** The prior determination delegates twice, and the first hop never leaves the application. Splunk Web authenticating users through splunkd is delegation between two components of the same product under assessment, so citing the management endpoint that Splunk Web uses to reach splunkd does not place the requirement outside the application boundary; it relocates the requirement within that boundary. The second hop then fails for the same reason it fails for the application as a whole: the product is its own authentication authority by default and maintains its own account store, so the named identity provider does not hold all accounts in scope. The claim that the configuration surface contains no account de-association trigger at either tier is also incorrect, and the web tier is where the clearest counter-evidence sits: web-features.conf defines the Automated User Management controls for System for Cross-Domain Identity Management, the protocol by which an identity provider deactivates and deletes the account objects a service holds. SCIM is supported on the splunkd side by a supervisor process that handles its authorization tokens and by a SCIM provider domain allowlist and a user-deletion synchronization setting in the authentication configuration. Both tiers of the application therefore carry configuration that bears on account de-association, and the requirement is APPLICABLE.

**SRG-APP-000170-AU-002530.** The inheritance fails on two independent grounds. First, DISA's own product-specific implementation for this requirement's CCI places it inside the application. The six rules this requirement carries as references (SPLK-CL-000340, 000350, 000360, 000370, 000380 and 000400) all direct password policy into authentication.conf under [splunk_auth], and they appear in the same sunsetted STIG whose SPLK-CL-000320 directs LDAP or SAML. In that STIG, directory delegation and native password-policy hardening are concurrent obligations, not alternatives, so CCI-004066 was never treated as inherited from the directory service. Second, the prior determination concedes in its own basis a residual that its named provider does not reach: the account of last resort, which SPLK-CL-000320 expressly preserves in native authentication. A control whose supporting rationale states that the provider does not cover part of the scope is a partially implemented control, not an inherited one, and the product always retains the native realm that holds it. Splunk exposes a password composition and history surface in [splunk_auth], and the selection of an external provider is itself made through an application setting (authType), so the requirement applies to the application. The absence of a key that counts changed character positions is real and my own search confirms it, but that makes the character-difference element an expected Other Than Satisfied result against an applicable requirement. Inability to meet a requirement is a finding to be carried as a risk decision, not a boundary question, and OUTSIDE_BOUNDARY on this row would tell an AO that no native password policy review is owed.

**SRG-APP-000173-AU-002560.** The capability finding is correct and my own search reproduces it: the specification set contains no minimum password age or minimum lifetime key, and expirePasswordDays is a ceiling only. The boundary conclusion drawn from it does not survive. This requirement carries the same CCI and the same six product STIG references as the character-difference requirement, including SPLK-CL-000400, which sets password lifetime through authentication.conf [splunk_auth]; DISA therefore placed password lifetime for this CCI inside the application rather than inheriting it from the directory service. The prior determination also concedes the same uncovered residual, the account of last resort that SPLK-CL-000320 preserves in native authentication, which the named LDAP or SAML provider does not reach and cannot be made to reach. An inheritance that the assessor's own basis says is incomplete is a finding, not an inheritance. The requirement addresses the application's native password lifetime surface, that surface is configured in authentication.conf, and the path by which an organization-selected handler could enforce a 24-hour floor is itself an application setting (authType, including the Scripted authentication extension point). Applicability therefore rests with the application. Because no key sets a floor, an instance retaining native accounts will be assessed Other Than Satisfied on this element and the shortfall carried as a documented risk decision against the system owner, which is where the obligation belongs. Writing it as outside the boundary retires an obligation the product cannot discharge.

**SRG-APP-000176-WSR-000096.** The reading of the Not Applicable clause stands and I reach the same conclusion: privKeyPath carries a product default private key path for Splunk Web and resolves on a live 10.4.2 instance, so the clause does not hold. Separately, the IA-1 inventory record sets has_own_na_clause to false for this requirement although its check text opens with that clause, so the flag understates the number of requirements carrying one. The boundary conclusion does not stand. The search offered in support of it tested for filesystem-permission vocabulary (chown, chmod, file mode, permission) and inferred from its absence that the application exposes no access control over the key. That is the wrong search for this requirement, which asks who may access the private key, not how a file mode is set, and it is the pattern the standard warns against: absence of a setting named chmod is not absence of access control. Splunk itself exposes read and write paths to the key material through its own interfaces, and only application configuration restricts them: the /services/properties endpoint returns web.conf settings including the key path and the passphrase field, the web settings handler can rewrite the key path, and the storage passwords endpoint exposes stored secrets. Each is gated by an authorize.conf capability assigned to roles. An authenticated non-administrator holding rest_properties_get or list_storage_passwords therefore reaches the key path and the protected passphrase through the product, with no involvement of the host filesystem. Host discretionary access control and container image or volume ownership are a parallel layer, not a substitute, and an OUTSIDE_BOUNDARY row would tell an AO that no capability and role review is owed for key material. The designated PKI Sponsor is an organizational appointment recorded as an artifact alongside the configuration, not in place of it.

**SRG-APP-000086-AU-000030.** The requirement is disjunctive, not conditional on an NTP client: the title reads "must be configured to synchronize to within one second of the host server or, if NTP is configured directly in the log server, the NTP time source must be the same as the host." The prior assessor established only that the second disjunct's precondition is unmet, and no mechanism for it exists; that search reproduces and is correct as far as it goes. The first disjunct carries no precondition, and Splunk Enterprise 10.4.2 exposes the configuration that governs it. Props.conf carries a dedicated timestamp extraction section whose keys select which clock supplies the time stamp recorded on a log record and whether it agrees with the host server's clock: DATETIME_CONFIG chooses between the host's current system time, the input layer's time (the forwarder's clock for Splunk-to-Splunk traffic, the file modification time for monitor and batch inputs) and the text extractor, and TZ overrides, per source type, the time zone the product otherwise takes from the system running splunkd. A per-source-type TZ or TZ_ALIAS override displaces recorded time stamps by whole hours from the host server while the host's own time service remains synchronized, which is the precise divergence the requirement is written against. The MAX_DAYS_AGO, MAX_DAYS_HENCE, MAX_DIFF_SECS_AGO and MAX_DIFF_SECS_HENCE keys bound acceptable divergence and rewrite out-of-bound time stamps, indexes.conf quarantinePastSecs and quarantineFutureSecs bound how far an event's time stamp may sit from the current time before the indexer diverts it, and limits.conf max_tolerable_skew and addpeer_skew_limit are in-application clock-skew bounds between a search head and a search peer that log a warning and refuse the peer respectively. Grade D is therefore not reachable: the host operating system's time service is a supporting dependency assessed under the applicable operating system STIG, but the product's own configuration determines whether the time stamps it records agree with that clock, so the control is not implemented wholly by another baseline. The requirement discussion's note scopes NTP configuration out to the host operating system and network device management STIGs; it does not scope out the time stamps the log server records. As written, OUTSIDE_BOUNDARY would represent to the Authorizing Official that the Splunk administrator owes nothing on this requirement, and the configuration surface contradicts that.

**SRG-APP-000141-WSR-000085.** The underlying factual claim survives: an independent re-run of the search across all 128 files of the shipped specification set confirms the product implements no WebDAV protocol. The determination does not survive, because grade A requires that the product expose no mechanism for the requirement, and this requirement is the Web Server SRG tailoring of CM-7 a / CCI-000381 (least functionality), not a test for a protocol name. Two mechanisms exist and were not addressed. First, the requirement carries product STIG reference SPLK-CL-000300, which the basis and evidence never mention; DISA's product-specific implementation for this CCI directs that each instance be configured only with the Splunk instance roles necessary for the implementation, and the settings carrying those roles are present in 10.4.2. Second, Splunk Web implements an HTTP capability that moves server-side framework documents between apps and exposes configuration governing which HTTP methods that endpoint accepts, which is the functional class the requirement's discussion describes. Separately, the evidence misreads its own citation: restmap.conf.spec:468 is the method list for search head cluster REST replay, not an allow list of methods the product's HTTP endpoints accept, so it cannot carry the inference drawn from it. An assessment objective exists, with a configuration surface to examine and test; whether any instance is Satisfied is determined later.

**SRG-APP-000439-WSR-000192.** The determination of Not Applicable is withdrawn: the requirement carries no Not Applicable clause and its check text reads "If the web server does not use HTTP/2 at a minimum, this is a finding", so absence of the mandated capability is the finding the benchmark anticipates rather than an exemption from it, and a requirement the product cannot meet is assessed Other Than Satisfied and carried as a POA&M item for the system owner. The original basis itself names a TLS-terminating front end as the implementer, which is grade D reasoning supporting at most OUTSIDE_BOUNDARY and never NOT_APPLICABLE; and because the requirement's discussion extends the objective to back-end servers and to communications between web servers, which the product performs through its HEC HTTP server and its HTTP output, a client-facing front end cannot discharge the whole objective in any case. Grade A was also claimed from a configuration search alone, which cannot establish absence of HTTP/2 because ALPN negotiation requires no configuration key; a negotiation test was needed and was available.

**SRG-APP-000439-WSR-000193.** The determination of Not Applicable is withdrawn because the product does operate a request-forwarding front end with a configuration key that disables it: web.conf registers exposed splunkd REST endpoints and controls, per endpoint, whether splunkd forwards a request it has received to a remote node through the "remote-proxy" endpoint, with a companion setting governing how the forwarded request's arguments are re-encoded, while a search head cluster replays received REST methods to other members and proxies received requests to the captain. The objective — that a front end not hand a back end a request it has rewritten into a less strictly validated form — therefore has a referent inside the application boundary and an examination target. The benchmark provides no Not Applicable clause here but a severity modifier ("If HTTP downgrading is operationally necessary, and the rewritten request is validated against HTTP/1.x specification ..., mark as a CAT III finding"), which presupposes the requirement attaches; and the grade A premise that no listener accepts HTTP/2 was drawn from a configuration search, which cannot establish ALPN behavior.

**SRG-APP-000439-WSR-000196.** The rejection of grade B is sound and is retained — whether a forward proxy is used is a configurable state of an instance, so the clause "If a forward proxy is not used, this is not applicable" cannot be invoked at the product level — but the disposition does not follow from it. The benchmark's fix text directs "Configure the web server to only use forward proxies that route HTTP/2 requests upstream", which is an act of configuration performed on the application: the product names its forward proxy and scopes which destinations are routed through it in its own configuration file, and the original evidence cites exactly those keys, which is grade C mechanism evidence recorded against a disposition stating the application owes nothing. The upstream protocol remains a property of the proxy and must be obtained from that proxy's own baseline; that dependency belongs in the basis, not in the disposition.

**SRG-APP-000920-AU-000410.** That the host operating system sets the clock is accepted and the named provider is correct for that function, but the disposition is withdrawn because it records the whole objective as inherited while the requirement reads "within and between systems or system components" and the product is itself a multi-component system. The application carries a configurable share of the inter-component half: it bounds the clock difference it tolerates between a search head and a search peer, refuses to register a peer outside the configured bound, logs when the tolerance is exceeded, and at the ingest boundary reconciles the time representation of events arriving from other components, including a time zone conveyed by the forwarder. A per-host time service also cannot by itself produce agreement between components, which requires a common authoritative source designated by the organization and not named in the original provider statement; and the original search found only one of the two skew settings the specification set contains, so the basis for inheriting the entire control is incomplete.

**SRG-APP-000920-WSR-000320.** The observation that web.conf holds no clock or time-source key is accurate but does not place the requirement outside the application boundary, because the SRG requirement addresses the product that operates the browser-facing interface rather than one configuration file of it, and the product-level mechanisms for clock agreement between its components are configurable within the application. The disposition is withdrawn for the same reason as its Central Log Server counterpart: the application bounds and reports the clock difference it tolerates between components and reconciles event time at the ingest boundary, so the Splunk team owns a configurable share of this objective, while the clock-setting function alone is inherited from the host operating system's time service. The original search also missed one of the two skew settings in the specification set, and a per-host time service does not by itself achieve agreement between components, which needs an organization-designated common authoritative source that the provider statement does not name.

**SRG-APP-000925-AU-000420.** The finding that neither organization-defined parameter — the authoritative time source and the comparison frequency — has an application configuration surface is accepted, and the operating system's time service remains the provider for the comparison against the authoritative source. The disposition is withdrawn because the specification set does contain a clock-comparison mechanism that the original evidence did not find: a configurable tolerance for the difference between the native clock on the search head and the native clock on the peer, which logs a warning when exceeded and which the specification does not restrict to peer registration. That is a comparison of internal system clocks performed by the application against a configurable threshold, so the Splunk team owns a share of this objective and the row cannot be recorded as wholly inherited; the two skew settings must be examined on the instance and set to values the organization has approved.

**SRG-APP-000925-WSR-000330.** That web.conf carries no clock or time-source key is accurate, and the operating system's time service remains the provider for the comparison against the organization-defined authoritative source at the organization-defined frequency. The disposition is withdrawn because the claim that "the application performs no comparison of its clock against an authoritative source" was supported by a search that missed the one setting in the specification set that compares internal system clocks on a configurable tolerance and logs on exceedance, and because the requirement addresses the product operating the browser-facing interface rather than one of its configuration files. The application therefore owns a configurable share of the comparison objective and the row cannot be recorded as wholly inherited.

**SRG-APP-000219-WSR-000190.** The inheritance fails on its own terms and is overturned. First, no providing baseline is named: "the TLS-terminating reverse proxy or load balancer fronting the management interface" is a class of device, offered in the alternative, whose presence the basis under review itself treats as conditional when it concedes the requirement is Other Than Satisfied where no such device exists. A provider that may or may not be present is an architectural assumption, not an inheritance, and an applicability determination must hold for Splunk Enterprise 10.4.2 at any site. Second, this is a Web Server SRG requirement addressed to the web server under assessment. The splunkd management interface is that web server; interposing a second web server relocates the assessment object rather than transferring the control, and the requirement continues to bear on the management interface behind any such device. Third, the capability premise is too broad. The requirement's discussion states the objective as session authenticity against man-in-the-middle attacks and session hijacking and holds that web services will require TLS mutual authentication, and Splunk Enterprise 10.4.2 implements mutual TLS on the splunkd management interface through requireClientCert, which conditions every request in a management session on a certificate signed by a trusted certificate authority. That binding is to a client credential rather than to a source address, and a change of source address does not defeat it. Source-address restriction effective for the whole management session is separately configurable through the httpServer and per-endpoint network ACLs and through the general remote-login restriction, each evaluated per request. The narrow observation survives examination: the product exposes no key that compares a request's source address to the address that established the session, so testing an instance against the literal check text may yield Other Than Satisfied. That is an assessment result against the objective, not grounds to place the requirement outside the application boundary.

**SRG-APP-000219-WSR-000191.** Overturned on the same grounds as the management-session requirement, and more strongly, because Splunk Web is itself the web server the requirement addresses. The determination under review names no providing baseline; a reverse proxy or load balancer offered in the alternative, and conceded to be absent at some sites, is an architectural assumption rather than an inheritance, and the basis itself admits the requirement would then be Other Than Satisfied, which is a finding against the Splunk application. Shifting a Web Server SRG requirement about authenticated user sessions onto an upstream device relocates the assessment object; Splunk Web continues to serve authenticated user sessions behind any such device and the requirement continues to bear on it. The capability premise is also too broad. The requirement's discussion identifies the objective as session authenticity against session hijacking and insertion of false information into sessions, and holds that web services will require TLS mutual authentication. Splunk Enterprise 10.4.2 implements mutual TLS and certificate-bound user identity in Splunk Web through requireClientCert together with enableCertBasedUserAuth, certBasedUserAuthMethod and the Subject Alternative Name object identifier list, with client common name and alternative name checking. Those settings condition each request in a user session on a client certificate and derive the user identity from it, which addresses the stated objective without reference to a source address. Splunk Web additionally exposes a listener network ACL and, in strict single sign-on mode, a per-request source-address restriction against a configured trusted address list, each evaluated for the life of the session, along with session lifetime and cookie attribute controls. The narrow observation stands: the product exposes no key that pins a session to the address that established it, so testing an instance against the literal check text may yield Other Than Satisfied. That is an assessment result, not an inheritance, and the requirement remains with the Splunk application.

\newpage

## Findings against the product reference

The Splunk Enterprise 8.x for Linux STIG is sunsetted and targets a major version earlier than the one assessed. The following settings it names were re-examined against 10.4.2. A site implementing the reference verbatim would configure settings that no longer exist, under names the product does not read.

| Product rule | Setting named | Status in 10.4.2 |
|---|---|---|
| SPLK-CL-000080 | web.conf [settings] login_content | present but behavior changed - prescribed implementation... |
| SPLK-CL-000080 | web.conf [settings] login_content - acknowledgement behavior | consequential gap for the companion AC-8 b requirement |
| SPLK-CL-000060 | authentication.conf [splunk_auth] lockoutAttempts,... | settings confirmed in 10.4.2 - examination method in the... |
| SPLK-CL-000020 | none named | reference names no configuration setting |
| SPLK-CL-000010 | web.conf tools.session.timeout | withdrawn_or_never_existed — the implemented key in 10.4.2... |
| SPLK-CL-000290 | $SPLUNK_HOME/etc/opt/system/local/web.conf | incorrect path — the local web.conf path is... |
| SPLK-CL-000290 | inputs.conf [SSL] serverCert, sslPassword | confirmed in 10.4.2; two adjacent keys in the same stanza... |
| SPLK-CL-000010 | tools.session.timeout (web.conf) | renamed |
| SPLK-CL-000390 | SPLUNK_COMMON_CRITERIA (splunk-launch.conf) | not documented in the launch configuration specification |
| SPLK-CL-000390 | PYTHONDONTWRITEBYTECODE (splunk-launch.conf) | withdrawn |
| SPLK-CL-000320 | sslEnabled (authentication.conf, LDAP strategy stanza) | renamed (letter case) |
| SPLK-CL-000400 | expirePasswordDays (authentication.conf [splunk_auth]) | confirmed, but the rule omits the setting that activates it |
| SPLK-CL-000320 and... | ldap.conf TLS_REQCERT, TLS_CACERT, TLS_PROTOCOL_MIN,... | outside the Splunk configuration surface |
| SPLK-CL-000190 | $SPLUNK_ETC | withdrawn |
| SPLK-CL-000250 | (none named) | no_reference |
| SPLK-CL-000170 | (none named) | no_reference |
| SPLK-CL-000160 | server.conf [diskUsage] minFreeSpace | confirmed_in_10_4_2, value syntax extended |
| SPLK-CL-000260 | props.conf (no key named) for retaining the identity of... | imprecise_reference |
| SPLK-CL-000140 | admin role membership (Settings >> Users; Settings >>... | confirmed_but_off_objective |
| SPLK-CL-000120 | indexes.conf frozenTimePeriodInSecs | confirmed_in_10_4_2 |
| SPLK-CL-000270 | inputs.conf UDP input stanzas | confirmed_in_10_4_2 |
| SPLK-CL-000280 | Reporting and Alert tools (no conf key named) | confirmed_in_10_4_2 |
| SPLK-CL-000290 | inputs.conf [SSL] serverCert, sslPassword; outputs.conf... | confirmed_in_10_4_2 |
| SPLK-CL-000150 | outputs.conf forwarder output; inputs.conf receiver input | confirmed_in_10_4_2 |
| SPLK-CL-000100 | Settings >> Data Inputs (inputs.conf) | confirmed_in_10_4_2 |
| SPLK-CL-000110 | output.conf and input.conf (as named in the check text) | renamed |
| SPLK-CL-000090 | indexes.conf located in $SPLUNK_HOME/etc/system/local | check locus is version-stale |
| SPLK-CL-000140 | LDAP group-to-role mapping (Settings >> Authentication... | incomplete for 10.4.2 |
| n/a - finding against the... | Version of the supplied specification set | wrong product version |
| n/a - finding against the... | audit.conf logging_format and [auditconfig:/path] enabled... | absent from the supplied set, present in 10.4.2 |
| n/a - finding against the... | authorize.conf [capability::edit_dispatch_as] | withdrawn |
| n/a - finding against the... | log.cfg logging channel levels | outside the .conf specification surface |
| n/a - observation, not a... | audit trail event signing (audit.conf eventHash,... | withdrawn |
| SPLK-CL-000300 | Monitoring Console 'Mode' type (Standalone / Distributed),... | withdrawn |
| SPLK-CL-000300 | Monitoring Console 'General Setup' configuration page | renamed |
| SPLK-CL-000300 | Per-instance 'server roles' as a configurable value | withdrawn as a configuration setting |
| SPLK-CL-000290 | web.conf path given as... | path malformed in the reference; the settings it names are... |
| none - Splunk 8.x... | server.conf [config_change_audit] | renamed to [config_change_tracker] |
| SPLK-CL-000510 | None named - the rule's fix text directs a version upgrade... | no setting to confirm; the reference is procedural, so... |
| SPLK-CL-000390 | PYTHONDONTWRITEBYTECODE | withdrawn |
| SPLK-CL-000390 | SPLUNK_COMMON_CRITERIA | undeclared_but_still_honored |
| SPLK-CL-000410 | enablePasswordHistory, passwordHistoryCount | confirmed_but_addresses_a_different_objective |
| SPLK-CL-000490 | SSO proxy service (Apache, IIS, F5, SAML) | superseded_by_a_native_mechanism |
| SPLK-CL-000430 | /etc/openldap/ldap.conf TLS_PROTOCOL_MIN, TLS_CIPHER_SUITE | outside_the_application_boundary |
| SPLK-CL-000460 | disabled (inputs.conf, under [splunktcp-ssl:<port>]) | Not documented for the stanza the rule names in 10.4.2;... |
| SPLK-CL-000460 | Scope of the rule relative to the SRG requirements it is... | Present but narrower than the requirements sharing its CCI |
| SPLK-CL-000390 | SPLUNK_FIPS | confirmed_in_10_4_2 |
| SPLK-CL-000450 | (no configuration setting named by the rule) | no_reference |

\newpage

## Appendix A — Determination detail by requirement

One entry per requirement. The basis states why the determination holds, the citation is what an assessor retrieves to confirm it, and the assessment method is what a later assessment of an instance runs to gather that instance's result.

### Applicable requirements

**SRG-APP-000033-AU-001610** — CAT I — Applicable, evidence grade C.

The Central Log Server must be configured to enforce approved authorizations for logical access to information and system resources in accordance with applicable access control policies.

*Basis.* Splunk Enterprise implements role-based access control in its own configuration, with named roles, an inheritance relationship between them, a capability model of 156 discrete capabilities, and data-scoped restrictions on which indexes a role may search and what search filter is imposed on it. Authorization is evaluated after authentication and is not conferred by authentication alone, including for externally authenticated users, who reach roles through an explicit role mapping.

*Citation.* authorize.conf.spec:67 [role_<roleName>]; authorize.conf.spec:54 [capability::<capability>] with 156 capability stanzas present in the file (grep -c '^\[capability::' authorize.conf.spec = 156); authorize.conf.spec:79 importRoles; authorize.conf.spec:86 grantableRoles; authorize.conf.spec:150 srchFilter; authorize.conf.spec:292 srchIndexesAllowed and :297 srchIndexesDisallowed; authorize.conf.spec:236 srchJobsQuota; authentication.conf.spec:351 [roleMap_<authSettings-key>] and authentication.conf.spec:1230 [roleMap_<saml-authSettings-key>] for externally authenticated users.

*Mechanism.* authorize.conf [role_<roleName>] with importRoles, grantableRoles, srchFilter, srchIndexesAllowed, srchIndexesDisallowed, and the [capability::<capability>] set; authentication.conf [roleMap_<authSettings-key>] and [roleMap_<saml-authSettings-key>] for external authentication

*Assessment method.* Run as the Splunk service account: splunk btool authorize list --debug to enumerate the resolved roles, their imported roles, capabilities and index scoping, and splunk btool authentication list --debug to resolve the role mappings for any external authentication provider. Examine the enumerated capability sets against the documented duties of each role, giving particular attention to admin_all_objects (authorize.conf.spec:447), change_authentication (:479), edit_user (:719) and edit_roles (:622); the benchmark directs a finding where users hold permissions not relevant to their role.

**SRG-APP-000148-AU-002270** — CAT I — Applicable, evidence grade C.

The Central Log Server must be configured to uniquely identify and authenticate organizational users (or processes acting on behalf of organizational users).

*Basis.* Splunk Enterprise 10.4.2 carries its own identification and authentication subsystem: authType selects among native Splunk, LDAP, Scripted, SAML and ProxySSO authentication, and each named user is bound to a role through the roleMap and userToRoleMap stanzas, so per-user identifiers and per-user authentication are reachable through application configuration. The accompanying prohibition on group logon accounts is established by account review rather than by a configuration key, so the assessment must enumerate accounts as well as read the conf layer.

*Citation.* authentication.conf.spec:30 (authType = [Splunk|LDAP|Scripted|SAML|ProxySSO]); authentication.conf.spec:44 (authSettings); authentication.conf.spec:351 ([roleMap_<authSettings-key>]); authentication.conf.spec:1251 ([userToRoleMap_<saml-authSettings-key>]); authorize.conf.spec:67 ([role_<roleName>])

*Mechanism.* authentication.conf [authentication] authType, authSettings; [roleMap_<authSettings-key>]; [userToRoleMap_<saml-authSettings-key>]; authorize.conf [role_<roleName>]

*Assessment method.* splunk btool authentication list --debug (run as the Splunk service account) to read authType, authSettings and the role-map stanzas; then enumerate logon accounts via the REST endpoint /services/authentication/users and confirm each carries a distinct identifier and that no shared or group logon account exists.

*Product reference.* SPLK-CL-000320 — renamed

**SRG-APP-000171-AU-002540** — CAT I — Applicable, evidence grade C.

For accounts using password authentication, the Central Log Server must be configured to store only cryptographic representations of passwords.

*Basis.* Splunk native authentication stores passwords as salted hashes and exposes the algorithm as a configurable setting, with SHA512-crypt and SHA256-crypt available alongside the legacy MD5-crypt, so storing only a cryptographic representation is reachable through application configuration. The specification set records that the setting applies to passwords set or changed after it takes effect and that existing passwords retain their previous algorithm, which an assessment must account for rather than reading the key alone.

*Citation.* authentication.conf.spec:58 (passwordHashAlgorithm = [SHA512-crypt|SHA256-crypt|SHA512-crypt-<num_rounds>|SHA256-crypt-<num_rounds>|MD5-crypt], "This controls how hashed passwords are stored", "This setting only affects new password settings", default SHA512-crypt); passwords.conf.spec:22 (a clear text password "when saved from splunkd" is replaced by an encrypted representation)

*Mechanism.* authentication.conf [authentication] passwordHashAlgorithm

*Assessment method.* splunk btool authentication list authentication --debug (run as the Splunk service account) and read passwordHashAlgorithm; then inspect the hash prefix on each native account record to confirm no account retains an MD5-crypt representation from before the setting took effect.

**SRG-APP-000172-AU-002550** — CAT I — Applicable, evidence grade C.

For accounts using password authentication, the Central Log Server must use FIPS-validated SHA-1 or later protocol to protect the integrity of the password authentication process.

*Basis.* Splunk exposes both halves of this requirement through its own configuration: SPLUNK_FIPS constrains the instance to the FIPS-validated cryptographic module, and passwordHashAlgorithm selects a SHA-2 family hash for the stored authenticator. The specification set records that SPLUNK_FIPS is one-time only and must be configured before the instance first starts, otherwise the secret key generated at first startup may not meet FIPS guidance, so this determination cannot be satisfied by a later configuration change.

*Citation.* splunk-launch.conf.spec:110 (SPLUNK_FIPS = [0|1], "NOTE: This setting is one-time only", "If you configure it to 'true' and then start the Splunk platform instance, you cannot later configure it to 'false'. You must reinstall the software"); authentication.conf.spec:58 (passwordHashAlgorithm)

*Mechanism.* splunk-launch.conf SPLUNK_FIPS; authentication.conf [authentication] passwordHashAlgorithm

*Assessment method.* read SPLUNK_FIPS from splunk-launch.conf and confirm FIPS mode in the startup banner of splunkd.log; splunk btool authentication list authentication --debug (run as the Splunk service account) and read passwordHashAlgorithm.

*Product reference.* SPLK-CL-000390 — confirmed in 10 4 2

**SRG-APP-000172-WSR-000104** — CAT I — Applicable, evidence grade C.

The web server must encrypt passwords during transmission.

*Basis.* Splunk Web terminates TLS through its own configuration, so credentials submitted at logon are protected in transit by application settings rather than by an external proxy. The product also exposes a GET-based alternate logon endpoint that places the user name and password in a URL query string; keeping that endpoint disabled is part of the same determination, and the specification set documents the endpoint's URL form explicitly.

*Citation.* web.conf.spec:70 (enableSplunkWebSSL, "Toggle between http or https", default false); web.conf.spec:82 (serverCert); web.conf.spec:75 (privKeyPath); web.conf.spec:198 (enable_insecure_login, "Provides an alternate GET-based authentication mechanism", documented URL carries username and password as query parameters, default false)

*Mechanism.* web.conf [settings] enableSplunkWebSSL, serverCert, privKeyPath, enable_insecure_login; server.conf [sslConfig] for the management interface

*Assessment method.* splunk btool web list settings --debug (run as the Splunk service account) and read enableSplunkWebSSL and enable_insecure_login; then confirm the web port rejects plaintext HTTP and that a request to the GET-based logon endpoint is refused.

*Product reference.* SPLK-CL-000390 — confirmed in 10 4 2

**SRG-APP-000175-AU-002630** — CAT I — Applicable, evidence grade C.

The Central Log Server, when using PKI-based authentication, must validate certificates by constructing a certification path (which includes status information) to an accepted trust anchor.

*Basis.* Splunk exposes both elements the requirement names through its own configuration: sslRootCAPath supplies the accepted trust anchor against which a presented client certificate is validated, and certificateStatusValidationMethod turns on certificate status checking for every Splunk network channel that uses TLS, backed by a revocation list at sslCRLPath. Status information is available by certificate revocation list only; the specification set states that "crl" is the single accepted value, so an assessment should not expect an OCSP responder configuration.

*Citation.* web.conf.spec:108 (sslRootCAPath, the root CA used "to authenticate client certificates"); server.conf.spec:996 (sslRootCAPath); server.conf.spec:1125 (certificateStatusValidationMethod = crl, "Currently, the only acceptable value for this setting is 'crl'", default empty so checks are off); server.conf.spec:5392 (sslCRLPath); web.conf.spec:151 (requireClientCert)

*Mechanism.* web.conf [settings] sslRootCAPath, requireClientCert; server.conf [sslConfig] sslRootCAPath, certificateStatusValidationMethod; [kvstore] sslCRLPath

*Assessment method.* splunk btool server list sslConfig --debug and splunk btool web list settings --debug (run as the Splunk service account) to read sslRootCAPath and certificateStatusValidationMethod; then present a certificate issued outside the configured trust anchor and a revoked certificate, and confirm both are refused.

**SRG-APP-000176-AU-002640** — CAT I — Applicable, evidence grade C.

The Central Log Server, when using PKI-based authentication, must enforce authorized access to the corresponding private key.

*Basis.* The check text clause "If not using PKI-based authentication this is NA" turns on site state rather than on a product property and is declined, since Splunk can use PKI-based authentication. The product enforces authorized use of the private key through its own configuration: sslPassword protects the key named by privKeyPath with a passphrase that splunkd stores encrypted, so possession of the key file alone does not yield a usable key. Discretionary access control on the key file itself is provided by the host operating system and is assessed under SRG-APP-000176-WSR-000096.

*Citation.* web.conf.spec:93 (sslPassword, "Password that protects the private key specified by 'privKeyPath'"); web.conf.spec:75 (privKeyPath); server.conf.spec:989 (sslPassword); authentication.conf.spec:1385 ([secrets] stanza, integration with platform-provided secret storage); the group inventory records has_own_na_clause as false for this requirement, which is inconsistent with the check text quoted above

*Mechanism.* web.conf [settings] privKeyPath, sslPassword; server.conf [sslConfig] sslPassword

*Assessment method.* splunk btool web list settings --debug and splunk btool server list sslConfig --debug (run as the Splunk service account) to read privKeyPath and confirm sslPassword is present and stored in encrypted form; then confirm the key file named by privKeyPath is encrypted rather than an unprotected PEM key.

**SRG-APP-000178-AU-002660** — CAT I — Applicable, evidence grade C.

The Central Log Server must obfuscate authentication information during the authentication process so that the authentication is not visible.

*Basis.* Splunk exposes configuration that keeps authentication information out of view during the authentication exchange: TLS termination protects the credential in transit, and the GET-based alternate logon endpoint, which the specification set documents as carrying the user name and password in a URL query string where they would be visible in logs and history, is governed by enable_insecure_login. Retrieval of stored credentials in cleartext through the REST and SPL surfaces is separately constrained by the storage password masking settings.

*Citation.* web.conf.spec:198 (enable_insecure_login, documented URL form carries username and password as query parameters, default false); web.conf.spec:70 (enableSplunkWebSSL); limits.conf.spec:5072 ([storage_passwords_masking]); limits.conf.spec:5073 (view_cleartext_allowlist, "Default: '*' (always return cleartext passwords)"); limits.conf.spec:5094 (view_cleartext_spl_rest, default true)

*Mechanism.* web.conf [settings] enable_insecure_login, enableSplunkWebSSL; limits.conf [storage_passwords_masking] view_cleartext_allowlist, view_cleartext_spl_rest

*Assessment method.* splunk btool web list settings --debug and splunk btool limits list storage_passwords_masking --debug (run as the Splunk service account) to read enable_insecure_login, enableSplunkWebSSL, view_cleartext_allowlist and view_cleartext_spl_rest; then request the GET-based logon endpoint and confirm refusal, and confirm the logon form does not echo the typed credential.

**SRG-APP-000179-AU-002670** — CAT I — Applicable, evidence grade C.

The Central Log Server must use FIPS-validated SHA-1 or higher hash function to protect the integrity of keyed-hash message authentication code (HMAC), Key Derivation Functions (KDFs), Random Bit Generation, hash-only applications, and digital signature verification (legacy use only).

*Basis.* SPLUNK_FIPS constrains the instance to the FIPS-validated cryptographic module, which is what selects the validated implementation behind the HMAC, key derivation, random bit generation, hashing and signature verification the requirement enumerates. Protocol, cipher suite and curve selection are separately configurable on each of the web, management, receiving and forwarding channels, so the hash actually negotiated is also reachable through application configuration. SPLUNK_FIPS is one-time only and must be configured before first start.

*Citation.* splunk-launch.conf.spec:110 (SPLUNK_FIPS = [0|1], one-time only); server.conf.spec:765 (sslVersions); server.conf.spec:780 (sslVersionsForClient); server.conf.spec:940 (cipherSuite); server.conf.spec:955 (ecdhCurves); web.conf.spec:239, :255, :276 (sslVersions, cipherSuite, ecdhCurves); inputs.conf.spec:929-931 (sslVersions, cipherSuite, ecdhCurves); outputs.conf.spec:664, :676, :779 (cipherSuite, ecdhCurves, sslVersions)

*Mechanism.* splunk-launch.conf SPLUNK_FIPS; server.conf [sslConfig] sslVersions, sslVersionsForClient, cipherSuite, ecdhCurves; web.conf [settings] sslVersions, cipherSuite, ecdhCurves; inputs.conf and outputs.conf SSL stanzas

*Assessment method.* read SPLUNK_FIPS from splunk-launch.conf and confirm FIPS mode in the splunkd.log startup banner; splunk btool server list sslConfig --debug, splunk btool web list settings --debug, splunk btool inputs list --debug and splunk btool outputs list --debug (run as the Splunk service account) to read sslVersions, cipherSuite and ecdhCurves on each channel.

*Product reference.* SPLK-CL-000390, SPLK-CL-000430 — confirmed in 10 4 2

**SRG-APP-000179-WSR-000110** — CAT I — Applicable, evidence grade C.

The web server must use cryptographic modules that meet the requirements of applicable federal laws, Executive Orders, directives, policies, regulations, standards, and guidance when encrypting stored data.

*Basis.* SPLUNK_FIPS selects the FIPS-validated cryptographic module for the instance's cryptographic operations, including the at-rest protection of stored credentials written through the password store and the hashing of native account authenticators, so that module used when the application encrypts data it stores is reachable through application configuration. Splunk exposes no configuration-level encryption for index data held on local storage; server-side encryption keys apply to remote storage volumes only, and local at-rest protection of index data rests with the host operating system or storage baseline, which an assessment should record separately.

*Citation.* splunk-launch.conf.spec:110 (SPLUNK_FIPS); authentication.conf.spec:58 (passwordHashAlgorithm); passwords.conf.spec:22 (clear text replaced by an encrypted representation when saved from splunkd); server.conf.spec:6330 (remote.s3.encryption = sse-s3 | sse-kms | sse-c | none, applying to remote storage volumes); no local index encryption setting appears in the specification set

*Mechanism.* splunk-launch.conf SPLUNK_FIPS; authentication.conf [authentication] passwordHashAlgorithm; server.conf remote volume remote.s3.encryption where remote storage is used

*Assessment method.* read SPLUNK_FIPS from splunk-launch.conf and confirm FIPS mode in the splunkd.log startup banner; splunk btool authentication list authentication --debug and splunk btool server list --debug (run as the Splunk service account) to read passwordHashAlgorithm and any remote volume encryption setting; record local index at-rest protection against the host or storage baseline.

*Product reference.* SPLK-CL-000390, SPLK-CL-000430 — confirmed in 10 4 2

**SRG-APP-000224-WSR-000135** — CAT I — Applicable, evidence grade C.

The web server must generate a unique session identifier for each session using a FIPS 140-2 approved random number generator.

*Basis.* Splunk Enterprise 10.4.2 selects the FIPS 140-2 algorithm set and the validated cryptographic module for the whole instance through one launch-file setting, and that setting governs the random number generator from which session identifiers are drawn. The specification records that the setting takes effect only before the instance first starts, cannot be reversed afterwards without reinstalling, and that a secret generated on first start before it is set might not meet FIPS guidance. The requirement therefore applies to the product and is implemented at installation rather than by later configuration change.

*Citation.* splunk-launch.conf.spec:110-127 (SPLUNK_FIPS = [0|1], 'uses the algorithms and restrictions that apply to the FIPS Publication 140-2 standard'; 'This setting is one-time only'; reinstall required to reverse). Server.conf.spec:5369-5371 and :6634-6636 (settings whose behavior changes when SPLUNK_FIPS=1). Confirmed against the live instance reporting Splunk 10.4.2 (build 33c3bf42cd73).

*Mechanism.* splunk-launch.conf SPLUNK_FIPS (the launch file carries no stanzas)

*Assessment method.* Run `splunk show fips-mode` as the Splunk service account and examine the launch file for SPLUNK_FIPS; then open two concurrent authenticated sessions and confirm the identifiers issued are neither equal nor sequential.

**SRG-APP-000429-WSR-000113** — CAT I — Applicable, evidence grade C.

The web server must encrypt user identifiers and passwords.

*Basis.* The check text carries the conditional 'If the web server is not authorizing and managing users, this is NA.' That condition requires that the product neither authorize nor manage users, and both halves fail: Splunk Enterprise carries native authentication with locally stored credentials and its own role-based authorization model. The product is therefore the user authenticator and manager and the requirement applies. The storage protection is a product setting: one key selects the algorithm used to store hashed passwords for the native authentication type, with SHA512-crypt documented as the default and an optional round count, and configured service credentials are encrypted at startup rather than kept in clear text. Note that MD5-crypt remains a selectable value for that key, so the assessment must read the configured value rather than rely on the default.

*Citation.* authentication.conf.spec:26 ([authentication]) with :58-79 (passwordHashAlgorithm = [SHA512-crypt|SHA256-crypt|SHA512-crypt-<num_rounds>|SHA256-crypt-<num_rounds>|MD5-crypt], 'This controls how hashed passwords are stored in the $SPLUNK_HOME/etc/passwd file for the default "Splunk" authType'; 'Default: SHA512-crypt'; the setting affects only new or changed passwords). Authentication.conf.spec:437 ([splunk_auth]) with :441 (minPasswordLength); :893 ('On startup, the auth system encrypts the values you specify here'). Authorize.conf.spec:67-78 ([role_<roleName>], the authorization model). Splunk-launch.conf.spec:110-127 (SPLUNK_FIPS constrains the algorithm set).

*Mechanism.* authentication.conf [authentication] authType, passwordHashAlgorithm; authentication.conf [splunk_auth] minPasswordLength; authorize.conf [role_<roleName>]; splunk-launch.conf SPLUNK_FIPS

*Assessment method.* Run `splunk btool authentication list --debug` as the Splunk service account and read authType and passwordHashAlgorithm; examine the local credential file and confirm every entry carries a hash prefix corresponding to the configured algorithm and that no entry retains a weaker prior algorithm.

**SRG-APP-000439-AU-004310** — CAT I — Applicable, evidence grade C.

The Central Log Server must be configured to protect the confidentiality and integrity of transmitted information.

*Basis.* Splunk Enterprise implements transmission protection on the forwarder-to-indexer and management channels through its own configuration: TLS listeners with a server certificate, optional mutual authentication, version and cipher selection on the receiving side, and matching client certificate and peer-verification settings on the sending side. DISA published a product-specific implementation for this requirement and the files, stanzas and keys it names are present in the 10.4.2 configuration surface.

*Citation.* inputs.conf.spec:876 [splunktcp-ssl:<port>], 986 [SSL], 990 serverCert, 1002 sslPassword, 1015 requireClientCert, 1035 sslVersions, 1052 cipherSuite; outputs.conf.spec:647 sslPassword, 652 clientCert, 700 sslVerifyServerCert, 741 sslCommonNameToCheck, 779 sslVersions; server.conf.spec:724 enableSplunkdSSL. SPLK-CL-000460 names inputs.conf [splunktcp-ssl:9997]/[SSL] serverCert and sslPassword and outputs.conf [tcpout:group1] clientCert and sslPassword; each of those keys still exists in 10.4.2.

*Mechanism.* inputs.conf [splunktcp-ssl:<port>] and [SSL] serverCert, sslPassword, requireClientCert, sslVersions, cipherSuite; outputs.conf [tcpout:<group>] clientCert, sslPassword, sslVersions, sslVerifyServerCert, sslCommonNameToCheck; server.conf [sslConfig] enableSplunkdSSL

*Assessment method.* splunk btool inputs list --debug; splunk btool outputs list --debug; splunk btool server list --debug - confirm a TLS receiver is defined and that the plaintext equivalents are not, then test each receiving port with "openssl s_client -connect <host>:<port>" and confirm the handshake completes with a certificate issued by an approved authority.

*Product reference.* SPLK-CL-000460 — confirmed in 10 4 2

**SRG-APP-000439-WSR-000151** — CAT I — Applicable, evidence grade C.

The web server must employ cryptographic mechanisms (TLS/DTLS/SSL) preventing the unauthorized disclosure of information during transmission.

*Basis.* The product implements TLS on the browser-facing channel through its own configuration file, with the certificate, private key, protocol versions and cipher selection all exposed as settings; the splunkd management channel and the HTTP Event Collector channel carry equivalent settings. The sunsetted product STIG rule for this CCI addresses only the Splunk-to-Splunk channel and names no key for the browser-facing channel, so the mechanism is established from the specification set.

*Citation.* web.conf.spec:16 [settings], 70 enableSplunkWebSSL ("Toggle between http or https"), 75 privKeyPath, 82 serverCert, 93 sslPassword, 239 sslVersions, 255 cipherSuite; server.conf.spec:724 enableSplunkdSSL; inputs.conf.spec:1665 enableSSL (HTTP Event Collector). Each of these keys resolves in the merged web.conf and server.conf of a live 10.4.2 instance through btool.

*Mechanism.* web.conf [settings] enableSplunkWebSSL, serverCert, privKeyPath, sslPassword, sslVersions, cipherSuite; server.conf [sslConfig] enableSplunkdSSL; inputs.conf [http] enableSSL

*Assessment method.* splunk btool web list --debug and splunk btool server list --debug to examine enableSplunkWebSSL and enableSplunkdSSL; then test each listener with "openssl s_client -connect <host>:<port>" and confirm that no equivalent plaintext listener answers.

*Product reference.* SPLK-CL-000460 — confirmed in 10 4 2

**SRG-APP-000514-AU-002890** — CAT I — Applicable, evidence grade C.

The Central Log Server must implement NIST FIPS-validated cryptography for the following: to provision digital signatures; to generate cryptographic hashes; and/or to protect unclassified information requiring confidentiality and cryptographic protection.

*Basis.* The product exposes a single install-time switch that places the instance in FIPS mode, after which its algorithm set and restrictions follow the FIPS publication across every channel, SSLv3 is refused regardless of the version setting, and certificate revocation checking becomes mandatory. The setting is one-time: it must be present before first start, and reversing it requires reinstalling the software, which makes this an image or installation decision rather than a runtime one.

*Citation.* splunk-launch.conf.spec:110 SPLUNK_FIPS = [0|1] - "NOTE: This setting is one-time only... If you configure it to \"true\" and then start the Splunk platform instance, you cannot later configure it to \"false\". You must reinstall the software." The product-wide effect is recorded at web.conf.spec:246, server.conf.spec:774-775, alert_actions.conf.spec:435, deploymentclient.conf.spec:152 and indexes.conf.spec:2358 (ssl3 disabled in FIPS mode regardless of configuration) and at server.conf.spec:5400 (the CRL file is used when the instance is in FIPS mode). DISA's SPLK-CL-000390 names this same setting and it exists in 10.4.2.

*Mechanism.* splunk-launch.conf, SPLUNK_FIPS = 1, set before the instance is first started

*Assessment method.* Examine splunk-launch.conf for SPLUNK_FIPS and run "splunk show fips-mode" as the Splunk service account; confirm the command reports FIPS mode enabled. Note that the specification text cites FIPS 140-2 while the requirement cites 140-2/140-3; the validation status of the cryptographic module is a CMVP certificate matter examined alongside the configuration setting.

*Product reference.* SPLK-CL-000390 — confirmed in 10 4 2

**SRG-APP-000610-AU-000050** — CAT I — Applicable, evidence grade C.

The Central Log Server must use FIPS-validated SHA-2 or higher hash function for digital signature generation and verification (non-legacy use).

*Basis.* Splunk Enterprise selects hash and cipher algorithms through configuration and a FIPS launch setting constrains the available set, so the requirement applies to the application. The FIPS setting is read at startup from the launch configuration, and DISA's reference states it must be in place before the initial start, which makes entry into FIPS mode an installation activity rather than a runtime configuration change.

*Citation.* splunk-launch.conf.spec:110 SPLUNK_FIPS = [0|1]; authentication.conf.spec:58 passwordHashAlgorithm offers SHA512-crypt and SHA256-crypt with explicit round counts; server.conf.spec:765 sslVersions, :780 sslVersionsForClient, :940 cipherSuite, :955 ecdhCurves; web.conf.spec:239, :255, :276; inputs.conf.spec:929-931; outputs.conf.spec:779, :664, :676. All settings named by the product STIG reference are present in 10.4.2 under unchanged names.

*Mechanism.* splunk-launch.conf: SPLUNK_FIPS; authentication.conf [authentication]: passwordHashAlgorithm; server.conf, web.conf, inputs.conf, outputs.conf: sslVersions, sslVersionsForClient, cipherSuite, ecdhCurves

*Assessment method.* splunk show fips-mode; examine the launch configuration for SPLUNK_FIPS; splunk btool authentication list --debug for [authentication] passwordHashAlgorithm; splunk btool server list --debug, splunk btool web list --debug, splunk btool inputs list --debug and splunk btool outputs list --debug for sslVersions, cipherSuite and ecdhCurves.

*Product reference.* SPLK-CL-000390, SPLK-CL-000430 — confirmed in 10 4 2

**SRG-APP-000001-WSR-000001** — CAT II — Applicable, evidence grade C.

The web server must limit the number of allowed simultaneous session requests.

*Basis.* Splunk Web exposes settings that bound the number of simultaneous HTTP connections the application will accept and the number of threads available to active HTTP transactions, which is the limit this requirement calls for. The splunkd management HTTP server exposes equivalent bounds, so the parameter exists on both of the product's listening interfaces.

*Citation.* web.conf.spec:1106 maxSockets - "The number of simultaneous HTTP connections that Splunk Web can accept. This value can be limited to constrain resource usage."; web.conf.spec:1098 maxThreads; web.conf.spec:835 server.thread_pool; web.conf.spec:853 server.socket_timeout; server.conf.spec:1379 maxSockets and server.conf.spec:1389 maxThreads under [httpServer].

*Mechanism.* web.conf [settings] maxSockets, maxThreads, server.thread_pool, server.socket_timeout; server.conf [httpServer] maxSockets, maxThreads

*Assessment method.* Run as the Splunk service account, never as root: splunk btool web list --debug | grep -E 'maxSockets|maxThreads|server.thread_pool' and splunk btool server list httpServer --debug | grep -E 'maxSockets|maxThreads'. Per web.conf.spec:1101-1104 and 1109-1112 a value of 0 delegates the limit to estimated server capacity and a negative value removes it; the benchmark directs a finding where the parameter is unlimited.

**SRG-APP-000001-WSR-000002** — CAT II — Applicable, evidence grade C.

The web server must perform server-side session management.

*Basis.* Splunk Web holds session state on the Splunk instance and transmits only a session identifier to the browser, and the specification set exposes the storage type and storage path for that state together with the cookie protections. The assessment objective of this requirement - that user authorization and identity information not be carried by the client - is met by the product's own session subsystem rather than by an external component.

*Citation.* web.conf.spec:920 tools.sessions.on - "Whether or not user session support is enabled. Always set this to true."; web.conf.spec:977-982 tools.sessions.storage_type = [file] and tools.sessions.storage_path, documented default storage_path=var/run/splunk; web.conf.spec:924 tools.sessions.timeout; web.conf.spec:943 tools.sessions.httponly; web.conf.spec:951 tools.sessions.secure; web.conf.spec:962 tools.sessions.forceSecure.

*Mechanism.* web.conf [settings] tools.sessions.on, tools.sessions.storage_type, tools.sessions.storage_path, tools.sessions.timeout, tools.sessions.httponly, tools.sessions.secure, tools.sessions.forceSecure

*Assessment method.* Run as the Splunk service account: splunk btool web list --debug | grep -E 'tools\.sessions'. Examine that tools.sessions.on resolves to true and that storage_type and storage_path resolve to a server-side location; test by authenticating to Splunk Web and confirming the browser receives only a session cookie and no identity or authorization attributes.

**SRG-APP-000014-WSR-000006** — CAT II — Applicable, evidence grade C.

The web server must use encryption strength in accordance with the categorization of data hosted by the web server when remote connections are provided.

*Basis.* Splunk Enterprise exposes the protocol version list, cipher string and elliptic curve list for both the Splunk Web interface and the splunkd management and replication channels, so the encryption strength offered on remote connections is selectable by configuration and can be matched to the categorization of the data the instance holds. The product additionally exposes a FIPS mode that constrains the available algorithms at the launch layer.

*Citation.* web.conf.spec:70 enableSplunkWebSSL; web.conf.spec:239 sslVersions; web.conf.spec:255 cipherSuite - "If set, uses the specified cipher string for the HTTP server"; web.conf.spec:276 ecdhCurves; server.conf.spec:765 sslVersions, server.conf.spec:940 cipherSuite and server.conf.spec:955 ecdhCurves under [sslConfig]; splunk-launch.conf.spec:110 SPLUNK_FIPS = [0|1].

*Mechanism.* web.conf [settings] enableSplunkWebSSL, sslVersions, cipherSuite, ecdhCurves; server.conf [sslConfig] sslVersions, sslVersionsForClient, cipherSuite, ecdhCurves; splunk-launch.conf SPLUNK_FIPS

*Assessment method.* Run as the Splunk service account: splunk btool web list --debug | grep -E 'enableSplunkWebSSL|sslVersions|cipherSuite|ecdhCurves', splunk btool server list sslConfig --debug | grep -E 'sslVersions|cipherSuite|ecdhCurves', and splunk btool splunk-launch list --debug | grep SPLUNK_FIPS. Test the offered strength independently of the declared value with openssl s_client -connect <splunk-web-host>:<web-port> -tls1_1 and -tls1_2, and with openssl ciphers against the resolved cipherSuite string. The assessment must also establish the system categorization against which the offered strength is judged.

**SRG-APP-000015-WSR-000014** — CAT II — Applicable, evidence grade C.

The web server must use cryptography to protect the integrity of remote sessions.

*Basis.* This requirement addresses cryptographic protection of the remote session itself rather than the strength selection assessed under SRG-APP-000014-WSR-000006, and Splunk Enterprise implements it by terminating remote access sessions over TLS on both the Splunk Web interface and the splunkd REST and management interface, with optional mutual certificate authentication. The keys that enable and constrain that protection are part of the product's configuration surface.

*Citation.* web.conf.spec:70 enableSplunkWebSSL; web.conf.spec:75 privKeyPath and web.conf.spec:82 serverCert; web.conf.spec:151 requireClientCert; web.conf.spec:239 sslVersions and web.conf.spec:255 cipherSuite; server.conf.spec:858 requireClientCert and server.conf.spec:798 sslVerifyServerCert under [sslConfig]; web.conf.spec:951 tools.sessions.secure, which binds the session cookie to the protected channel.

*Mechanism.* web.conf [settings] enableSplunkWebSSL, serverCert, privKeyPath, requireClientCert, sslVersions, cipherSuite, tools.sessions.secure; server.conf [sslConfig] requireClientCert, sslVerifyServerCert

*Assessment method.* Run as the Splunk service account: splunk btool web list --debug | grep -E 'enableSplunkWebSSL|serverCert|privKeyPath|requireClientCert|tools.sessions.secure' and splunk btool server list sslConfig --debug | grep -E 'requireClientCert|sslVerifyServerCert'. Test by requesting the Splunk Web login path over cleartext HTTP and confirming the connection is refused or redirected, then confirming the TLS session establishes on the management port.

**SRG-APP-000016-WSR-000005** — CAT II — Applicable, evidence grade C.

The web server must generate information to be used by external applications or entities to monitor and control remote access.

*Basis.* Splunk Enterprise generates an HTTP access record for Splunk Web and an audit trail for authentication and administrative actions, and the specification set exposes forwarding stanzas that deliver those records to an external system over TCP, syslog or HTTP. The requirement asks the application to generate and supply remote access information to an external monitoring or control application, not to perform the monitoring itself, so the mechanism is the generation plus the egress path and both are present.

*Citation.* web.conf.spec:871 log.access_file - "The HTTP access log filename", default web_access.log; audit.conf.spec:23-29 [auditTrail] queueing - "Whether or not audit events are sent to the indexQueue"; inputs.conf.spec:1497-1506 documenting the _audit index and the audittrail sourcetype; outputs.conf.spec:61 [tcpout] and outputs.conf.spec:121 [tcpout:<target_group>]; outputs.conf.spec:1058 [syslog] and outputs.conf.spec:1077 [syslog:<target_group>]; outputs.conf.spec:856 [httpout].

*Mechanism.* web.conf [settings] log.access_file; audit.conf [auditTrail] queueing; outputs.conf [tcpout], [tcpout:<target_group>], [syslog], [syslog:<target_group>], [httpout]

*Assessment method.* Run as the Splunk service account: splunk btool web list --debug | grep log.access_file, splunk btool audit list --debug, and splunk btool outputs list --debug to identify the configured external target groups. Then establish that the records reach the external monitoring application, by examining the receiving system for the forwarded web access and audit events rather than by examining the forwarder alone.

**SRG-APP-000026-AU-000580** — CAT II — Applicable, evidence grade C.

The Central Log Server must automatically audit account creation.

*Basis.* Splunk Enterprise maintains its own local user accounts and performs their creation through a managed REST endpoint, and the product writes an audit trail of those administrative actions to a dedicated internal index. The configuration surface that governs whether those audit events reach an index is part of the product, so the requirement is implementable by Splunk configuration.

*Citation.* audit.conf.spec:23-29 [auditTrail] queueing, the only setting the shipped audit specification exposes; indexes.conf:200 [_audit] in the shipped default index definitions; inputs.conf.spec:1497-1506 documenting the _audit index and the audittrail sourcetype; authorize.conf.spec:463 naming the /services/authentication/users endpoint through which accounts are created.

*Mechanism.* audit.conf [auditTrail] queueing, with account creation recorded to the _audit index (indexes.conf [_audit]) under the audittrail sourcetype; account creation occurs through /services/authentication/users

*Assessment method.* Run as the Splunk service account: splunk btool audit list --debug to establish that [auditTrail] queueing resolves to true, and splunk btool indexes list --debug | grep -c '\[_audit\]' to establish the audit index exists. Then test by having the administrator create a test account through the supported interface and searching the audit trail over that interval for the resulting user-creation record; the assessment must confirm the record carries the acting user, the target account and the timestamp.

**SRG-APP-000027-AU-000590** — CAT II — Applicable, evidence grade C.

The Central Log Server must automatically audit account modification.

*Basis.* Modification of a Splunk local account or of the roles bound to it is performed through the product's managed user and role endpoints, and those administrative actions are written to the product's audit trail. The same configuration surface that governs audit event delivery for account creation governs it for modification, so Splunk implements this requirement through its own configuration.

*Citation.* audit.conf.spec:23-29 [auditTrail] queueing; indexes.conf:200 [_audit] in the shipped default index definitions; inputs.conf.spec:1497-1506 documenting the _audit index and the audittrail sourcetype; authorize.conf.spec:463 naming /services/authentication/users and authorize.conf.spec:622 and :719 naming the edit_roles and edit_user capabilities that gate modification.

*Mechanism.* audit.conf [auditTrail] queueing, with account and role modification recorded to the _audit index (indexes.conf [_audit]); modification is gated by authorize.conf [capability::edit_user] and [capability::edit_roles]

*Assessment method.* Run as the Splunk service account: splunk btool audit list --debug to establish [auditTrail] queueing, then test by having the administrator modify a test account's role assignment through the supported interface and searching the audit trail over that interval for the resulting modification record, confirming the acting user, the target account and the attribute changed.

**SRG-APP-000028-AU-000600** — CAT II — Applicable, evidence grade C.

The Central Log Server must automatically audit account disabling actions.

*Basis.* Splunk native authentication exposes no distinct disabled flag on a local account; access is withdrawn by removing the account's role assignments or by removing the account, and both are modifications to the user object performed through the managed endpoint and recorded in the product's audit trail. The requirement is therefore implementable, with the caveat that the assessor must examine the record of the action the operator actually uses to withdraw access rather than look for a dedicated disable event.

*Citation.* audit.conf.spec:23-29 [auditTrail] queueing; indexes.conf:200 [_audit]; inputs.conf.spec:1497-1506 documenting the _audit index and the audittrail sourcetype; authorize.conf.spec:79 importRoles and authorize.conf.spec:67 [role_<roleName>], the role binding whose removal withdraws access; a search of all 71 specification files for an account disable or deactivate setting returned no account-scoped result (grep -iE 'disable.{0,12}account|account.{0,12}disabl|deactivat' over *.spec in the specification set: hits only in federated.conf.spec:195-204, web-features.conf.spec:180, limits.conf.spec:4494 and inputs.conf.spec:2626, none of which concern user accounts).

*Mechanism.* audit.conf [auditTrail] queueing, with the role-removal or account-removal action recorded to the _audit index (indexes.conf [_audit]); the action itself is a modification through /services/authentication/users or /services/authorization/roles

*Assessment method.* Run as the Splunk service account: splunk btool audit list --debug to establish [auditTrail] queueing. Determine from the administrator which action the site uses to withdraw access from a local account, then test by performing it against a test account and searching the audit trail over that interval for the resulting record. Where authentication is bound to a directory service, the disable action occurs in that service and its audit record is that provider's.

**SRG-APP-000029-AU-000610** — CAT II — Applicable, evidence grade C.

The Central Log Server must automatically audit account removal actions.

*Basis.* Removal of a Splunk local account is performed through the product's managed user endpoint and the action is written to the product's audit trail, under the same configuration surface that governs the other account management audit events. Splunk implements this requirement through its own configuration.

*Citation.* audit.conf.spec:23-29 [auditTrail] queueing; indexes.conf:200 [_audit] in the shipped default index definitions; inputs.conf.spec:1497-1506 documenting the _audit index and the audittrail sourcetype; authorize.conf.spec:463 naming the /services/authentication/users endpoint and authorize.conf.spec:719 the edit_user capability that gates removal.

*Mechanism.* audit.conf [auditTrail] queueing, with account removal recorded to the _audit index (indexes.conf [_audit]); removal is gated by authorize.conf [capability::edit_user]

*Assessment method.* Run as the Splunk service account: splunk btool audit list --debug to establish [auditTrail] queueing, then test by having the administrator remove a test account through the supported interface and searching the audit trail over that interval for the resulting removal record, confirming the acting user, the removed account and the timestamp.

**SRG-APP-000033-WSR-000169** — CAT II — Applicable, evidence grade C.

The web server must enforce approved authorizations for logical access to hosted applications and resources in accordance with applicable access control policies.

*Basis.* This requirement carries the same CCI as SRG-APP-000033-AU-001610 but states the web server objective, that an authorization check be performed before content is served and that possession of a valid certificate not by itself confer access. Splunk Enterprise implements both halves: its web and REST endpoints are gated by the role and capability model, and where client certificates are used for authentication the certificate is mapped to an account whose roles are then evaluated, rather than being accepted as authorization.

*Citation.* web.conf.spec:151 requireClientCert; web.conf.spec:120-131 enableCertBasedUserAuth - "splunkd uses a digital certificate to identify and grant a user access to a Splunk platform instance resource", with web.conf.spec:133 certBasedUserAuthMethod defining how credentials are extracted from the client certificate; authorize.conf.spec:67 [role_<roleName>] and :54 [capability::<capability>] as the authorization model the mapped account is subject to; authentication.conf.spec:351 [roleMap_<authSettings-key>].

*Mechanism.* web.conf [settings] requireClientCert, enableCertBasedUserAuth, certBasedUserAuthMethod; authorize.conf [role_<roleName>] and [capability::<capability>]; authentication.conf [roleMap_<authSettings-key>]

*Assessment method.* Run as the Splunk service account: splunk btool web list --debug | grep -E 'requireClientCert|enableCertBasedUserAuth|certBasedUserAuthMethod' and splunk btool authorize list --debug. Test by authenticating as an account holding a restricted role and requesting a resource outside that role's capability and index scope, confirming the request is refused; where certificate-based authentication is in use, confirm a certificate that authenticates successfully still resolves to a role before access is granted.

**SRG-APP-000065-AU-000240** — CAT II — Applicable, evidence grade C.

The Central Log Server must enforce the limit of three consecutive invalid logon attempts by a user during a 15 minute time period.

*Basis.* Splunk native authentication exposes a failed-logon lockout with a separately settable attempt count, counting window and lockout duration, and the permitted ranges accommodate the three-attempts-in-fifteen-minutes limit this requirement states. The limit applies to accounts authenticated by Splunk itself; where authentication is bound to a directory service the lockout is enforced by that provider, and a role granted the never_lockout capability is exempt, both of which the assessment must account for.

*Citation.* authentication.conf.spec:532 lockoutAttempts - "The number of unsuccessful login attempts that can occur before a user is locked out", minimum 1 maximum 64; authentication.conf.spec:543 lockoutThresholdMins, minimum 1 maximum 120; authentication.conf.spec:514 lockoutUsers; authentication.conf.spec:521 lockoutMins; authentication.conf.spec:437 [splunk_auth]; authorize.conf.spec:867 [capability::never_lockout] - "Allows a user's account to never lockout". A live 10.4.2 instance returns all four keys through splunk btool authentication list --debug, confirming the mechanism is present and readable.

*Mechanism.* authentication.conf [splunk_auth] lockoutUsers, lockoutAttempts, lockoutThresholdMins, lockoutMins

*Assessment method.* Run as the Splunk service account: splunk btool authentication list splunk_auth --debug | grep -iE 'lockout' and read the resolved layer each value comes from rather than inspecting a single file. Then run splunk btool authorize list --debug and identify any role holding never_lockout. Note that authentication.conf.spec:539 and :550 state lockout state applies per search head cluster member and not cluster-wide, so in a clustered deployment the assessment must examine every member.

*Product reference.* SPLK-CL-000060 — confirmed in 10 4 2

**SRG-APP-000080-AU-000010** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured to protect the data sent from hosts and devices from being altered in a way that may prevent the attribution of an action to an individual (or process acting on behalf of an individual).

*Basis.* Splunk Enterprise implements rawdata integrity protection in the index layer, and restricts removal of indexed records: the product's delete command masks events through the index rather than removing rawdata from disk, and protected audit actions remain recorded regardless of per-path audit suppression. The determination is that the product exposes these mechanisms through its own configuration; whether any index carries the setting is current state gathered per instance.

*Citation.* indexes.conf.spec:671 'enableDataIntegrityControl = <boolean>' / 'Whether or not splunkd computes hashes on rawdata slices and stores the hashes for future data integrity checks'. Authorize.conf.spec:590-593 '[capability::delete_by_keyword]' / 'The delete command does not actually delete the raw data on disk. Instead, it masks the data (via the index) from showing up in search results'. Audit.conf.spec:47-62 '[auditconfig:/path]' with 'Protected actions such as delete always remain logged even if the setting omits them'. Line numbers are from the 10.4.2 specification set; existence confirmed readable on a live Splunk 10.4.2 instance (build 33c3bf42cd73) via btool indexes list --debug.

*Mechanism.* indexes.conf, per-index stanza [<index name>], key enableDataIntegrityControl; supporting: authorize.conf [capability::delete_by_keyword]; audit.conf [auditconfig:/path] enabled / disabled

*Assessment method.* splunk btool indexes list --debug, and read enableDataIntegrityControl for every index in scope; verify stored hashes with splunk check-integrity -index <index name>. SPLK-CL-000090 scopes its check to instances carrying the indexer role, so run this at the indexing tier.

*Product reference.* SPLK-CL-000090 — confirmed in 10 4 2

**SRG-APP-000086-AU-000390** — CAT II — Applicable, evidence grade C.

Where multiple log servers are installed in the enclave, each log server must be configured to aggregate log records to a central aggregation server or other consolidated events repository.

*Basis.* A Splunk instance that receives records can forward them onward to a higher-tier aggregation instance through its own outputs.conf, and whether it also retains a local copy is governed by the indexAndForward setting. Whether an enclave holds more than one log server is a site architecture fact and is current state, not a property of the product.

*Citation.* outputs.conf.spec:61 '[tcpout]', :63 'defaultGroup = <comma-separated list>', :123 'server = <comma-separated list>', :72 'indexAndForward = <boolean>' and :1264 '[indexAndForward]'; outputs.conf.spec:541-542 'forwardedindex.<n>.whitelist' / 'forwardedindex.<n>.blacklist' select which internal indexes are forwarded onward. SPLK-CL-000110's fix text names outputs.conf for this purpose and the stanza family exists in 10.4.2. Confirmed readable on the live instance via btool outputs list --debug.

*Mechanism.* outputs.conf [tcpout] defaultGroup, [tcpout:<target_group>] server, indexAndForward and [indexAndForward]; outputs.conf forwardedindex.<n>.whitelist / forwardedindex.<n>.blacklist

*Assessment method.* splunk btool outputs list --debug on every log server in the enclave; confirm the [tcpout] target group resolves to the designated aggregation tier, and confirm with '| tstats count by splunk_server' at the aggregation tier that records from the subordinate servers arrive. Examine indexAndForward to establish whether local retention is intended.

*Product reference.* SPLK-CL-000100, SPLK-CL-000110 — confirmed in 10 4 2

**SRG-APP-000089-AU-000400** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured to retain the DoW-defined attributes of the log records sent by the devices and hosts.

*Basis.* Splunk Enterprise governs which attributes survive ingestion through per-sourcetype props.conf settings, which both derive attributes and, through TRANSFORMS and SEDCMD, can remove them; source attribution attributes are assigned in inputs.conf. The list of required attributes is organizationally defined, but retaining them is product configuration.

*Citation.* props.conf.spec:506 'DATETIME_CONFIG', :533 'TIME_PREFIX', :558 'TIME_FORMAT', :584 'TZ' (date and time attributes); :1190 'EXTRACT-<class>', :1173 'REPORT-<class>', :1353 'FIELDALIAS-<class>', :1401 'EVAL-<fieldname>' (attribute derivation); :1131 'TRANSFORMS-<class>' and :1331 'SEDCMD-<class>' (can remove attributes and must therefore be examined); inputs.conf.spec:60 'host', :93 'index', :113 'sourcetype'; field_filters.conf.spec:32 '[<fieldFilterName>]' and :86 'index' can withhold fields at search time. SPLK-CL-000130's fix text names props.conf, which exists in 10.4.2. Confirmed readable on the live instance via btool props list --debug.

*Mechanism.* props.conf per-sourcetype stanzas: DATETIME_CONFIG, TIME_PREFIX, TIME_FORMAT, TZ, EXTRACT-<class>, REPORT-<class>, FIELDALIAS-<class>, EVAL-<fieldname>, TRANSFORMS-<class>, SEDCMD-<class>; inputs.conf host, index, sourcetype; field_filters.conf [<fieldFilterName>]

*Assessment method.* splunk btool props list --debug and review every TRANSFORMS-<class> and SEDCMD-<class> for attribute removal; splunk btool field_filters list --debug for search-time field suppression; then sample events per sourcetype and confirm each organizationally defined attribute is present in the indexed record.

*Product reference.* SPLK-CL-000130 — confirmed in 10 4 2

**SRG-APP-000089-WSR-000047** — CAT II — Applicable, evidence grade C.

The web server must generate, at a minimum, log records for system startup and shutdown, system access, and system authentication events.

*Basis.* Splunk Web and the splunkd REST tier expose their access and service logs through web.conf and restmap.conf, and the product's authentication and authorization events are produced as audit records whose scope is selectable in audit.conf. Startup and shutdown messages are emitted on splunkd log channels whose levels are set in log.cfg, which sits outside the .conf specification surface and must be examined directly.

*Citation.* web.conf.spec:926 'log.access_file = <filename>' / 'The HTTP access log filename', :931 'log.access_maxsize', :939 'log.access_maxfiles', :946 'log.error_maxsize' (web_service.log), :954 'log.error_maxfiles'. Restmap.conf.spec:138 'includeInAccessLog = <boolean>' / 'Whether to include requests to this endpoint in the splunkd_access.log'. Audit.conf.spec:28-29 '[auditTrail]' / 'queueing', :36 'logging_format = v1|v2|both', :47-62 '[auditconfig:/path]' enabled / disabled. Log.cfg carries 456 category lines on the live 10.4.2 instance and is referenced from the .conf surface only at server.conf.spec:4778, so it is not described by the specification set.

*Mechanism.* web.conf log.access_file, log.access_maxsize, log.access_maxfiles, log.error_maxsize, log.error_maxfiles; restmap.conf per-endpoint includeInAccessLog; audit.conf [auditTrail] queueing and logging_format, [auditconfig:/path] enabled / disabled

*Assessment method.* splunk btool web list --debug and read the log.* keys; splunk btool audit list --debug and read logging_format and any [auditconfig:<path>] suppression; splunk btool restmap list --debug for includeInAccessLog set to false. Then confirm records exist in web_access.log, web_service.log and splunkd.log, and that 'index=_audit action=login*' returns authentication events. SPLK-CL-000130 is mapped here only through CCI-000169 and addresses ingested-record attributes rather than Splunk Web's own logging; the props.conf file it names exists.

*Product reference.* SPLK-CL-000130 — confirmed in 10 4 2

**SRG-APP-000092-WSR-000055** — CAT II — Applicable, evidence grade C.

The web server must initiate session logging upon start up.

*Basis.* Splunk Web's access and service logs are named and bounded through web.conf, and the appserver that writes them is started by splunkd as part of bring-up; the splunkd REST tier's access log inclusion is selectable per endpoint. The appserver's own log channel levels are set in log.cfg, which sits outside the .conf specification surface.

*Citation.* web.conf.spec:926 'log.access_file = <filename>' / 'The HTTP access log filename' / 'Default: web_access.log', :946 'log.error_maxsize = <integer>' / 'The maximum size, in bytes, the web_service.log can be', :55 'appServerPorts' (the appserver listeners splunkd brings up). Restmap.conf.spec:138 'includeInAccessLog = <boolean>'. Log.cfg is present on the live 10.4.2 instance with 456 category lines and is referenced from the .conf surface only at server.conf.spec:4778.

*Mechanism.* web.conf log.access_file, log.error_maxsize, appServerPorts; restmap.conf per-endpoint includeInAccessLog

*Assessment method.* splunk btool web list --debug and read log.access_file, log.error_maxsize and appServerPorts. Then, during an approved maintenance window, restart the instance and compare the timestamp of the first record in web_access.log against the appserver start message in web_service.log and splunkd.log to confirm no gap at the front.

**SRG-APP-000095-WSR-000056** — CAT II — Applicable, evidence grade C.

The web server must produce log records containing sufficient information to establish what type of events occurred.

*Basis.* Splunk Web and the splunkd REST tier write access logs whose records carry the request method, resource and status, which establish the event type for the web tier; the configurable surface is which log file is written, its rotation, and which endpoints are included. The record layout itself is a product property rather than a configuration key, so the assessment examines produced records rather than a format setting.

*Citation.* web.conf.spec:926 'log.access_file = <filename>' / 'The HTTP access log filename', :931 'log.access_maxsize', :939 'log.access_maxfiles', :946 'log.error_maxsize' / 'The maximum size, in bytes, the web_service.log can be'. Restmap.conf.spec:138 'includeInAccessLog = <boolean>' / 'If set to "false", requests do not appear in splunkd_access.log'. A search of the 10.4.2 specification set for an access-log format or layout key returned none, so the field set is fixed by the product; the live instance shows 24 includeInAccessLog entries under btool restmap list --debug.

*Mechanism.* web.conf log.access_file, log.access_maxsize, log.access_maxfiles, log.error_maxsize; restmap.conf per-endpoint includeInAccessLog; props.conf for the splunk_web_access and splunkd_access sourcetypes to extract the request attributes at index time

*Assessment method.* splunk btool web list --debug for the log.* keys and splunk btool restmap list --debug for any endpoint with includeInAccessLog set to false; then exercise the web interface and examine web_access.log, web_service.log and splunkd_access.log records for method, resource and status, confirming with 'index=_internal sourcetype=splunk_web_access | stats count by method, status'.

**SRG-APP-000096-WSR-000057** — CAT II — Applicable, evidence grade C.

The web server must produce log records containing sufficient information to establish when (date and time) events occurred.

*Basis.* Splunk Web's access and service log records carry a timestamp as a fixed property of the product's log layout, and the timestamp recognition applied when those files are ingested into the internal index is governed by props.conf. There is no configuration key that removes the timestamp from the web tier's records.

*Citation.* web.conf.spec:926 'log.access_file = <filename>' and :946 'log.error_maxsize' establish the web tier's access and service logs; a search of the 10.4.2 specification set returned no key controlling the presence or layout of the timestamp field in those records. Props.conf.spec:533 'TIME_PREFIX', :558 'TIME_FORMAT', :584 'TZ' govern recognition of that timestamp at ingest for the splunk_web_access and splunkd_access sourcetypes.

*Mechanism.* web.conf log.access_file and log.error_maxsize; props.conf TIME_PREFIX, TIME_FORMAT, TZ for the splunk_web_access and splunkd_access sourcetypes

*Assessment method.* Exercise the web interface, then examine web_access.log and web_service.log records for a date and time field, and confirm correct recognition at ingest with 'index=_internal sourcetype=splunk_web_access | table _time, _raw | head 20'; splunk btool props list --debug for the timestamp keys applied to those sourcetypes.

**SRG-APP-000097-WSR-000058** — CAT II — Applicable, evidence grade C.

The web server must produce log records containing sufficient information to establish where within the web server the events occurred.

*Basis.* The splunkd REST tier identifies the serving handler per endpoint, and inclusion of each endpoint's requests in the access log is selectable; the appserver's service log attributes records to an emitting component through named log channels. The channel levels are set in log.cfg, which is outside the .conf specification surface and must be examined directly.

*Citation.* restmap.conf.spec:138 'includeInAccessLog = <boolean>' / 'Whether to include requests to this endpoint in the splunkd_access.log', with the per-endpoint stanza families that name the handler, including '[script:<uniqueName>]' / 'Per-endpoint stanza'. Web.conf.spec:946 'log.error_maxsize' / 'The maximum size, in bytes, the web_service.log can be'. Log.cfg on the live 10.4.2 instance carries 456 category lines naming the emitting components and is referenced from the .conf surface only at server.conf.spec:4778.

*Mechanism.* restmap.conf per-endpoint stanzas with includeInAccessLog; web.conf log.error_maxsize and log.error_maxfiles for web_service.log; log.cfg per-channel categories, outside the .conf surface

*Assessment method.* splunk btool restmap list --debug and list every endpoint with includeInAccessLog set to false; examine log.cfg for any audit-, auth- or appserver-related category raised above INFO; then run 'index=_internal sourcetype=splunkd_access | stats count by uri_path' and 'index=_internal sourcetype=splunkd component=* | stats count by component' to confirm the serving component is recoverable.

**SRG-APP-000098-WSR-000059** — CAT II — Applicable, evidence grade C.

The web server must produce log records containing sufficient information to establish the source of events.

*Basis.* Splunk Web's access log records the client address of each request, and web.conf determines whether that address is taken from the immediate peer or from proxy-supplied headers; trusted-proxy settings bound which upstream is believed. The determination is that the product exposes these mechanisms.

*Citation.* web.conf.spec:926 'log.access_file = <filename>' / 'The HTTP access log filename'; :1071-1079 'tools.proxy.on = <boolean>' / 'If set to "false", the instance relies on its own internal HTTP server settings and the immediate client's HTTP headers for the information needed for access request logging'; :852 'trustedIP = <ip_addresses>' / 'IP addresses of the authenticating proxy (trusted IP)'; :783 'remoteUser = <http_header_string>'. Restmap.conf.spec:138 'includeInAccessLog' for the REST tier.

*Mechanism.* web.conf log.access_file, tools.proxy.on, tools.proxy.base, trustedIP; restmap.conf includeInAccessLog

*Assessment method.* splunk btool web list --debug and read tools.proxy.on, tools.proxy.base and trustedIP; then request a page and confirm the client address recorded in web_access.log matches the originating client, with 'index=_internal sourcetype=splunk_web_access | stats count by clientip'. Note that tools.proxy.on carries a code default and may not appear in any conf layer, so btool can return nothing for it; examine web.conf directly or read the value from the REST properties endpoint.

**SRG-APP-000098-WSR-000060** — CAT II — Applicable, evidence grade C.

A web server, behind a load balancer or proxy server, must produce log records containing the client IP information as the source and destination and not the load balancer or proxy IP information with each event.

*Basis.* This requirement's check text carries the clause 'If the web server is not sitting behind a proxy server, this finding is NA', but that condition is a property of a particular deployment's network architecture rather than of Splunk Enterprise as a product, and Splunk Web is supported behind a reverse proxy, so the condition cannot be established as holding at every site. The product implements the requirement through a dedicated setting that makes it take the client identity from proxy-supplied headers.

*Citation.* web.conf.spec:1071-1029 'tools.proxy.on = <boolean>' / 'Whether or not the Splunk platform instance is behind a reverse proxy server' / 'If set to "true", the instance assumes that it is behind a reverse proxy and uses HTTP header information from the proxy to log access requests' / 'All of the instance's HTTP services will use information from "X-Forwarded-*", "Front-End-Https", and "X-Url-Scheme" headers, where available, to override what it receives from proxied requests', with :1086 'tools.proxy.base = <scheme>://<URL>' required when it is true. For data arriving through a proxy rather than browser traffic, inputs.conf.spec:2207 'connection_host = [ip|dns|proxied_ip|none]' and :2213 'proxied_ip checks whether an X-Forwarded-For header was sent'. The inventory records has_own_na_clause as false for this requirement, so grade B was not available and was not used.

*Mechanism.* web.conf tools.proxy.on with tools.proxy.base, and trustedIP to bound the trusted upstream; inputs.conf connection_host = proxied_ip on the HTTP Event Collector stanza

*Assessment method.* Establish from the network architecture whether a load balancer or reverse proxy fronts Splunk Web; where one does, read tools.proxy.on and tools.proxy.base from web.conf directly (tools.proxy.on carries a code default and may be absent from every conf layer, so btool can return nothing for it), then request a page through the proxy and confirm web_access.log records the client address rather than the proxy address. For HTTP Event Collector inputs behind a proxy, splunk btool inputs list --debug and read connection_host.

**SRG-APP-000099-WSR-000061** — CAT II — Applicable, evidence grade C.

The web server must produce log records that contain sufficient information to establish the outcome (success or failure) of events.

*Basis.* Splunk Web and the splunkd REST tier record an HTTP status code with each request, which establishes the outcome for the web tier; the configurable surface is which log is written and which endpoints are included, and extraction of the status attribute at ingest is governed by props.conf.

*Citation.* web.conf.spec:926 'log.access_file = <filename>' / 'The HTTP access log filename', :946 'log.error_maxsize' for web_service.log. Restmap.conf.spec:138 'includeInAccessLog = <boolean>' / 'If set to "false", requests do not appear in splunkd_access.log'. Props.conf.spec:1190 'EXTRACT-<class>' and :1173 'REPORT-<class>' for extraction of the status attribute from those sourcetypes. A search of the 10.4.2 specification set returned no key that removes the status field from the access-log layout.

*Mechanism.* web.conf log.access_file and log.error_maxsize; restmap.conf per-endpoint includeInAccessLog; props.conf EXTRACT-<class> and REPORT-<class> for the splunk_web_access and splunkd_access sourcetypes

*Assessment method.* Exercise both a successful and a rejected request against the web interface, then confirm both appear in web_access.log with distinguishable status codes, and confirm extraction with 'index=_internal sourcetype=splunk_web_access | stats count by status'; splunk btool restmap list --debug for endpoints excluded from the access log.

**SRG-APP-000100-WSR-000064** — CAT II — Applicable, evidence grade C.

The web server must produce log records containing sufficient information to establish the identity of any user/subject or process associated with an event.

*Basis.* Splunk Web's access log records the authenticated user for authenticated requests, and where an authenticating proxy fronts the web tier, web.conf names the header that carries the username and bounds which upstream is trusted to supply it. The determination is that the product exposes these mechanisms.

*Citation.* web.conf.spec:926 'log.access_file = <filename>' / 'The HTTP access log filename'; :783 'remoteUser = <http_header_string>' / 'Remote user HTTP header sent by the authenticating proxy server', with :822 'remoteUserMatchExact = [0 | 1]' and :852 'trustedIP = <ip_addresses>' / 'Splunk Web verifies it is receiving data from the proxy host for all SSO requests'. Audit.conf.spec:28-29 '[auditTrail]' / 'queueing' for the corresponding audit record. Restmap.conf.spec:138 'includeInAccessLog' for the REST tier.

*Mechanism.* web.conf log.access_file, remoteUser, remoteUserMatchExact, trustedIP; audit.conf [auditTrail] queueing and logging_format; restmap.conf includeInAccessLog

*Assessment method.* Sign in to the web interface and confirm the user attribute is populated for the resulting authenticated requests in web_access.log, with 'index=_internal sourcetype=splunk_web_access | stats count by user'; splunk btool web list --debug and read remoteUser, remoteUserMatchExact and trustedIP where an authenticating proxy is in path.

**SRG-APP-000108-WSR-000166** — CAT II — Applicable, evidence grade C.

The web server must use a logging mechanism that is configured to alert the ISSO and SA in the event of a processing failure.

*Basis.* Splunk Enterprise detects degradation and failure of its own indexing, queueing and forwarding through the health reporter, which raises a configurable alert when a monitored feature crosses a color threshold, and delivers notifications through its alert actions; an operator-authored scheduled search provides a second path. The designation of the ISSO and SA as recipients is an organizational input; the delivery is product configuration.

*Citation.* health.conf.spec:32 '[health_reporter]' with :88 'alert.disabled = [0|1]', :93 'alert.actions = <string>', :96 'alert.min_duration_sec', :101 'alert.threshold_color = [yellow|red]', :105 'alert.suppress_period'; :141 '[feature:*]' with per-feature :176 'alert.disabled' and :188 'alert.threshold_color', and :185-196 'indicator:<indicator name>' thresholds. Alert_actions.conf.spec:176 '[email]' with :186 'to = <string>'. Savedsearches.conf.spec:44 'search = <string>', :86 'enableSched', :92 'cron_schedule', :305 'alert_condition = <search string>', :335 'action.email', :339 'action.email.to'. Confirmed readable on the live instance via btool health list --debug and btool alert_actions list --debug.

*Mechanism.* health.conf [health_reporter] and [feature:<name>] with alert.disabled, alert.actions, alert.threshold_color, alert.min_duration_sec, alert.suppress_period; alert_actions.conf [email] to; savedsearches.conf search, enableSched, cron_schedule, alert_condition, action.email, action.email.to

*Assessment method.* splunk btool health list --debug and read alert.disabled and alert.actions for the health reporter and each monitored feature; splunk btool alert_actions list --debug for the [email] recipient list and mail server; splunk btool savedsearches list --debug for any operator-authored failure alert. Then confirm the recipient list matches the ISSO and SA of record, and on a non-production instance induce a blocked-queue condition and confirm the notification is delivered.

**SRG-APP-000116-WSR-000066** — CAT II — Applicable, evidence grade C.

The web server must use the internal system clock to generate time stamps for log records.

*Basis.* Splunk Enterprise performs its own web-tier logging and exposes the access and error log set through configuration; the product offers no alternate time source for those records, and the time stamp applied to the indexed copy is governed by the same product time-stamping settings as any other input.

*Citation.* web.conf.spec:871 log.access_file, :876 log.access_maxsize, :884 log.access_maxfiles; props.conf.spec:502 DATETIME_CONFIG with the CURRENT value. Confirmed readable on 10.4.2 with btool web list settings --debug, which returns log.access_file.

*Mechanism.* web.conf [settings] log.access_file names the web access log; props.conf DATETIME_CONFIG and TZ govern the time stamp on the indexed copy

*Assessment method.* Generate a Splunk Web request, then compare the resulting entry in the log named by web.conf log.access_file against the host clock reading; record the settings with `splunk btool web list settings --debug` and `splunk btool props list --debug`.

**SRG-APP-000118-AU-000100** — CAT II — Applicable, evidence grade C.

The Central Log Server must protect audit information from any type of unauthorized read access.

*Basis.* Splunk writes its own audit records to an internal index and presents them through its search interface, so by the requirement's own discussion the application is accountable for read access to audit data; role-based index restriction is the product mechanism. File permissions on the installation directory, which the referenced product STIG rule addresses, are a host operating system baseline matter and reach only the on-disk copy.

*Citation.* authorize.conf.spec:67 [role_<roleName>], :282 srchIndexesDefault, :292 srchIndexesAllowed, :297 srchIndexesDisallowed, :150 srchFilter, :953 [capability::search], :447 [capability::admin_all_objects]. The _audit index stanza is present in indexes.conf on 10.4.2 (btool indexes list _audit --debug).

*Mechanism.* authorize.conf [role_<roleName>] srchIndexesAllowed, srchIndexesDefault, srchIndexesDisallowed and srchFilter, with [capability::search] and [capability::admin_all_objects]

*Assessment method.* Run `splunk btool authorize list --debug` as the Splunk service account and record srchIndexesAllowed, srchIndexesDefault, srchIndexesDisallowed and srchFilter for every role, together with the roles holding the search and admin_all_objects capabilities; compare against the index holding audit records.

*Product reference.* SPLK-CL-000190 — withdrawn

**SRG-APP-000118-WSR-000068** — CAT II — Applicable, evidence grade C.

Web server log files must only be accessible by privileged users.

*Basis.* The product indexes its own web-tier access and error logs into an internal index and gates search access to that index by role, and gates the views that display those records by object access control list. The permissions on the log files themselves are set by the host operating system baseline, so that portion is inherited while the application-layer portion applies.

*Citation.* authorize.conf.spec:292 srchIndexesAllowed, :297 srchIndexesDisallowed, :282 srchIndexesDefault; default.meta.spec:41 and :47 access = read : [...], write : [...]; web.conf.spec:871 log.access_file. Confirmed readable on 10.4.2 with btool web list settings --debug and btool authorize list --debug.

*Mechanism.* authorize.conf [role_<roleName>] srchIndexesAllowed and srchIndexesDisallowed over the internal index holding web-tier logs; default.meta [views] access read list; web.conf [settings] log.access_file

*Assessment method.* Run `splunk btool authorize list --debug` for the role grants over the internal index holding web-tier logs, `splunk btool web list settings --debug` for the log set, and examine the metadata access lists on the views that present those records.

*Product reference.* SPLK-CL-000190 — withdrawn

**SRG-APP-000119-AU-000110** — CAT II — Applicable, evidence grade C.

The Central Log Server must protect audit information from unauthorized modification.

*Basis.* Indexed records are not rewritable through the product; the one application path that alters what a search returns from an audit index requires both the delete_by_keyword capability and the index named in deleteIndexesAllowed, and changes to the audit configuration require the change_audit capability. Splunk 10.4.2 exposes no cryptographic audit-record signing, so role restriction is the application-layer integrity mechanism and the determination rests on it.

*Citation.* authorize.conf.spec:495 [capability::delete_by_keyword], :309 deleteIndexesAllowed with the note at :311 that it must be used together with that capability, :483 [capability::change_audit]. Audit.conf.spec in 10.4.2 contains a single stanza, [auditTrail], with the single key queueing; a search of every .conf.spec file in the specification set for an audit signature or audit key setting returns no match.

*Mechanism.* authorize.conf [capability::delete_by_keyword] with [role_<roleName>] deleteIndexesAllowed, and [capability::change_audit] over the audit configuration

*Assessment method.* Run `splunk btool authorize list --debug` and record which roles hold delete_by_keyword and change_audit and which indexes appear in deleteIndexesAllowed for those roles; run `splunk btool audit list --debug` for the audit trail settings.

*Product reference.* SPLK-CL-000190 — withdrawn

**SRG-APP-000119-WSR-000069** — CAT II — Applicable, evidence grade C.

The log information from the web server must be protected from unauthorized modification.

*Basis.* The product gates modification of the indexed copy of its web-tier logs by capability and index grant, and bounds the on-disk rotation set through web server log settings. The permissions on the log files themselves are set by the host operating system baseline, so that portion is inherited while the application-layer portion applies.

*Citation.* authorize.conf.spec:495 [capability::delete_by_keyword], :309 deleteIndexesAllowed, :483 [capability::change_audit]; web.conf.spec:876 log.access_maxsize, :884 log.access_maxfiles; default.meta.spec:17-18 (write access to the object plus read access to the app required to modify).

*Mechanism.* authorize.conf [capability::delete_by_keyword] with [role_<roleName>] deleteIndexesAllowed over the internal index holding web-tier logs; default.meta access write list; web.conf [settings] log.access_maxfiles and log.access_maxsize

*Assessment method.* Run `splunk btool authorize list --debug` for the delete and audit-change grants and `splunk btool web list settings --debug` for the log rotation set; examine the metadata access lists on the objects that present web-tier log records.

*Product reference.* SPLK-CL-000190 — withdrawn

**SRG-APP-000120-AU-000120** — CAT II — Applicable, evidence grade C.

The Central Log Server must protect audit information from unauthorized deletion.

*Basis.* Deletion of audit records through the application requires a capability and a per-index grant that the product exposes per role. Separately, index aging is a product setting and the specification states that records are deleted at freeze when no archive script is given, so the archive setting forms part of the deletion-protection determination.

*Citation.* authorize.conf.spec:495 [capability::delete_by_keyword], :309 deleteIndexesAllowed, :447 [capability::admin_all_objects]; indexes.conf.spec:684 frozenTimePeriodInSecs, which states that data is deleted when rolled to frozen if no coldToFrozenScript is specified, :713 coldToFrozenScript, :792 coldToFrozenDir.

*Mechanism.* authorize.conf [capability::delete_by_keyword] with [role_<roleName>] deleteIndexesAllowed; indexes.conf frozenTimePeriodInSecs with coldToFrozenDir or coldToFrozenScript

*Assessment method.* Run `splunk btool authorize list --debug` for the roles holding delete_by_keyword and their deleteIndexesAllowed grants, and `splunk btool indexes list --debug` for frozenTimePeriodInSecs, coldToFrozenDir and coldToFrozenScript on every index holding audit records.

*Product reference.* SPLK-CL-000190 — withdrawn

**SRG-APP-000120-WSR-000070** — CAT II — Applicable, evidence grade C.

The log information from the web server must be protected from unauthorized deletion.

*Basis.* The product gates deletion of the indexed copy of its web-tier logs by capability and per-index grant, and the rolled on-disk set is bounded by product settings rather than removed arbitrarily. The permissions on the log files themselves are set by the host operating system baseline, so that portion is inherited while the application-layer portion applies.

*Citation.* authorize.conf.spec:495 [capability::delete_by_keyword], :309 deleteIndexesAllowed; web.conf.spec:884 log.access_maxfiles, :899 log.error_maxfiles; server.conf.spec:1680 [stderr_log_rotation] with BackupIndex at :1694; default.meta.spec:26-27 (write access to the app required to add or remove an object).

*Mechanism.* authorize.conf [capability::delete_by_keyword] with [role_<roleName>] deleteIndexesAllowed; web.conf [settings] log.access_maxfiles and log.error_maxfiles; default.meta access write list

*Assessment method.* Run `splunk btool authorize list --debug` for the delete grants over the internal index holding web-tier logs and `splunk btool web list settings --debug` for log.access_maxfiles and log.error_maxfiles.

*Product reference.* SPLK-CL-000190 — withdrawn

**SRG-APP-000121-AU-000130** — CAT II — Applicable, evidence grade C.

The Central Log Server must protect audit tools from unauthorized access.

*Basis.* The audit tools in this product are its search commands, saved searches, reports and views, each of which is a configuration object carrying its own access control list, with the REST endpoints that reach them gated by capability. Access to the tools is therefore determined by product configuration and the requirement applies to the application.

*Citation.* default.meta.spec:41, :47 and :53 access = read : [<roles>], write : [<roles>], with the rule at :10-14 that every layer must permit read access; authorize.conf.spec:458 [capability::list_all_objects], :912 [capability::run_custom_command], :903 [capability::rtsearch], :946 [capability::schedule_search], :447 [capability::admin_all_objects]; restmap.conf.spec:112 capability.<post|delete|get|put>; commands.conf.spec:40 custom command stanza with filename at :68.

*Mechanism.* default.meta [views], [savedsearches] and per-object stanzas with access = read : [<roles>], write : [<roles>]; authorize.conf [capability::list_all_objects], [capability::run_custom_command], [capability::rtsearch], [capability::schedule_search]; restmap.conf capability.<method>

*Assessment method.* Enumerate the metadata access lists on the apps, categories and objects that hold the audit reports, views and custom commands; run `splunk btool authorize list --debug` for the roles holding list_all_objects, run_custom_command, rtsearch and schedule_search, and `splunk btool restmap list --debug` for the capability gates on the reachable endpoints.

*Product reference.* SPLK-CL-000190 — withdrawn

**SRG-APP-000122-AU-000140** — CAT II — Applicable, evidence grade C.

The Central Log Server must protect audit tools from unauthorized modification.

*Basis.* Modification of a saved search, report, view or custom command requires write access in that object's metadata access list together with the corresponding editing capability, both of which are product configuration. The requirement therefore applies to the application.

*Citation.* default.meta.spec:17-22 (write access to the object plus read access to the app and the generic category required in order to modify), :41, :47; authorize.conf.spec:454 [capability::edit_own_objects], :447 [capability::admin_all_objects], :730 [capability::edit_view_html], :650 [capability::edit_search_scheduler], :653 [capability::edit_search_schedule_priority]; restmap.conf.spec:112 capability.<post|delete|get|put>.

*Mechanism.* default.meta access write list on the object, its app and its category; authorize.conf [capability::edit_own_objects], [capability::admin_all_objects], [capability::edit_view_html], [capability::edit_search_scheduler]; restmap.conf capability.post and capability.put

*Assessment method.* Record the write lists in the metadata for the audit reports, views and custom commands, and run `splunk btool authorize list --debug` for the roles holding edit_own_objects, admin_all_objects, edit_view_html and edit_search_scheduler; attempt an edit as a non-privileged role and confirm it is refused.

*Product reference.* SPLK-CL-000190 — withdrawn

**SRG-APP-000123-AU-000150** — CAT II — Applicable, evidence grade C.

The Central Log Server must protect audit tools from unauthorized deletion.

*Basis.* Removal of an audit tool object requires write access to the containing app in that object's metadata, as the metadata specification states, together with an object-administration capability; both are product configuration, so the requirement applies to the application.

*Citation.* default.meta.spec:26-28 (write access to the app required for an attempt to add or remove an object), :41; authorize.conf.spec:447 [capability::admin_all_objects], :454 [capability::edit_own_objects], :885 [capability::rest_apps_management]; restmap.conf.spec:112 capability.<post|delete|get|put>.

*Mechanism.* default.meta access write list on the containing app; authorize.conf [capability::admin_all_objects], [capability::edit_own_objects], [capability::rest_apps_management]; restmap.conf capability.delete

*Assessment method.* Record the app-level write lists in the metadata for the apps holding audit tools, and run `splunk btool authorize list --debug` for the roles holding admin_all_objects, edit_own_objects and rest_apps_management; attempt a removal as a non-privileged role and confirm it is refused.

*Product reference.* SPLK-CL-000190 — withdrawn

**SRG-APP-000125-WSR-000071** — CAT II — Applicable, evidence grade C.

The log data and records from the web server must be backed up onto a different system or media.

*Basis.* The product indexes its own web-tier log records, so the same native off-load and archive settings that apply to any index reach those records, and the product can additionally forward them to a separate instance. The requirement is therefore met through product configuration.

*Citation.* indexes.conf.spec:543 remotePath, :792 coldToFrozenDir, :713 coldToFrozenScript; outputs.conf.spec:121 [tcpout:<target_group>] with server at :123; server.conf.spec:2929 replication_factor. Confirmed on 10.4.2: a [tcpout] stanza is present in outputs.conf and coldToFrozenDir and maxTotalDataSizeMB are present in the indexes.conf default stanza.

*Mechanism.* indexes.conf remotePath, coldToFrozenDir and coldToFrozenScript over the internal index holding web-tier logs; outputs.conf [tcpout:<target_group>] server; server.conf [clustering] replication_factor

*Assessment method.* Run `splunk btool indexes list --debug` for the archive and remote-path settings on the internal index holding web-tier logs and `splunk btool outputs list --debug` for the forwarding target groups; confirm the destination is a different system or medium from the one being logged.

*Product reference.* SPLK-CL-000250 — no reference

**SRG-APP-000131-WSR-000051** — CAT II — Applicable, evidence grade C.

All web server files must be verified for their integrity (e.g., checksums and hashes) before becoming part of the production web server.

*Basis.* Splunk exposes a native integrity verification mechanism that validates the files delivered by the running release against the release manifest at startup and on a recurring interval, including detection of files present in the binary and library directories that the manifest does not list. The product also records a checksum of the package an app was installed from, and can compute hashes over indexed rawdata slices. The requirement is therefore implementable and assessable within the application. Pre-install hash validation of the vendor-supplied product package itself is performed by the host operating system package management baseline, which an assessment should record as a dependency rather than as the application determination.

*Citation.* limits.conf.spec:4450-4480 ('installed_files_integrity = enabled | log_only | disabled'; 'The source of truth for the files that should be present is the manifest file'; installed_files_integrity_interval at :4468; installed_files_anomalous_integrity_interval at :4475). App.conf.spec:158 ('install_source_checksum = <string>'). Indexes.conf.spec:594 ('enableDataIntegrityControl = <boolean>'). Presence on a live Splunk 10.4.2 instance (build 33c3bf42cd73) confirmed: btool limits list --debug returns installed_files_integrity, and the release manifest file named by the specification text is present in the installation root.

*Mechanism.* limits.conf [system_checks] installed_files_integrity, installed_files_integrity_interval, installed_files_anomalous_integrity_interval; app.conf [install] install_source_checksum; indexes.conf enableDataIntegrityControl

*Assessment method.* Run, as the Splunk service account: splunk btool limits list system_checks --debug; splunk btool app list --debug; splunk btool indexes list --debug. Examine installed_files_integrity, the recorded install_source_checksum of each installed app, and enableDataIntegrityControl per index. Corroborate with the host package manager's signature and checksum verification setting.

**SRG-APP-000141-AU-000090** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured to disable non-essential capabilities.

*Basis.* Splunk exposes a disable setting for each major component it ships: apps and add-ons carry an install state, the KV Store process, Splunk Web and distributed search each carry a disable setting, individual inputs carry a disable setting, and Splunk Web features are toggled individually. Non-essential capability is therefore removable through the application's own configuration, and the requirement is assessed against which components remain enabled relative to documented mission need.

*Citation.* app.conf.spec:121-129 ([install] state = disabled | enabled, state_change_requires_restart); server.conf.spec:5232-5238 ([kvstore] disabled); web.conf.spec:23-27 (startwebserver = [0 | 1]); web-features.conf.spec holds 20 [feature:<name>] stanzas (counted) spanning :19 to :433; distsearch.conf.spec:29-36 ([distributedSearch] disabled); inputs.conf.spec:1486, :1632, :2010, :2258, :2335 (disabled). Presence on a live Splunk 10.4.2 instance confirmed by btool reads of server, web, app, inputs and distsearch.

*Mechanism.* app.conf [install] state = disabled | enabled; server.conf [kvstore] disabled; web.conf [settings] startwebserver; web-features.conf [feature:<name>] toggles; distsearch.conf [distributedSearch] disabled; inputs.conf per-input disabled

*Assessment method.* Run, as the Splunk service account: splunk btool app list --debug; splunk btool server list kvstore --debug; splunk btool web list settings --debug; splunk btool web-features list --debug; splunk btool inputs list --debug; splunk btool distsearch list --debug. Reconcile each enabled component against the documented mission need recorded in the system security plan.

*Product reference.* SPLK-CL-000300 — withdrawn

**SRG-APP-000141-WSR-000015** — CAT II — Applicable, evidence grade C.

The web server must not perform user management for hosted applications.

*Basis.* Splunk maintains a native user store, but the product exposes a single setting that delegates authentication and user management to an enterprise directory or identity provider, with mapping from external groups onto Splunk roles. Splunk apps do not carry independent user stores; they share the instance's identity layer, so the hosted-application user management the requirement prohibits is governed by the instance authentication type. The requirement is implementable in the application and is assessed against that setting.

*Citation.* authentication.conf.spec:26-44 ([authentication] authType, authTypePreferredForUserCollision, authSettings); :351 ([roleMap_<authSettings-key>]); :1230 ([roleMap_<saml-authSettings-key>]); :1330 ([roleMap_proxySSO]). Presence on a live Splunk 10.4.2 instance confirmed: btool authentication list --debug returns authType.

*Mechanism.* authentication.conf [authentication] authType = [Splunk|LDAP|Scripted|SAML|ProxySSO] with authSettings, and [roleMap_<authSettings-key>], [roleMap_<saml-authSettings-key>], [roleMap_proxySSO]

*Assessment method.* Run, as the Splunk service account: splunk btool authentication list --debug. Examine authType, authSettings and the role maps, and confirm that no installed app maintains a separate account store.

*Product reference.* SPLK-CL-000300 — withdrawn

**SRG-APP-000141-WSR-000075** — CAT II — Applicable, evidence grade C.

The web server must only contain services and functions necessary for operation.

*Basis.* The product is delivered as a set of components, each of which carries a configuration setting that deactivates it: apps and add-ons, data inputs, forwarding outputs, the KV Store process, Splunk Web and distributed search. Deactivation does not require removal of the installed package. The requirement is therefore implementable through the application's own configuration, and the assessment compares the enabled component set against documented operational need.

*Citation.* app.conf.spec:121-124 ([install] state), :154 (allows_disable); inputs.conf.spec:1486, :1632, :2010 (disabled); server.conf.spec:5234 ([kvstore] disabled); web.conf.spec:23 (startwebserver); distsearch.conf.spec:36 ([distributedSearch] disabled); outputs.conf.spec:201 (disabled). Presence on a live Splunk 10.4.2 instance confirmed by btool reads of app, inputs, server, web, distsearch and outputs.

*Mechanism.* app.conf [install] state = disabled | enabled and allows_disable; inputs.conf per-input disabled; server.conf [kvstore] disabled; web.conf [settings] startwebserver; distsearch.conf [distributedSearch] disabled; outputs.conf disabled

*Assessment method.* Run, as the Splunk service account: splunk btool app list --debug; splunk btool inputs list --debug; splunk btool outputs list --debug; splunk btool server list --debug; splunk btool web list settings --debug. Enumerate every enabled component and reconcile each against the documented operational need.

*Product reference.* SPLK-CL-000300 — withdrawn

**SRG-APP-000141-WSR-000076** — CAT II — Applicable, evidence grade C.

The web server must not be a proxy server.

*Basis.* Splunk is not a general-purpose forward or reverse proxy, and the specification set contains no listener stanza that forwards arbitrary client requests to third-party destinations. The product does, however, expose two bounded proxy paths that an assessment must examine: Splunk Web proxies requests to the instance's own management interface, with a setting that limits that path to read operations, and a REST stanza proxies the applications browser to the remote applications repository. The product's [proxyConfig] stanza makes splunkd a proxy client, not a proxy server, and the tools.proxy settings declare that the instance sits behind a reverse proxy. Because named settings bound the product's proxying behavior, the requirement applies and is assessed against them rather than dismissed.

*Citation.* web.conf.spec:371-378 ('enable_proxy_write = <boolean>'; 'Indicates if the /splunkd proxy endpoint allows POST operations'), :1016-1031 (tools.proxy.on - 'Whether or not the Splunk platform instance is behind a reverse proxy server'; tools.proxy.base); server.conf.spec:1201-1268 ([proxyConfig] http_proxy at :1206, https_proxy at :1211, proxy_rules at :1217, no_proxy at :1241 - 'splunkd sends all HTTP requests through the proxy server'); restmap.conf.spec:486 ([proxy:appsbrowser]); server.conf.spec:1734 (allowInternetAccess).

*Mechanism.* web.conf [settings] enable_proxy_write, tools.proxy.on, tools.proxy.base; server.conf [proxyConfig] http_proxy, https_proxy, proxy_rules, no_proxy; server.conf [applicationsManagement] allowInternetAccess; restmap.conf [proxy:appsbrowser]

*Assessment method.* Run, as the Splunk service account: splunk btool web list settings --debug; splunk btool server list --debug; splunk btool restmap list --debug. Examine enable_proxy_write, tools.proxy.on and [applicationsManagement] allowInternetAccess, then enumerate the instance's listening sockets and confirm none forwards requests to third-party destinations.

*Product reference.* SPLK-CL-000300 — withdrawn

**SRG-APP-000141-WSR-000077** — CAT II — Applicable, evidence grade C.

The web server must provide install options to exclude the installation of documentation, sample code, example applications, and tutorials.

*Basis.* Splunk delivers pre-installed apps, some of which carry sample content, example searches and tutorial material. The product exposes a per-app install state and a visibility setting by which such an app is deactivated and hidden without removing the installed tree, and the app directory can be removed outright. The requirement's second element - an install-time option to exclude these components - is assessed against the same per-app surface, because the product installer offers no component selection; whether any such content remains present at a given instance is a current-state result gathered by the assessment.

*Citation.* app.conf.spec:121-129 ([install] state = disabled | enabled, state_change_requires_restart), :154 (allows_disable = <boolean>), :284-287 ([ui] is_visible = <boolean>). Presence on a live Splunk 10.4.2 instance confirmed: btool app list --debug returns the install and ui stanzas.

*Mechanism.* app.conf [install] state = disabled | enabled and allows_disable; app.conf [ui] is_visible

*Assessment method.* Run, as the Splunk service account: splunk btool app list --debug. Enumerate installed apps with their install state and visibility, then inventory the app directories for documentation, sample code, example applications and tutorial content.

*Product reference.* SPLK-CL-000300 — withdrawn

**SRG-APP-000141-WSR-000078** — CAT II — Applicable, evidence grade C.

Web server accounts not used by installed features (i.e., tools, utilities, specific services, etc.) must not be created and must be deleted when the web server feature is uninstalled.

*Basis.* Splunk's own configuration creates no per-feature service accounts. The accounts this requirement reaches are the native Splunk users and the roles bound to them, which the product exposes through its authentication and authorization configuration, plus the single administrative account established from the installation seed stanza. The requirement is therefore assessable against the application's own account inventory, where each account is reconciled to an installed feature or a named person. The operating system service account under which the product runs belongs to the host baseline.

*Citation.* authentication.conf.spec:26-44 ([authentication] authType, authSettings); user-seed.conf.spec ([user_info] USERNAME, PASSWORD, HASHED_PASSWORD; 'Currently, only one user can be configured with user-seed.conf'); authorize.conf.spec:67 ([role_<roleName>]), :79 (importRoles). Presence on a live Splunk 10.4.2 instance confirmed by btool reads of authentication and authorize.

*Mechanism.* authentication.conf [authentication] authType and the native user store; user-seed.conf [user_info] USERNAME; authorize.conf [role_<roleName>] and importRoles

*Assessment method.* Enumerate the native user store through the authentication/users REST endpoint. Run, as the Splunk service account: splunk btool authorize list --debug; splunk btool authentication list --debug. Reconcile each account to an installed feature or a named person and identify any account bound to a feature that is not installed.

*Product reference.* SPLK-CL-000300 — withdrawn

**SRG-APP-000141-WSR-000080** — CAT II — Applicable, evidence grade C.

The web server must provide install options to exclude installation of utility programs, services, plug-ins, and modules not necessary for operation.

*Basis.* Utility programs, plug-ins and modules reach a Splunk instance as apps and add-ons, as custom search commands, and as data inputs, and each of those is a named configuration stanza that the product permits to be disabled or removed. The requirement's install-time exclusion element is assessed against the same surface, because the product installer offers no component selection; deactivation and removal after installation are both available through configuration.

*Citation.* app.conf.spec:121-124, :154; commands.conf.spec:40 ([<STANZA_NAME>]), :53 (type), :68 (filename); inputs.conf.spec:1486, :1632, :2010 (disabled); server.conf.spec:5234 ([kvstore] disabled); web-features.conf.spec holds 20 [feature:<name>] stanzas. Presence on a live Splunk 10.4.2 instance confirmed by btool reads of app, inputs and server.

*Mechanism.* app.conf [install] state = disabled | enabled and allows_disable; commands.conf [<STANZA_NAME>] with filename and type; inputs.conf per-input disabled; server.conf [kvstore] disabled; web-features.conf [feature:<name>] toggles

*Assessment method.* Run, as the Splunk service account: splunk btool app list --debug; splunk btool commands list --debug; splunk btool inputs list --debug; splunk btool web-features list --debug. Reconcile each installed app, custom command and input against the documented operational need.

*Product reference.* SPLK-CL-000300 — withdrawn

**SRG-APP-000141-WSR-000081** — CAT II — Applicable, evidence grade C.

The web server must have Multipurpose Internet Mail Extensions (MIME) that invoke OS shell programs disabled.

*Basis.* Splunk's static file handler maps a filename extension to a Content-Type response header only; the specification set records no mapping from a MIME type to an external interpreter or shell, so the literal MIME vector named in the title is absent from the product. The requirement's finding condition is broader - whether a user of the Splunk instance can invoke operating system programs - and Splunk does expose that, through scripted alert actions, scripted inputs, custom search commands and scripted REST handlers. Each of those paths is gated by a named capability, so the requirement applies and is assessed against those capability assignments and script stanzas. Treating this requirement as not applicable on the narrow MIME reading would leave the product's actual program-invocation paths unassessed.

*Citation.* server.conf.spec:1653-1670 ([mimetype-extension-map]; '<file-extension> = <MIME-type>' instructs the static file server to mark files with a Content-Type header, with no handler program named); authorize.conf.spec:638 ([capability::edit_scripted] - 'Lets a user create and edit scripted inputs'), :912 ([capability::run_custom_command]), :924 ([capability::run_sendalert]), :927 ([capability::run_debug_commands]); alert_actions.conf.spec:517 ([script]); savedsearches.conf.spec:403-407 (action.script, action.script.filename); commands.conf.spec:53 (type), :68 (filename); restmap.conf.spec:144-193 ([script:<uniqueName>], scripttype, handler, script).

*Mechanism.* authorize.conf [capability::edit_scripted], [capability::run_custom_command], [capability::run_sendalert], [capability::run_debug_commands]; alert_actions.conf [script]; savedsearches.conf action.script and action.script.filename; commands.conf filename and type; restmap.conf [script:<uniqueName>] with script, scripttype and handler

*Assessment method.* Run, as the Splunk service account: splunk btool authorize list --debug; splunk btool server list mimetype-extension-map --debug; splunk btool commands list --debug; splunk btool restmap list --debug; splunk btool alert_actions list --debug; splunk btool savedsearches list --debug. Enumerate roles holding the script-execution capabilities and every script stanza present, and confirm no non-administrative role can invoke an operating system program.

*Product reference.* SPLK-CL-000300 — withdrawn

**SRG-APP-000141-WSR-000082** — CAT II — Applicable, evidence grade C.

The web server must allow the mappings to unused and vulnerable scripts to be removed.

*Basis.* Every script mapping in Splunk is a named configuration stanza: a custom search command, a scripted REST endpoint, or a script alert action. Each mapping is removed by deleting its stanza, or deactivated by disabling the app that carries it. The product therefore permits mappings to unused scripts to be removed through its own configuration, which is what this requirement asks of the product.

*Citation.* commands.conf.spec:40 ([<STANZA_NAME>]), :53 (type), :57 (python.version), :68 (filename); restmap.conf.spec:144 ([script:<uniqueName>]), :153 (scripttype), :170 (handler), :178 (script), :187 (script.arg.<N>); alert_actions.conf.spec:517 ([script]), :623 ([<custom_alert_action>]), :87 (command); app.conf.spec:124 ([install] state). Presence on a live Splunk 10.4.2 instance confirmed by btool reads of alert_actions and app.

*Mechanism.* commands.conf [<STANZA_NAME>] with filename, type and python.version; restmap.conf [script:<uniqueName>] with script, scripttype and handler; alert_actions.conf [script] and [<custom_alert_action>]; app.conf [install] state = disabled

*Assessment method.* Run, as the Splunk service account: splunk btool commands list --debug; splunk btool restmap list --debug; splunk btool alert_actions list --debug. Enumerate every script stanza with its owning app and reconcile each against documented operational need.

*Product reference.* SPLK-CL-000300 — withdrawn

**SRG-APP-000141-WSR-000083** — CAT II — Applicable, evidence grade C.

The web server must have resource mappings set to disable the serving of certain file types.

*Basis.* Splunk restricts served content by root path rather than by a file-extension deny list. The static endpoint and static directory settings bound which filesystem tree the HTTP static handler serves, a separate setting suppresses directory index generation, and the MIME map labels the extensions served from that tree. A search of the specification set for an extension allow or deny list returns nothing beyond the MIME map key and unrelated remote-storage compression lists, so the restriction this requirement describes is assessed against the served-root settings. Those settings exist in the product, so the requirement applies; whether configuration, log or credential files fall inside a served root is a current-state result the assessment gathers by test.

*Citation.* web.conf.spec:297 (root_endpoint), :303 (static_endpoint), :308 (static_dir), :333 (tools.staticdir.generate_indexes = [1 | 0] - 'Whether or not the webserver serves a directory listing for static directories'); server.conf.spec:1656-1670 ([mimetype-extension-map]). Search of the specification set for 'file.?extension|extension.?(allow|deny|block|list)|forbidden.?(file|extension)' returns only server.conf.spec:1660 (the MIME map key) and two remote-storage compression extension lists in indexes.conf.spec.

*Mechanism.* web.conf [settings] static_endpoint, static_dir, root_endpoint, tools.staticdir.generate_indexes; server.conf [mimetype-extension-map]

*Assessment method.* Run, as the Splunk service account: splunk btool web list settings --debug; splunk btool server list mimetype-extension-map --debug. Then request configuration file, log file and credential file paths through the Splunk Web static endpoint and confirm none is served, and confirm directory listings are not generated.

*Product reference.* SPLK-CL-000300 — withdrawn

**SRG-APP-000141-WSR-000085** — CAT II — Applicable, evidence grade C.

The web server must have Web Distributed Authoring (WebDAV) disabled.

*Basis.* The underlying factual claim survives: an independent re-run of the search across all 128 files of the shipped specification set confirms the product implements no WebDAV protocol. The determination does not survive, because grade A requires that the product expose no mechanism for the requirement, and this requirement is the Web Server SRG tailoring of CM-7 a / CCI-000381 (least functionality), not a test for a protocol name. Two mechanisms exist and were not addressed. First, the requirement carries product STIG reference SPLK-CL-000300, which the basis and evidence never mention; DISA's product-specific implementation for this CCI directs that each instance be configured only with the Splunk instance roles necessary for the implementation, and the settings carrying those roles are present in 10.4.2. Second, Splunk Web implements an HTTP capability that moves server-side framework documents between apps and exposes configuration governing which HTTP methods that endpoint accepts, which is the functional class the requirement's discussion describes. Separately, the evidence misreads its own citation: restmap.conf.spec:468 is the method list for search head cluster REST replay, not an allow list of methods the product's HTTP endpoints accept, so it cannot carry the inference drawn from it. An assessment objective exists, with a configuration surface to examine and test; whether any instance is Satisfied is determined later.

*Citation.* Capability search, re-run independently of any ignore-file filtering over all 128 files of the shipped specification set for 'webdav|propfind|proppatch|mkcol|\bdav\b|lock-token|allprop', case-insensitive: 0 files, 0 lines. Mechanism for the HTTP document-authoring surface: web.conf.spec:206-219 defines enable_secure_entity_move, documenting a 'move' REST endpoint that relocates framework entities (views, styles, drilldown actions) between apps and the HTTP methods permitted against it; web.conf.spec:198 enable_insecure_login and web.conf.spec:221 enable_insecure_pdfgen govern GET-based variants of state-changing endpoints; web.conf.spec:23 startwebserver governs whether the web application server runs at all. The endpoint patterns themselves appear at web.conf:1463 and web.conf:1904. Splunkd's REST layer accepts GET, POST, PUT and DELETE against server-side objects with per-method authorization configurable: restmap.conf.spec:307-320, 'capability.<post|delete|get|put>'. Mechanism for the role minimization the product STIG reference names: server.conf.spec:2430-2432 [clustering] mode = [manager|peer|searchhead|disabled]; server.conf.spec:4458 [shclustering] with its disabled setting; distsearch.conf.spec:29 and :36 [distributedSearch] disabled; inputs.conf.spec:626 [splunktcp]. Citation check on the refuted evidence: restmap.conf.spec:465-469 is the [restreplayshc] stanza, where 'methods' lists REST methods replayed to other search head cluster members and line 468 is its 'Available fields' comment. Confirmation that the mechanisms exist and are readable on a live Splunk 10.4.2 (build 33c3bf42cd73) instance, read-only: btool web list --debug returns startwebserver, enable_secure_entity_move, enable_insecure_login and enable_insecure_pdfgen; btool server list --debug returns the [clustering], [shclustering] and [license] stanzas; btool distsearch list --debug returns [distributedSearch]. The Monitoring Console and its General Setup Mode named by the product STIG reference are present in 10.4.2; that value is persisted to an app-local configuration file of the monitoring console app and so has no entry in the shipped specification set.

*Mechanism.* web.conf [settings] enable_secure_entity_move, enable_insecure_login, enable_insecure_pdfgen, startwebserver; restmap.conf capability.<post|delete|get|put>; server.conf [clustering] mode and [shclustering] disabled; distsearch.conf [distributedSearch] disabled; inputs.conf [splunktcp]

*Assessment method.* Examine the HTTP authoring surface: splunk btool web list --debug (run as the splunk service account) and determine the effective values of enable_secure_entity_move, enable_insecure_login, enable_insecure_pdfgen and startwebserver. Examine the per-method authorization surface: splunk btool restmap list --debug for capability.<post|delete|get|put> on endpoints that modify server-side objects. Examine role minimization: splunk btool server list --debug for [clustering] mode and [shclustering] disabled, splunk btool distsearch list --debug for [distributedSearch] disabled, and splunk btool inputs list --debug for receiving inputs, then compare the enabled roles against the documented deployment design, per product STIG reference SPLK-CL-000300. Test by issuing an HTTP GET against an entity 'move' endpoint and confirming it is refused.

*Product reference.* SPLK-CL-000300 — confirmed in 10 4 2

**SRG-APP-000141-WSR-000086** — CAT II — Applicable, evidence grade C.

The web server must protect system resources and privileged operations from hosted applications.

*Basis.* Splunk apps run inside the instance rather than as separately hosted applications, and the product bounds what each app and each role may reach. Named capabilities gate privileged operations, per-endpoint capability requirements gate REST operations by HTTP method, app metadata access control lists gate object read and write at three layers, and workload pools bound the CPU and memory an execution category may consume. The requirement is implementable through the application's own configuration.

*Citation.* authorize.conf.spec:54 ([capability::<capability>]), :67 ([role_<roleName>]), :150 (srchFilter), :292 (srchIndexesAllowed), :447 ([capability::admin_all_objects]); restmap.conf.spec:111-117 (capability, capability.<post|delete|get|put> - 'Depending on the HTTP method, check capabilities on the authenticated session user'); default.meta.spec ('To access/use an object, users must have read access to: the app containing the object, the generic category within the app, the object itself'; 'access = read : [ * ], write : [ admin, power ]'); workload_pools.conf.spec:73-80 ([workload_pool:<pool_name>] cpu_weight, mem_weight), :105-115 ([workload_category:<category>]).

*Mechanism.* authorize.conf [capability::<capability>] and [role_<roleName>] with srchIndexesAllowed and srchFilter; restmap.conf capability and capability.<post|delete|get|put>; default.meta access = read/write at app, category and object layers; workload_pools.conf [workload_pool:<pool_name>] cpu_weight and mem_weight

*Assessment method.* Run, as the Splunk service account: splunk btool authorize list --debug; splunk btool restmap list --debug; splunk btool workload_pools list --debug. Examine the metadata access control lists under each installed app, then authenticate as a limited role and confirm it cannot reach system resources or privileged operations outside its capability set.

*Product reference.* SPLK-CL-000300 — withdrawn

**SRG-APP-000141-WSR-000087** — CAT II — Applicable, evidence grade C.

Users and scripts running on behalf of users must be contained to the document root or home directory tree of the web server.

*Basis.* Splunk serves application content from per-app static directories bounded by the static directory setting, and the product's object metadata confines visibility to the owning app unless a setting explicitly exports the object to system scope. Role configuration further bounds which indexes a user's searches reach and which events within them are returned. Containment is therefore expressed in the application's own configuration, and the requirement is assessed against those settings together with a traversal test above the served root.

*Citation.* web.conf.spec:297 (root_endpoint), :303 (static_endpoint), :308 (static_dir), :333 (tools.staticdir.generate_indexes); default.meta.spec ('By default, objects are only visible within the app in which they were created. To make an object available to all apps, set the object's export setting to system'; 'export = none'); authorize.conf.spec:292 (srchIndexesAllowed), :150 (srchFilter); app.conf.spec:287 ([ui] is_visible).

*Mechanism.* web.conf [settings] root_endpoint, static_endpoint, static_dir, tools.staticdir.generate_indexes; default.meta access and export; authorize.conf [role_<roleName>] srchIndexesAllowed and srchFilter; app.conf [ui] is_visible

*Assessment method.* Run, as the Splunk service account: splunk btool web list settings --debug; splunk btool authorize list --debug. Examine each app's metadata export and access settings. Then, as a non-administrative user, attempt traversal above the static root through the Splunk Web static endpoint and attempt to search an index outside srchIndexesAllowed.

*Product reference.* SPLK-CL-000300 — withdrawn

**SRG-APP-000142-WSR-000089** — CAT II — Applicable, evidence grade C.

The web server must be configured to use a specified IP address and port.

*Basis.* Splunk exposes an explicit bind address and port for Splunk Web, an explicit address-and-port binding for additional management listeners, a launch-time bind address that governs both the management port and the forwarder receiving ports, and per-input bind and source access control lists. The specification set states that leaving the launch-time bind address unset results in an unspecified bind to all interfaces, which is precisely the condition this requirement prohibits, so the setting is the mechanism and the requirement applies to the product.

*Citation.* web.conf.spec:844-852 ('server.socket_host = <ip_address>'; "The string '0.0.0.0' is a special IPv4 entry meaning 'any active interface'"), :28 (httpport), :35-43 (mgmtHostPort), :858 (listenOnIPv6); server.conf.spec:1612-1622 ('[httpServerListener:<ip:><port>]'; 'If a non-empty <ip> is included ... The listening port is bound only to a specific interface'); splunk-launch.conf.spec:79-90 ('SPLUNK_BINDIP = <ip address>'; 'If not set ... It effectively binds to \'*\', meaning an unspecified bind'; 'For splunkd, this sets both the management port and the ports that receive from forwarders'); inputs.conf.spec:770 ([splunktcp://[<remote server>]:<port>]), :577, :687, :908 (acceptFrom).

*Mechanism.* web.conf [settings] server.socket_host, httpport, mgmtHostPort, listenOnIPv6; server.conf [httpServerListener:<ip:><port>]; splunk-launch.conf SPLUNK_BINDIP; inputs.conf [splunktcp://[<remote server>]:<port>] with acceptFrom

*Assessment method.* Run, as the Splunk service account: splunk btool web list settings --debug; splunk btool server list --debug; splunk btool inputs list --debug. Examine splunk-launch.conf for SPLUNK_BINDIP. Then enumerate the instance's listening sockets and attempt to reach Splunk Web and the management port on each other address assigned to the host.

**SRG-APP-000149-AU-002280** — CAT II — Applicable, evidence grade C.

The Central Log Server must use multifactor authentication for network access to privileged user accounts.

*Basis.* The product exposes two independent second-factor mechanisms through its own configuration: externalTwoFactorAuthVendor activates Duo or RSA multifactor authentication for interactive logon, and enableMfaAuthRest extends the Duo factor to the splunkd REST interface, which is the path the CLI uses. Certificate-based user authentication is the alternative where DoW PKI is the chosen factor. Both are application-level settings, so the requirement falls inside the Splunk boundary.

*Citation.* authentication.conf.spec:87 (externalTwoFactorAuthVendor; Duo and RSA named at :91); authentication.conf.spec:95 (externalTwoFactorAuthSettings); authentication.conf.spec:1568 (enableMfaAuthRest); web.conf.spec:120 (enableCertBasedUserAuth); web.conf.spec:151 (requireClientCert)

*Mechanism.* authentication.conf [authentication] externalTwoFactorAuthVendor, externalTwoFactorAuthSettings; [<duo-externalTwoFactorAuthSettings-key>] enableMfaAuthRest; web.conf [settings] enableCertBasedUserAuth, requireClientCert

*Assessment method.* splunk btool authentication list authentication --debug and splunk btool web list settings --debug (run as the Splunk service account) to read externalTwoFactorAuthVendor, externalTwoFactorAuthSettings, enableCertBasedUserAuth and requireClientCert; then test an interactive network logon with a privileged account and confirm a second factor is demanded.

**SRG-APP-000150-AU-002320** — CAT II — Applicable, evidence grade C.

The Central Log Server must use multifactor authentication for network access to non-privileged user accounts.

*Basis.* The same application mechanisms that provide a second factor for privileged accounts govern non-privileged accounts, because externalTwoFactorAuthVendor and the certificate-based user authentication settings act on the instance's logon path and are not scoped by role. An assessment must therefore confirm the factor is demanded for a non-privileged account specifically, since no per-role multifactor setting exists to inspect.

*Citation.* authentication.conf.spec:87 (externalTwoFactorAuthVendor); authentication.conf.spec:95 (externalTwoFactorAuthSettings); web.conf.spec:120 (enableCertBasedUserAuth); web.conf.spec:133 (certBasedUserAuthMethod); no role-scoped multifactor key appears in the specification set (grep -rniE "twoFactor|enableMfa" over the 128-file set returns matches only in authentication.conf.spec under [authentication] and the Duo and RSA vendor stanzas)

*Mechanism.* authentication.conf [authentication] externalTwoFactorAuthVendor, externalTwoFactorAuthSettings; web.conf [settings] enableCertBasedUserAuth, certBasedUserAuthMethod, requireClientCert

*Assessment method.* splunk btool authentication list authentication --debug and splunk btool web list settings --debug (run as the Splunk service account); then test an interactive network logon with a non-privileged account and confirm a second factor is demanded.

**SRG-APP-000151-AU-002330** — CAT II — Applicable, evidence grade C.

The Central Log Server must use multifactor authentication for local access using privileged user accounts.

*Basis.* Splunk Enterprise exposes no logon path that bypasses the network stack: Splunk Web, the splunkd management interface and the CLI all authenticate through splunkd, so what the requirement calls local access reaches the application over a loopback socket and is governed by the same application settings, with enableMfaAuthRest covering the CLI and REST path. Interactive logon to the underlying host operating system is a separate requirement against the host baseline and is not what this requirement reaches in a product with no local console.

*Citation.* authentication.conf.spec:1568 (enableMfaAuthRest: "Determines whether splunkd requires Duo multifactor authentication against REST endpoints"); authentication.conf.spec:87 (externalTwoFactorAuthVendor); web.conf.spec:120 (enableCertBasedUserAuth); no console or serial logon mechanism appears in the specification set

*Mechanism.* authentication.conf [<duo-externalTwoFactorAuthSettings-key>] enableMfaAuthRest; [authentication] externalTwoFactorAuthVendor, externalTwoFactorAuthSettings; web.conf [settings] enableCertBasedUserAuth

*Assessment method.* splunk btool authentication list --debug (run as the Splunk service account) to read externalTwoFactorAuthVendor and enableMfaAuthRest; then attempt a CLI authentication from the instance host with a privileged account and confirm a second factor is demanded.

**SRG-APP-000154-AU-002360** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured to use multifactor authentication for network access to privileged accounts such that one of the factors is provided by a device separate from the system gaining access.

*Basis.* The separate-device condition is met by a credential held on hardware distinct from the system being accessed, and Splunk configuration selects that form directly: certBasedUserAuthMethod accepts EDIPI and PIV extraction from a client certificate, which is the CAC and PIV form factor, with certBasedUserAuthPivOidList naming the object identifiers searched in the Subject Alternative Name. A Duo or RSA hardware token is the alternative, also selected through application configuration.

*Citation.* web.conf.spec:133 (certBasedUserAuthMethod = CommonName|EDIPI|PIV); web.conf.spec:144 (certBasedUserAuthPivOidList); web.conf.spec:120 (enableCertBasedUserAuth); web.conf.spec:151 (requireClientCert); authentication.conf.spec:87 (externalTwoFactorAuthVendor)

*Mechanism.* web.conf [settings] enableCertBasedUserAuth, certBasedUserAuthMethod, certBasedUserAuthPivOidList, requireClientCert; authentication.conf [authentication] externalTwoFactorAuthVendor

*Assessment method.* splunk btool web list settings --debug (run as the Splunk service account) to read enableCertBasedUserAuth, certBasedUserAuthMethod, certBasedUserAuthPivOidList and requireClientCert; then present a hardware PKI credential on a privileged network logon and confirm the identity is drawn from the certificate.

**SRG-APP-000156-AU-002380** — CAT II — Applicable, evidence grade C.

The Central Log Server must use FIPS-validated SHA-1 or higher hash function to provide replay-resistant authentication mechanisms for network access to privileged accounts.

*Basis.* The requirement's own discussion accepts TLS as a compliant replay-resistant mechanism, and Splunk exposes TLS termination with protocol and cipher selection for both the web interface and the management interface. SPLUNK_FIPS constrains the instance to the FIPS-validated cryptographic module, so the negotiated hash is FIPS-validated; that setting takes effect only when configured before the instance first starts, which an assessment must account for.

*Citation.* web.conf.spec:70 (enableSplunkWebSSL); web.conf.spec:82 (serverCert); web.conf.spec:75 (privKeyPath); web.conf.spec:239 (sslVersions); web.conf.spec:255 (cipherSuite); server.conf.spec:765 (sslVersions); server.conf.spec:780 (sslVersionsForClient); splunk-launch.conf.spec:110 (SPLUNK_FIPS = [0|1], "NOTE: This setting is one-time only")

*Mechanism.* web.conf [settings] enableSplunkWebSSL, serverCert, privKeyPath, sslVersions, cipherSuite; server.conf [sslConfig] sslVersions, sslVersionsForClient, cipherSuite; splunk-launch.conf SPLUNK_FIPS

*Assessment method.* splunk btool web list settings --debug and splunk btool server list sslConfig --debug (run as the Splunk service account) to read enableSplunkWebSSL, serverCert, privKeyPath, sslVersions and cipherSuite; read SPLUNK_FIPS from splunk-launch.conf; then confirm the negotiated protocol and cipher on the web and management ports with an external TLS scan.

*Product reference.* SPLK-CL-000330 — confirmed in 10 4 2

**SRG-APP-000163-AU-002470** — CAT II — Applicable, evidence grade C.

The Central Log Server must disable accounts (individuals, groups, roles, and devices) after 35 days of inactivity.

*Basis.* The OUTSIDE_BOUNDARY determination fails on three independent grounds. First, the benchmark scopes its own remediation to the application's local accounts: the fix text reads "For local accounts (except for the account of last resort), configure the Central Log Server to disable accounts (individuals, groups, roles, and devices) after 35 days of inactivity." A directory service or SAML identity provider does not hold the accounts in the Splunk native account store, so the named provider cannot discharge a requirement whose remediation is directed at local accounts. The native store persists under every authentication binding - authType accepts Splunk, LDAP, Scripted, SAML and ProxySSO (authentication.conf.spec:30), the [splunk_auth] stanza (authentication.conf.spec:458) is independent of any external binding, and authTypePreferredForUserCollision exists precisely because native accounts coexist with identity-provider accounts - so local accounts are present at every site and the requirement follows them into the application boundary. Second, the prior basis made applicability conditional on a site's binding choice, conceding that where a site relies on native local accounts "there is no mechanism." A disposition asserting that the Splunk team owes nothing cannot rest on a basis conceding it may owe everything; applicability is a property of the product and the requirement, not of one site's authentication selection. Third, the capability claim is unsound. Splunk Enterprise 10.4.2 exposes inbound automated user management over SCIM - the configuration path by which an identity provider that detects account inactivity applies deactivation or removal to the account held by the Splunk instance. That mechanism is present in the specification set the prior assessor searched and the search missed it, because the search enumerated invented setting names rather than the capability. The implementation is shared: the identity provider makes the inactivity determination, and the Splunk application owes the configuration of the provisioning path that applies it, which is work inside the boundary. The native account store exposes no inactivity timer - expirePasswordDays (authentication.conf.spec:508) and expireUserAccounts (authentication.conf.spec:525) govern password expiry, which the prior assessor had right - and the SCIM integration is bounded to the identity-provider domains named by scimSupportedDomains (authentication.conf.spec:95), a setting the specification instructs the operator not to modify. Those are capability limits to be recorded against the requirement and tested against an instance later; they are not grounds to move the requirement outside the application boundary.

*Citation.* Determination rests on the specification set as shipped with the running product, confirmed as Splunk 10.4.2 build 33c3bf42cd73 (splunk version). Mechanism citations, 10.4.2 line numbering: server.conf.spec:6998 [teleport_supervisor] and :6999 disabled = <boolean>, governing whether splunkd launches the supervisor process that "handles authorization tokens for System for Cross-Domain Identity Management (SCIM) operations", default false; web-features.conf.spec:533 [feature:identity_sidecar_scim] and :535 enabled = <boolean>, governing the "Automated User Management (AUM) controls for System for Cross-Domain Identity Management (SCIM)"; authentication.conf.spec:95 scimSupportedDomains in [authentication] (authentication.conf.spec:26), constraining the domains permitted for SCIM integration; authentication.conf.spec:618 scsSyncUserDeletes, confirming the local user store is the object of provisioning operations. The account-of-last-resort exemption named in the fix text has its role-scoped counterpart at authorize.conf.spec:1002 [capability::never_lockout] and :1005 [capability::never_expire]. Native account lifecycle settings that do not meet the requirement: authentication.conf.spec:508 expirePasswordDays and :525 expireUserAccounts, both password expiry. Searches run independently over all 128 files of the provided set and over all 71 .spec files shipped with the instance: disableAfter, inactivityDays, accountExpir, maxInactiveDays, idleDays, lastActivity, revokeUser, disableUser returned 0 hits in both, confirming no inactivity-named setting; a broad search on inactiv|dormant|unused|stale|lastLogin|lastLogon returned only search, session, index, channel and cluster timers; deactivat|suspend|lifecycle returned only dashboard and audit-action settings. A search on scim|automated user management|teleport, which the prior assessor did not run, returned the provisioning surface cited above. Separate evidentiary finding: the specification snapshot provided as the task input is not the set 10.4.2 ships. Every file compared is materially shorter - authentication.conf.spec 1,729 lines against 2,126 as shipped, server.conf.spec 6,645 against 7,423, web-features.conf.spec 443 against 661, authorize.conf.spec 1,061 against 1,336, limits.conf.spec 5,102 against 5,719, web.conf.spec 1,566 against 1,697 - and the snapshot omits scimSupportedDomains and scsSyncUserDeletes outright. Stanza line numbers diverge between the two sets ([teleport_supervisor] at snapshot line 6584 against shipped line 6998), so file:line citations taken from the snapshot do not resolve against 10.4.2. Any grade A capability-absence claim built on that snapshot is unsafe, for this requirement and for every other requirement in scope.

*Mechanism.* server.conf [teleport_supervisor] disabled; web-features.conf [feature:identity_sidecar_scim] enabled; authentication.conf [authentication] scimSupportedDomains; authorize.conf [capability::never_expire] and [capability::never_lockout] for the account-of-last-resort exemption

*Providing baseline.* The organization's directory service or identity provider - Active Directory or another LDAP directory, or the SAML identity provider - bound through authentication.conf [<authSettings-key>] or [<saml-authSettings-key>], assessed under that baseline's own benchmark

*Assessment method.* splunk btool server list teleport_supervisor --debug; splunk btool web-features list feature:identity_sidecar_scim --debug; splunk btool authentication list authentication --debug; splunk btool authorize list --debug | grep -E 'never_expire|never_lockout' - then examine the identity provider configuration for an inactivity-triggered deactivation rule propagated over SCIM, and enumerate the native account roster (REST services/authentication/users) against authentication audit records to test whether any local account other than the account of last resort has been idle beyond 35 days. All btool invocations run as the splunk account.

**SRG-APP-000164-AU-002480** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured to enforce a minimum 15-character password length.

*Basis.* Splunk native authentication exposes a minimum password length as a configurable integer that rejects non-conforming password modification attempts, so the 15-character floor is reachable through application configuration. The setting governs accounts held in Splunk native authentication only; where organizational users are held in a directory service, length enforcement for those accounts rests with that provider.

*Citation.* authentication.conf.spec:441 (minPasswordLength = <positive integer>, "Password modification attempts which do not meet this requirement are explicitly rejected", default 8); key confirmed resolvable on a live 10.4.2 instance via btool authentication list splunk_auth

*Mechanism.* authentication.conf [splunk_auth] minPasswordLength

*Assessment method.* splunk btool authentication list splunk_auth --debug (run as the Splunk service account) and read minPasswordLength; then attempt to set a 14-character password on a native test account and confirm rejection.

*Product reference.* SPLK-CL-000340, SPLK-CL-000350, SPLK-CL-000360, SPLK-CL-000370, SPLK-CL-000380, SPLK-CL-000400 — confirmed in 10 4 2

**SRG-APP-000175-WSR-000095** — CAT II — Applicable, evidence grade C.

The web server must perform RFC 5280-compliant certification path validation.

*Basis.* This requirement's check text carries the clause "If PKI is not being used, this is NA", but that clause turns on a site's chosen state rather than on a property of the product, and Splunk Enterprise 10.4.2 can use PKI through enableCertBasedUserAuth; a benchmark clause conditioned on site state cannot support a determination that must hold for the product at any site, so it is declined here. Path validation to a configured trust anchor with revocation status is reachable through application configuration, which makes the requirement applicable wherever PKI is elected.

*Citation.* web.conf.spec:120 (enableCertBasedUserAuth); web.conf.spec:108 (sslRootCAPath); server.conf.spec:1125 (certificateStatusValidationMethod = crl); server.conf.spec:5392 (sslCRLPath); the group inventory records has_own_na_clause as false for this requirement, which is inconsistent with the check text quoted above and should be corrected in the inventory

*Mechanism.* web.conf [settings] enableCertBasedUserAuth, requireClientCert, sslRootCAPath; server.conf [sslConfig] sslRootCAPath, certificateStatusValidationMethod

*Assessment method.* splunk btool web list settings --debug and splunk btool server list sslConfig --debug (run as the Splunk service account) to read enableCertBasedUserAuth, sslRootCAPath and certificateStatusValidationMethod; where PKI is not elected the objective is Not Applicable for that instance, which the assessment records against the instance rather than against the product.

**SRG-APP-000176-WSR-000096** — CAT II — Applicable, evidence grade C.

Only authenticated system administrators or the designated PKI Sponsor for the web server must have access to the web servers private key.

*Basis.* The reading of the Not Applicable clause stands and I reach the same conclusion: privKeyPath carries a product default private key path for Splunk Web and resolves on a live 10.4.2 instance, so the clause does not hold. Separately, the IA-1 inventory record sets has_own_na_clause to false for this requirement although its check text opens with that clause, so the flag understates the number of requirements carrying one. The boundary conclusion does not stand. The search offered in support of it tested for filesystem-permission vocabulary (chown, chmod, file mode, permission) and inferred from its absence that the application exposes no access control over the key. That is the wrong search for this requirement, which asks who may access the private key, not how a file mode is set, and it is the pattern the standard warns against: absence of a setting named chmod is not absence of access control. Splunk itself exposes read and write paths to the key material through its own interfaces, and only application configuration restricts them: the /services/properties endpoint returns web.conf settings including the key path and the passphrase field, the web settings handler can rewrite the key path, and the storage passwords endpoint exposes stored secrets. Each is gated by an authorize.conf capability assigned to roles. An authenticated non-administrator holding rest_properties_get or list_storage_passwords therefore reaches the key path and the protected passphrase through the product, with no involvement of the host filesystem. Host discretionary access control and container image or volume ownership are a parallel layer, not a substitute, and an OUTSIDE_BOUNDARY row would tell an AO that no capability and role review is owed for key material. The designated PKI Sponsor is an organizational appointment recorded as an artifact alongside the configuration, not in place of it.

*Citation.* web.conf.spec:75 (privKeyPath, "The path to the file containing the web server SSL certificate private key", default under etc/auth/splunkweb), :82 (serverCert), :93 (sslPassword, "Password that protects the private key specified by 'privKeyPath'"); server.conf.spec [general] encrypt_fields at :547 with its default field list at :559 naming server sslPassword and sslKeysfilePassword, the mechanism that holds conf-stored key passphrases under the platform secret; authorize.conf.spec:894 ([capability::rest_properties_get], "Lets a user get information from the services/properties endpoint"), :733 ([capability::edit_web_settings]), :853 ([capability::list_storage_passwords], read of the storage passwords endpoint), :447 ([capability::admin_all_objects]), :67-68 ([role_<roleName>] with <capability> = <enabled>, the assignment surface). On a live 10.4.2 instance privKeyPath and sslPassword resolve under web.conf [settings] with the passphrase rendered in the platform's encrypted form, and btool authorize list resolves all four capability stanzas together with role stanzas carrying capability assignments, establishing that the application-level access-control mechanism exists. The independent search over every file in the set for chown, chmod, umask and file-mode settings returns nothing relevant, which establishes only that file modes are not a Splunk setting.

*Mechanism.* web.conf, [settings]: privKeyPath names the Splunk Web private key and sslPassword holds its passphrase; server.conf, [general] encrypt_fields places that passphrase field under the platform secret. Authorize.conf capability stanzas govern who reaches that material through the application: rest_properties_get, edit_web_settings, list_storage_passwords and admin_all_objects, assigned to roles through [role_<roleName>].

*Providing baseline.* The host operating system's discretionary access control on the filesystem, and the container platform's image and volume ownership where the instance runs in a container

*Artifact.* Designation letter or equivalent record appointing the PKI Sponsor for the web server, and the authorized system administrator roster against which role capability assignments are reconciled

*Assessment method.* Run `splunk btool web list settings --debug` as the splunk service account to identify the configured private key path and whether a passphrase field is present. Run `splunk btool authorize list --debug` and enumerate every role holding rest_properties_get, rest_properties_set, edit_web_settings, list_storage_passwords or admin_all_objects, then reconcile those role memberships against the authorized system administrator roster and the designated PKI Sponsor. Examine ownership and mode on the key path, and image or volume ownership where the instance runs in a container, as the parallel host layer.

**SRG-APP-000179-WSR-000111** — CAT II — Applicable, evidence grade C.

The web server must use cryptographic modules that meet the requirements of applicable federal laws, Executive Orders, directives, policies, regulations, standards, and guidance for such authentication.

*Basis.* The cryptographic module used when the application authenticates users and processes is selected by SPLUNK_FIPS, and the specific algorithms exercised during authentication are configurable through the stored-authenticator hash setting and the TLS protocol and cipher selection on the logon channel. All three are application configuration, so the requirement sits inside the Splunk boundary.

*Citation.* splunk-launch.conf.spec:110 (SPLUNK_FIPS); authentication.conf.spec:58 (passwordHashAlgorithm); web.conf.spec:70 (enableSplunkWebSSL); web.conf.spec:239 (sslVersions); web.conf.spec:255 (cipherSuite)

*Mechanism.* splunk-launch.conf SPLUNK_FIPS; authentication.conf [authentication] passwordHashAlgorithm; web.conf [settings] enableSplunkWebSSL, sslVersions, cipherSuite

*Assessment method.* read SPLUNK_FIPS from splunk-launch.conf and confirm FIPS mode in the splunkd.log startup banner; splunk btool authentication list authentication --debug and splunk btool web list settings --debug (run as the Splunk service account) to read passwordHashAlgorithm, enableSplunkWebSSL, sslVersions and cipherSuite; then confirm the negotiated cipher on the logon channel with an external TLS scan.

*Product reference.* SPLK-CL-000390, SPLK-CL-000430 — confirmed in 10 4 2

**SRG-APP-000181-AU-000200** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured to perform audit reduction that supports on-demand reporting requirements.

*Basis.* Splunk exposes stored, parameterized report definitions that can be run on demand over a selectable time range, and summarization paths that write reduced record sets without altering the original records. Audit reduction supporting on-demand reporting is therefore a product capability and the requirement applies to the application.

*Citation.* savedsearches.conf.spec:31 [<stanza name>], :44 search, :564 dispatch.earliest_time, :571 dispatch.latest_time, :439 action.summary_index with :443 action.summary_index._name, :772 auto_summarize.command; datamodels.conf.spec:29 acceleration; metric_rollups.conf.spec:38 defaultAggregation; macros.conf.spec:24 and :52 definition.

*Mechanism.* savedsearches.conf [<stanza name>] search with dispatch.earliest_time and dispatch.latest_time; action.summary_index and auto_summarize; datamodels.conf acceleration; metric_rollups.conf defaultAggregation; macros.conf definition

*Assessment method.* Run `splunk btool savedsearches list --debug` to enumerate report definitions with their dispatch ranges, action.summary_index and auto_summarize settings, then run one on demand and confirm it returns a reduced result set while the source records remain unchanged.

**SRG-APP-000206-WSR-000128** — CAT II — Applicable, evidence grade C.

A web server using mobile code must meet DoD-defined mobile code requirements.

*Basis.* Splunk Web is delivered to the browser as a JavaScript application, and hosted apps can add HTML-based views and Simple XML custom JavaScript extensions, so a requirement governing mobile code the Splunk instance emits reaches this product. Splunk Enterprise 10.4.2 exposes configuration that constrains which external content the browser is permitted to load and execute, and a capability that gates which roles may author HTML-based views.

*Citation.* web-features.conf.spec:48-106 ([feature:dashboards_csp] enable_dashboards_external_content_restriction sets the Content-Security-Policy header; enable_dashboards_redirection_restriction; dashboards_trusted_domain.<name> is the trusted domain list carried in the CSP header). Web-features.conf.spec:38-46 ([feature:quarantine_files] enable_unsupported_hotlinked_imports governs unsupported JavaScript dependencies in Simple XML custom extensions). Authorize.conf.spec:730-731 ([capability::edit_view_html] lets a user create, edit, or otherwise modify HTML-based views). Web.conf.spec:719-722 (x_frame_options_sameorigin).

*Mechanism.* web-features.conf [feature:dashboards_csp] enable_dashboards_external_content_restriction, enable_dashboards_redirection_restriction, dashboards_trusted_domain.<name>; web-features.conf [feature:quarantine_files] enable_unsupported_hotlinked_imports; authorize.conf [capability::edit_view_html]; web.conf [settings] x_frame_options_sameorigin

*Assessment method.* Run, as the Splunk service account, `splunk btool web-features list --debug` and `splunk btool authorize list --debug`, and examine the CSP and trusted-domain settings and the roles holding edit_view_html; examine the mobile code inventory for hosted apps against DoD mobile code policy.

**SRG-APP-000211-WSR-000030** — CAT II — Applicable, evidence grade C.

Web server accounts accessing the directory tree, the shell, or other operating system functions and utilities must only be administrative accounts.

*Basis.* Splunk Enterprise carries its own account and role model and gates every function that reaches the host file system, a shell, or a scripted interpreter behind a named capability that must be granted to a role, so the requirement is implementable and assessable inside the application boundary. The single operating system identity that splunkd adopts is named in the launch file; the privileges granted to that identity on the host belong to the host operating system baseline and are assessed there.

*Citation.* authorize.conf.spec:67-78 ([role_<roleName>], <capability> = <enabled>, capabilities disabled by default, importRoles) and :86-111 (grantableRoles scoping of user and role management). Host-reaching capabilities: authorize.conf.spec:638-639 (edit_scripted, scripted inputs), :756-758 (input_file), :912-913 (run_custom_command), :760-762 (install_apps), :447 (admin_all_objects), :597 (edit_monitor), :585 (edit_input_defaults). Splunk-launch.conf.spec:97-108 (SPLUNK_OS_USER, the OS user whose privileges splunkd adopts).

*Mechanism.* authorize.conf [role_<roleName>] capability assignment, importRoles, grantableRoles; the host-reaching capabilities edit_scripted, run_custom_command, input_file, edit_monitor, edit_input_defaults, install_apps, admin_all_objects; splunk-launch.conf SPLUNK_OS_USER

*Assessment method.* Run `splunk btool authorize list --debug` as the Splunk service account and enumerate, for each role, the host-reaching capabilities it holds directly or by importRoles; compare each against the documented function of the role.

**SRG-APP-000211-WSR-000031** — CAT II — Applicable, evidence grade C.

Anonymous user access to the web server application directories must be prohibited.

*Basis.* Splunk Enterprise requires an authenticated session for its management REST surface and for Splunk Web, and the specification set exposes exactly one setting that can place a REST endpoint outside that requirement, which makes the condition this requirement examines both reachable and assessable in product configuration. Write access to app objects is governed by per-app metadata access lists naming roles, and endpoint access can be further bound to a capability and a network ACL.

*Citation.* restmap.conf.spec:81-84 (requireAuthentication = <boolean>, 'Determines if this endpoint requires authentication', Default: true) and :111-119 (capability = <capabilityName>, capability.<post|delete|get|put>) and :121-130 (acceptFrom). Default.meta.spec:40-59 (access = read : [ * ], write : [ admin, power ]; per-object access stanzas; export; owner). Server.conf.spec:1469 (handling of objects previously shared to anonymous users).

*Mechanism.* restmap.conf [<rest endpoint name>:<description>] requireAuthentication, capability, acceptFrom; app metadata (default.meta / local.meta) access = read/write role lists; authorize.conf [role_<roleName>] capabilities

*Assessment method.* Run `splunk btool restmap list --debug` as the Splunk service account and enumerate every stanza carrying requireAuthentication = false; examine each app's metadata access stanzas for write grants to [ * ]; confirm an unauthenticated request to the management interface is refused.

**SRG-APP-000211-WSR-000129** — CAT II — Applicable, evidence grade C.

The web server must separate the hosted applications from hosted web server management functionality.

*Basis.* Splunk Enterprise serves hosted application content from the Splunk Web listener and its own management interface from the splunkd REST listener. Each listener is defined in its own conf file and stanza, with its own port and its own network ACL, and the operations that administer the Splunk instance are gated behind capabilities distinct from those needed to use a hosted app. The separation this requirement describes is therefore implementable through product configuration.

*Citation.* server.conf.spec:1291 ([httpServer], the splunkd REST and management listener) with acceptFrom at :1345. Web.conf.spec:16 ([settings], the Splunk Web listener) with acceptFrom at :1080. Capability separation: authorize.conf.spec:733-735 (edit_web_settings), :665 (edit_server), :753-754 (indexes_edit), :760-762 (install_apps), :447 (admin_all_objects). Restmap.conf.spec:111-119 (per-endpoint and per-method capability checks on the authenticated session user).

*Mechanism.* server.conf [httpServer] (management listener, acceptFrom); web.conf [settings] (Splunk Web listener, mgmtHostPort, acceptFrom); authorize.conf capabilities edit_web_settings, edit_server, indexes_edit, install_apps, admin_all_objects; restmap.conf capability per endpoint and method

*Assessment method.* Run `splunk btool server list --debug` and `splunk btool web list --debug` as the Splunk service account and confirm the two listeners and their network ACLs are separately defined; run `splunk btool authorize list --debug` and confirm roles used for hosted-app access hold none of the Splunk instance management capabilities.

**SRG-APP-000219-WSR-000190** — CAT II — Applicable, evidence grade C.

The web server must restrict a consistent inbound source IP for the entire management session.

*Basis.* The inheritance fails on its own terms and is overturned. First, no providing baseline is named: "the TLS-terminating reverse proxy or load balancer fronting the management interface" is a class of device, offered in the alternative, whose presence the basis under review itself treats as conditional when it concedes the requirement is Other Than Satisfied where no such device exists. A provider that may or may not be present is an architectural assumption, not an inheritance, and an applicability determination must hold for Splunk Enterprise 10.4.2 at any site. Second, this is a Web Server SRG requirement addressed to the web server under assessment. The splunkd management interface is that web server; interposing a second web server relocates the assessment object rather than transferring the control, and the requirement continues to bear on the management interface behind any such device. Third, the capability premise is too broad. The requirement's discussion states the objective as session authenticity against man-in-the-middle attacks and session hijacking and holds that web services will require TLS mutual authentication, and Splunk Enterprise 10.4.2 implements mutual TLS on the splunkd management interface through requireClientCert, which conditions every request in a management session on a certificate signed by a trusted certificate authority. That binding is to a client credential rather than to a source address, and a change of source address does not defeat it. Source-address restriction effective for the whole management session is separately configurable through the httpServer and per-endpoint network ACLs and through the general remote-login restriction, each evaluated per request. The narrow observation survives examination: the product exposes no key that compares a request's source address to the address that established the session, so testing an instance against the literal check text may yield Other Than Satisfied. That is an assessment result against the objective, not grounds to place the requirement outside the application boundary.

*Citation.* Independent search of the complete specification set, enumerated as a file list of 71 .spec files (67 .conf.spec, plus default.meta.spec, instance.cfg.spec, serverclass.seed.xml.spec and setup.xml.spec) rather than by recursive match, so no ignore rules could filter results. Unconstrained case-insensitive searches for 'remote.?addr', 'client.?ip', 'source.?ip', 'forwarded', 'hijack', 'originating' and 'same.{0,12}(ip|address)', and an enumeration of every key whose name begins with 'session', confirm that no key associates a session with the address that established it. The session keys that exist are web.conf.spec:920-978 (tools.sessions.on, .timeout, .restart_persist, .httponly, .secure, .forceSecure, .storage_type, .storage_path) and server.conf.spec:73 and :81 ([general] sessionTimeout, invalidateSessionTokensOnLogout). The determination under review did not establish that result, because every pattern it recorded requires the literal token 'session' adjacent to an address token and so cannot surface an address-aware key that carries no such token; two exist, inputs.conf.spec:3028 (remoteAddress) and server.conf.spec:105 ([general] allowRemoteLogin). Its stated scope is also mislabeled: the set holds 67 .conf.spec files, not 71. Mechanisms inside the application boundary: server.conf.spec:858, [sslConfig] requireClientCert, 'Whether or not an HTTPS client which connects to a splunkd server must possess a certificate that a certificate authority signed to complete the connection'; server.conf.spec:105, [general] allowRemoteLogin = always|never|requireSetPassword, 'Controls remote management by restricting general login'; server.conf.spec:1345, [httpServer] acceptFrom = <network_acl>, 'Lists a set of networks or addresses from which to accept connections'; restmap.conf.spec:121, per-endpoint acceptFrom; server.conf.spec:73, [general] sessionTimeout; server.conf.spec:1520, :1525, :1532 and :1548, [httpServer] allowCookieAuth, cookieAuthHttpOnly, cookieSameSiteSecure, cookieAuthSecure. Existence confirmed on a live Splunk 10.4.2 instance (build 33c3bf42cd73) with read-only 'btool server list --debug' run as the splunk account, which enumerates the allowRemoteLogin, sessionTimeout, acceptFrom and allowCookieAuth keys; requireClientCert is not enumerated there because no shipped default file carries it, and its presence in 10.4.2 rests on server.conf.spec:858.

*Mechanism.* server.conf [sslConfig] requireClientCert; server.conf [general] allowRemoteLogin; server.conf [general] sessionTimeout; server.conf [httpServer] acceptFrom; restmap.conf <endpoint> acceptFrom; server.conf [httpServer] allowCookieAuth, cookieAuthHttpOnly, cookieAuthSecure, cookieSameSiteSecure

*Providing baseline.* The TLS-terminating reverse proxy or load balancer fronting the Splunk management interface, assessed under the Web Server SRG in its own right, together with the network boundary baseline

*Assessment method.* Run as the splunk service account, read-only: 'splunk btool server list --debug' and 'splunk btool restmap list --debug', filtered for requireClientCert, allowRemoteLogin, acceptFrom, sessionTimeout, allowCookieAuth and cookieAuth. Then test the management listener for client-certificate demand by attempting a TLS handshake to the management port without presenting a client certificate and recording whether the handshake completes.

**SRG-APP-000219-WSR-000191** — CAT II — Applicable, evidence grade C.

The web server must restrict a consistent inbound source IP for the entire user session.

*Basis.* Overturned on the same grounds as the management-session requirement, and more strongly, because Splunk Web is itself the web server the requirement addresses. The determination under review names no providing baseline; a reverse proxy or load balancer offered in the alternative, and conceded to be absent at some sites, is an architectural assumption rather than an inheritance, and the basis itself admits the requirement would then be Other Than Satisfied, which is a finding against the Splunk application. Shifting a Web Server SRG requirement about authenticated user sessions onto an upstream device relocates the assessment object; Splunk Web continues to serve authenticated user sessions behind any such device and the requirement continues to bear on it. The capability premise is also too broad. The requirement's discussion identifies the objective as session authenticity against session hijacking and insertion of false information into sessions, and holds that web services will require TLS mutual authentication. Splunk Enterprise 10.4.2 implements mutual TLS and certificate-bound user identity in Splunk Web through requireClientCert together with enableCertBasedUserAuth, certBasedUserAuthMethod and the Subject Alternative Name object identifier list, with client common name and alternative name checking. Those settings condition each request in a user session on a client certificate and derive the user identity from it, which addresses the stated objective without reference to a source address. Splunk Web additionally exposes a listener network ACL and, in strict single sign-on mode, a per-request source-address restriction against a configured trusted address list, each evaluated for the life of the session, along with session lifetime and cookie attribute controls. The narrow observation stands: the product exposes no key that pins a session to the address that established it, so testing an instance against the literal check text may yield Other Than Satisfied. That is an assessment result, not an inheritance, and the requirement remains with the Splunk application.

*Citation.* Same independent search of the complete specification set recorded for SRG-APP-000219-WSR-000190, run by file list over all 71 .spec files so that no ignore rules could filter results, and extended to cookie-named and certificate-named keys. It confirms no key pins a session to its originating address, and it also shows the determination under review understated the product's configuration surface for this control. Mechanisms inside the application boundary, all in web.conf [settings]: web.conf.spec:151 requireClientCert, 'A client can connect only if it presents a certificate that was created and signed by the same CA that created the certificate that the instance uses'; web.conf.spec:120 enableCertBasedUserAuth, 'Whether or not user authentication with certificates is enabled'; web.conf.spec:134 certBasedUserAuthMethod (CommonName, EDIPI, PIV) and the following certBasedUserAuthPivOidList; web.conf.spec:169 sslCommonNameToCheck and :175 sslAltNameToCheck, which check the client certificate common name and Subject Alternative Name and require requireClientCert to have a value of true; web.conf.spec:1080 acceptFrom = <network_acl>; web.conf.spec:787 SSOMode = [permissive | strict], where strict means 'All requests to Splunk Web will be restricted to those originating from a trusted IP except those to endpoints that do not require authentication', with web.conf.spec:797 trustedIP; web.conf.spec:924 tools.sessions.timeout, :934 tools.sessions.restart_persist, :943 tools.sessions.httponly, :951 tools.sessions.secure, and :664 cookieSameSite. Existence confirmed on a live Splunk 10.4.2 instance (build 33c3bf42cd73) with read-only 'btool web list --debug' run as the splunk account, which enumerates the SSOMode, acceptFrom and tools.sessions.* keys; requireClientCert and enableCertBasedUserAuth are not enumerated there because no shipped default file carries them, and their presence in 10.4.2 rests on web.conf.spec:151 and :120.

*Mechanism.* web.conf [settings] requireClientCert, enableCertBasedUserAuth, certBasedUserAuthMethod, certBasedUserAuthPivOidList, sslCommonNameToCheck, sslAltNameToCheck; web.conf [settings] acceptFrom; web.conf [settings] SSOMode, trustedIP; web.conf [settings] tools.sessions.timeout, tools.sessions.secure, tools.sessions.httponly, tools.sessions.restart_persist, cookieSameSite

*Providing baseline.* The TLS-terminating reverse proxy or load balancer fronting Splunk Web, assessed under the Web Server SRG in its own right, together with the network boundary baseline

*Assessment method.* Run as the splunk service account, read-only: 'splunk btool web list --debug', filtered for requireClientCert, enableCertBasedUserAuth, certBasedUserAuthMethod, certBasedUserAuthPivOidList, sslCommonNameToCheck, sslAltNameToCheck, acceptFrom, SSOMode, trustedIP, tools.sessions and cookieSameSite. Then test the Splunk Web listener by attempting a TLS handshake without presenting a client certificate and recording whether the handshake completes, and examine whether an established user session continues to be served when the request arrives from a different source address.

**SRG-APP-000220-WSR-000201** — CAT II — Applicable, evidence grade C.

The web server must invalidate session identifiers upon hosted application user logout or other session termination.

*Basis.* Splunk Enterprise issues session identifiers and bearer tokens and carries named settings that end a session and invalidate what it issued. Version 10.4.2 carries a setting whose stated function is invalidating the tokens associated with a logged-out session across search head cluster members, together with an interval governing propagation of that logout information, and separate expiration settings for standard and ephemeral authorization tokens. The requirement is implementable and assessable in product configuration.

*Citation.* server.conf.spec:73-78 ([general] sessionTimeout, 'The amount of time before a user session times out'); :81-87 (invalidateSessionTokensOnLogout, 'invalidates any tokens associated with a logged-out session across all nodes in the cluster'); :89-98 (logoutCacheRefreshInterval). Web.conf.spec:924-932 (tools.sessions.timeout), :934-941 (tools.sessions.restart_persist), :403 (ui_inactivity_timeout). Authorize.conf.spec:390-409 ([tokens_auth] expiration) and :411-438 (ephemeralExpiration).

*Mechanism.* server.conf [general] sessionTimeout, invalidateSessionTokensOnLogout, logoutCacheRefreshInterval; web.conf [settings] tools.sessions.timeout, tools.sessions.restart_persist, ui_inactivity_timeout; authorize.conf [tokens_auth] expiration, ephemeralExpiration

*Assessment method.* Run `splunk btool server list --debug`, `splunk btool web list --debug` and `splunk btool authorize list --debug` as the Splunk service account for the named keys; then authenticate, log out, and replay the prior session identifier to confirm it is refused.

**SRG-APP-000223-WSR-000011** — CAT II — Applicable, evidence grade C.

Cookies exchanged between the web server and client, such as session cookies, must have security settings that disallow cookie access outside the originating web server and hosted application.

*Basis.* Splunk Enterprise sets the HttpOnly, Secure and SameSite attributes on the session cookie it issues, through separate keys for the Splunk Web session cookie and for the splunkd REST authentication cookie. Those attributes are the mechanism by which a cookie is kept from the reach of other origins and of page script, which is what this requirement describes.

*Citation.* web.conf.spec:943-949 (tools.sessions.httponly, session cookie not available to running JavaScript); :951-960 (tools.sessions.secure, browser must transmit the session cookie over HTTPS); :962-969 (tools.sessions.forceSecure); :664-690 (cookieSameSite = [ not_specified | lax | strict | none ]). Server.conf.spec:1520-1524 ([httpServer] allowCookieAuth); :1525-1530 (cookieAuthHttpOnly); :1532-1546 (cookieSameSiteSecure); :1548-1553 (cookieAuthSecure).

*Mechanism.* web.conf [settings] tools.sessions.httponly, tools.sessions.secure, tools.sessions.forceSecure, cookieSameSite; server.conf [httpServer] allowCookieAuth, cookieAuthHttpOnly, cookieAuthSecure, cookieSameSiteSecure

*Assessment method.* Run `splunk btool web list --debug` and `splunk btool server list --debug` as the Splunk service account for the cookie keys, then examine the Set-Cookie header returned by the authenticated interface and confirm the HttpOnly, Secure and SameSite attributes are present.

**SRG-APP-000223-WSR-000145** — CAT II — Applicable, evidence grade C.

The web server must accept only system-generated session identifiers.

*Basis.* Splunk Web holds session state in a server-side session store keyed by an identifier the Splunk instance issues, and the splunkd REST layer honors only session keys and tokens it issued. The one configuration surface that can introduce an externally asserted identity is proxy single sign-on, whose own specification records that a browser could dictate the user header unless exact header matching and a trusted proxy address are set. The requirement therefore applies and is assessable through named product settings.

*Citation.* web.conf.spec:920 (tools.sessions.on) and :977-978 (tools.sessions.storage_type = [file], tools.sessions.storage_path, the Splunk instance-side session store). Server.conf.spec:1520-1524 ([httpServer] allowCookieAuth, clients request a cookie from the /services/auth/login endpoint). Authorize.conf.spec:381-388 ([tokens_auth] disabled). The externally asserted identity surface: web.conf.spec:728-748 (remoteUser, with the caution that a browser could theoretically dictate the username), :767-775 (remoteUserMatchExact), :787-804 (SSOMode, trustedIP), :806-811 (allowSsoWithoutChangingServerConf).

*Mechanism.* web.conf [settings] tools.sessions.on, tools.sessions.storage_type, tools.sessions.storage_path, remoteUser, remoteUserMatchExact, SSOMode, trustedIP, allowSsoWithoutChangingServerConf; server.conf [general] trustedIP; server.conf [httpServer] allowCookieAuth; authorize.conf [tokens_auth] disabled

*Assessment method.* Run `splunk btool web list --debug` and `splunk btool server list --debug` as the Splunk service account for the session and single sign-on keys; then present a fabricated session cookie and a fabricated bearer token to the interface and confirm both are refused.

**SRG-APP-000224-WSR-000136** — CAT II — Applicable, evidence grade C.

The web server must generate unique session identifiers that cannot be reliably reproduced.

*Basis.* Splunk Web issues a session identifier to every authenticated client, drawn from the instance's cryptographic random number generator, whose module selection is governed by the launch-file FIPS setting. No setting in the specification set seeds that generator from client-supplied input or otherwise parameterizes identifier generation, so reproducibility is fixed product behavior and the assessment objective is met by examining identifiers the instance issues rather than by setting a key.

*Citation.* splunk-launch.conf.spec:110-127 (SPLUNK_FIPS, module and algorithm selection). Web.conf.spec:920 (tools.sessions.on, the session layer that issues the identifier). A search of all 71 .conf.spec files for 'random.*(number|generator|seed)', 'entropy', 'csprng', 'nonce', 'session.?id' and 'sessionid' returned no key that parameterizes identifier generation; the only hits were limits.conf.spec:2470, a description of search-schedule jitter, and web.conf.spec:1285-1293, a caution that appserver debug logging can print session ID strings.

*Mechanism.* splunk-launch.conf SPLUNK_FIPS; web.conf [settings] tools.sessions.on (no key parameterizes identifier generation)

*Assessment method.* Authenticate twice under identical conditions and compare the two issued session identifiers for equality; run `splunk show fips-mode` as the Splunk service account to establish which cryptographic module produced them.

**SRG-APP-000224-WSR-000137** — CAT II — Applicable, evidence grade C.

The web server must generate a session ID long enough that it cannot be guessed through brute force.

*Basis.* Splunk Web issues a session identifier to every authenticated client, so a requirement on identifier length bears on this product. The specification set exposes no key that sets the length of that identifier: the length is fixed product behavior, not a site setting. The assessment objective is therefore met by measuring an identifier the instance issues, and the row cannot be closed from configuration alone.

*Citation.* web.conf.spec:920 (tools.sessions.on) and :977-978 (tools.sessions.storage_type, tools.sessions.storage_path) are the only keys governing the session layer. A search of all 71 .conf.spec files for 'session.*(length|entropy|charset|character)', 'session.?id' and 'sessionid' returned a single hit, web.conf.spec:1292, a caution that debug logging can print session ID strings; no length key exists in the 10.4.2 specification set.

*Mechanism.* web.conf [settings] tools.sessions.on (session layer); no key in the specification set sets session identifier length

*Assessment method.* Capture the session cookie issued to an authenticated session and measure the identifier's length, confirming it is at least 128 bits (16 bytes) of identifier material.

**SRG-APP-000224-WSR-000138** — CAT II — Applicable, evidence grade C.

The web server must generate a session ID using as much of the character set as possible to reduce the risk of brute force.

*Basis.* The requirement bears on the product because Splunk Web issues session identifiers, but the character set used to form them is fixed in the product: the specification set carries no key that selects or widens the alphabet. The assessment objective is met by enumerating the characters present in identifiers the instance issues.

*Citation.* web.conf.spec:920 (tools.sessions.on) is the session layer; the same search of all 71 .conf.spec files for 'session.*(length|entropy|charset|character)', 'session.?id' and 'sessionid' returned only web.conf.spec:1292, a debug-logging caution. No character-set key exists in the 10.4.2 specification set.

*Mechanism.* web.conf [settings] tools.sessions.on (session layer); no key in the specification set selects the session identifier character set

*Assessment method.* Capture several session identifiers issued by the instance and enumerate the distinct characters present, confirming coverage of at least A-Z, a-z and 0-9.

**SRG-APP-000224-WSR-000139** — CAT II — Applicable, evidence grade C.

The web server must generate unique session identifiers with definable entropy.

*Basis.* Entropy in the issued session identifier derives from the instance's cryptographic random number generator, and the only configuration that bears on it is the launch-file setting that selects the FIPS 140-2 validated module and algorithm set. Entropy is not a definable value in this product: the specification set carries no key that sets it. The requirement applies and the assessment objective is met by measuring identifiers the instance issues against their length.

*Citation.* splunk-launch.conf.spec:110-127 (SPLUNK_FIPS, FIPS Publication 140-2 algorithms and restrictions). A search of all 71 .conf.spec files for 'entropy' returned no hits, and the searches for 'session.?id', 'sessionid' and 'random.*(number|generator|seed)' returned no key that sets or reports identifier entropy.

*Mechanism.* splunk-launch.conf SPLUNK_FIPS (random number generator and algorithm selection); no key in the specification set defines session identifier entropy

*Assessment method.* Collect a sample of session identifiers from the instance and measure their entropy against their length; run `splunk show fips-mode` as the Splunk service account to establish which cryptographic module generated them.

**SRG-APP-000225-WSR-000074** — CAT II — Applicable, evidence grade C.

The web server must augment re-creation to a stable and known baseline.

*Basis.* This requirement examines whether the product offers reinstallation from a known state and, failing that, whether it prohibits it. Splunk Enterprise holds its whole configuration in text conf files layered in a documented precedence between a shipped default layer and site layers, records a checksum of the package each app was installed from, and distributes app baselines from a deployment server repository to named server classes. Index data is addressed separately from configuration, so a rebuild does not entangle the two. Nothing in the product's configuration surface prohibits reinstallation to a known state.

*Citation.* app.conf.spec:121-167 ([install] state = disabled | enabled; install_source_checksum, 'Records a checksum of the tarball from which a given app was installed'; install_source_local_checksum). Serverclass.conf.spec:405-432 ([serverClass:<serverClassName>] with repositoryLocation, targetRepositoryLocation, stateOnClient = enabled | disabled | noop, restartIfNeeded). Deploymentclient.conf.spec:47 ([deployment-client]) and :248 ([target-broker:deploymentServer]). Splunk-launch.conf.spec:67-77 (SPLUNK_DB separates index data from the installation tree); indexes.conf.spec:412-468 (homePath, coldPath, thawedPath).

*Mechanism.* The conf-file layering system (shipped default layer plus site local layer) with app.conf [install] state, install_source_checksum, install_source_local_checksum; serverclass.conf [serverClass:<serverClassName>] repositoryLocation, targetRepositoryLocation, stateOnClient; deploymentclient.conf [deployment-client]; splunk-launch.conf SPLUNK_DB

*Assessment method.* Examine the configuration baseline held under version control and the deployment server repository; rebuild an instance from that baseline and compare `splunk btool <conf> list --debug` output, run as the Splunk service account, against the baseline for each conf file in scope.

**SRG-APP-000225-WSR-000140** — CAT II — Applicable, evidence grade C.

The web server must be built to fail to a known safe state if system initialization fails, shutdown fails, or aborts fail.

*Basis.* Splunk Enterprise carries settings whose stated function is halting work rather than continuing past a resource or file system failure. A disk usage floor pauses indexing and refuses to launch searches when free space falls below a configured threshold, and the file system lock check causes splunkd to refuse to start when it cannot confirm it can write to the file system correctly. These are the known-state behaviors this requirement examines, and both are addressable in product configuration.

*Citation.* server.conf.spec:1856-1890 ([diskUsage] minFreeSpace = <num>|<percentage>, 'Specifies a safe amount of space that must exist for splunkd to continue operating'; indexing is paused and a warning posted; pollingFrequency, pollingTimerFrequency). Splunk-launch.conf.spec:214-221 (OPTIMISTIC_ABOUT_FILE_LOCKING; when left at its default, splunkd cannot start if the locktest file system check fails). Server.conf.spec:1895 ([queue]).

*Mechanism.* server.conf [diskUsage] minFreeSpace, pollingFrequency, pollingTimerFrequency; server.conf [queue]; splunk-launch.conf OPTIMISTIC_ABOUT_FILE_LOCKING left at its default

*Assessment method.* Run `splunk btool server list --debug` as the Splunk service account and examine [diskUsage] and [queue]; examine the launch file and confirm OPTIMISTIC_ABOUT_FILE_LOCKING is absent or 0; compare the resulting failure behaviors against the failure states named in the system's risk analysis documentation.

**SRG-APP-000225-WSR-000141** — CAT II — Applicable, evidence grade C.

The web server must provide a clustering capability.

*Basis.* The check text carries a conditional Not Applicable clause, 'If the web server is not a high-availability web server, this finding is NA.' That clause turns on how a particular system is designated, not on a property of the product, so it cannot support a Not Applicable determination at the product level. On capability grounds the clause does not hold in either direction: Splunk Enterprise 10.4.2 ships both index replication clustering and search head clustering, each with its own stanza, plus cluster manager redundancy with automatic or manual switchover. The requirement applies and the clustering mechanism is named.

*Citation.* server.conf.spec:2430-2470 ([clustering] mode = [manager|peer|searchhead|disabled]; manager_uri; manager_switchover_mode = [disabled|auto|manual], with standby managers promoted by priority). Server.conf.spec:4458-4480 ([shclustering] disabled = <boolean>, 'Disables or enables search head clustering on this instance'; mgmt_uri; servers_list; captain election). Server.conf.spec:4087 and :4118 ([replication_port://<port>], [replication_port-ssl://<port>]); :5137 and :5169 (the search head cluster replication port stanzas).

*Mechanism.* server.conf [clustering] mode, manager_uri, manager_switchover_mode, replication_factor; server.conf [shclustering] disabled, mgmt_uri, servers_list; server.conf [replication_port://<port>] and [replication_port-ssl://<port>]

*Assessment method.* Run `splunk btool server list --debug` as the Splunk service account and examine [clustering] and [shclustering]; compare the result against the availability requirement recorded for the system, since the clause's condition is settled by that designation and not by the product.

**SRG-APP-000231-WSR-000144** — CAT II — Applicable, evidence grade C.

Information at rest must be encrypted using a DOD-accepted algorithm to protect the confidentiality and integrity of the information.

*Basis.* Splunk Enterprise exposes at-rest encryption configuration for the index data it holds on remote object storage volumes, including a client-side scheme with a named AES-256-GCM algorithm and an external key provider gated by its own capability, and it stores configured service credentials in encrypted rather than clear-text form. Index data held on local storage has no product-level encryption key; for that data the control is provided by the host storage baseline and is assessed there. The requirement applies to the product because part of its data-at-rest surface is governed by product configuration.

*Citation.* indexes.conf.spec:2018-2019 (volume stanzas are written [volume:<volume_name>]); :2411-2424 (remote.s3.encryption = sse-s3 | sse-kms | sse-c | cse | none, 'The encryption scheme to use for data buckets that are currently being stored (data at rest)'); :2440-2447 (remote.s3.encryption.cse.algorithm = aes-256-gcm); :2448-2466 (remote.s3.encryption.cse.key_type, key_refresh_interval); :2786-2790 (remote.gs.encryption). Distsearch.conf.spec:557-563 (remote.s3.encryption). Authorize.conf.spec:544-547 ([capability::edit_encryption_key_provider], Server-Side Encryption for a remote storage volume). Splunk-launch.conf.spec:110-127 (SPLUNK_FIPS constrains the algorithm set).

*Mechanism.* indexes.conf [volume:<volume_name>] remote.s3.encryption, remote.s3.encryption.cse.algorithm, remote.s3.encryption.cse.key_type, remote.gs.encryption; distsearch.conf remote.s3.encryption; authorize.conf [capability::edit_encryption_key_provider]; splunk-launch.conf SPLUNK_FIPS

*Assessment method.* Run `splunk btool indexes list --debug` as the Splunk service account and examine each [volume:...] stanza's encryption keys and the algorithm named; for buckets held on local storage, examine the host storage baseline's at-rest encryption and the algorithm it uses.

**SRG-APP-000233-WSR-000146** — CAT II — Applicable, evidence grade C.

The web server document directory must be in a separate partition from the web servers system files.

*Basis.* Splunk Enterprise lets the site place the data the instance serves on a file system separate from the program files, through one launch-file setting and the per-index path keys that reference it. It exposes no setting that relocates the app and configuration tree off the installation directory: a search of the specification set for a configuration or etc path variable returned no result. The requirement therefore applies, and the portion addressable in product configuration is the data path; creating and mounting the partition itself is a host operating system function.

*Citation.* splunk-launch.conf.spec:67-77 (SPLUNK_DB = <string>, 'The fully qualified path to the directory containing the index directories', 'Primarily used by paths expressed in indexes.conf'). Indexes.conf.spec:412-415 (homePath = <string>, with the documented form homePath = $SPLUNK_DB/$_index_name/db); :446 (coldPath); :468 (thawedPath); :531 (tstatsHomePath). A search of all 71 .conf.spec files for 'SPLUNK_ETC' returned no hits, and splunk-launch.conf.spec enumerates SPLUNK_HOME and SPLUNK_DB only, so no key relocates the app and configuration tree.

*Mechanism.* splunk-launch.conf SPLUNK_DB; indexes.conf homePath, coldPath, thawedPath, tstatsHomePath

*Assessment method.* Run `splunk btool indexes list --debug` as the Splunk service account to resolve each index's homePath, coldPath and thawedPath, and examine the launch file for SPLUNK_DB; compare the resolved paths against the host's mount table to confirm they resolve to a file system other than the one holding the program files.

**SRG-APP-000246-WSR-000149** — CAT II — Applicable, evidence grade C.

The web server must restrict the ability of users to launch Denial of Service (DoS) attacks against other information systems or networks.

*Basis.* The paths by which a Splunk user could direct traffic at another information system are alert actions, forwarding outputs and search commands that reach outside the instance. Each is gated by a named capability and bounded by named rate and result limits, and 10.4.2 carries an allow list that restricts the destinations to which the webhook alert action will send. The requirement is implementable and assessable in product configuration.

*Citation.* alert_actions.conf.spec:599-622 ([webhook] enable_allowlist = <boolean>, 'Whether or not the Splunk platform alert webhook uses the webhook allowlist'; allowlist.<name> = <regular expression>, which must be set when the allow list is enabled); :517 ([script]); :157 ([email]). Limits.conf.spec:3915 ([scheduler]) with :4033 (max_action_results), :4056-4067 (max_per_result_alerts, max_per_result_alerts_time), :4068 (max_searches_perc); :315 ([search]) with :457 (max_searches_per_cpu). Authorize.conf.spec:946 (schedule_search), :638-639 (edit_scripted), :699 (edit_tcp), :716 (edit_udp), :909-913 (run_dump, run_custom_command).

*Mechanism.* alert_actions.conf [webhook] enable_allowlist, allowlist.<name>; alert_actions.conf [script] and [email]; limits.conf [scheduler] max_per_result_alerts, max_per_result_alerts_time, max_action_results, max_searches_perc; limits.conf [search] max_searches_per_cpu; authorize.conf capabilities schedule_search, edit_scripted, run_custom_command, run_dump, edit_tcp, edit_udp

*Assessment method.* Run `splunk btool alert_actions list --debug` as the Splunk service account and examine [webhook] enable_allowlist and its allowlist entries; run `splunk btool limits list --debug` for [scheduler] and [search]; run `splunk btool authorize list --debug` and enumerate the roles holding the outbound-capable capabilities.

**SRG-APP-000251-WSR-000157** — CAT II — Applicable, evidence grade C.

The web server must limit the character set used for data entry.

*Basis.* Splunk Enterprise exposes the character set of its data-entry paths through its own configuration, so the requirement reaches the application. In web.conf [settings], tools.decode.on fixes the codec by which strings entering the Splunk Web controller methods are decoded, tools.encode.on and tools.encode.encoding fix the outgoing codec and override the client's Accept-Charset negotiation, and override_JSON_MIME_type_with_text_plain fixes the character set declared on JSON responses. For data entering the indexing pipeline, props.conf CHARSET declares the character set per source type. The product does not expose a per-field allowed-character list or a request-level character allow list, so the control available is codec-level: the assessment objective is met by fixing the accepted and emitted character set rather than by enumerating permitted characters. That is a configuration property of Splunk, not of another baseline.

*Citation.* web.conf.spec:985 tools.decode.on; web.conf.spec:992 tools.encode.on; web.conf.spec:999 tools.encode.encoding, documented as forcing UTF-8 output in place of CherryPy observing the client Accept-Charset header; web.conf.spec:364 override_JSON_MIME_type_with_text_plain; props.conf.spec:238 CHARSET. Searched all 67 .conf.spec files of the specification set for charset, character set and encoding vocabulary; the data-entry hits are confined to web.conf.spec, props.conf.spec and authentication.conf.spec:265. Tools.decode.on and tools.encode.encoding confirmed present and readable on a Splunk 10.4.2 instance (build 33c3bf42cd73) with splunk btool web list --debug.

*Mechanism.* web.conf [settings] tools.decode.on, tools.encode.on, tools.encode.encoding, override_JSON_MIME_type_with_text_plain; props.conf [<spec>] CHARSET

*Assessment method.* Run splunk btool web list --debug as the Splunk service account and examine tools.decode.on, tools.encode.on, tools.encode.encoding and override_JSON_MIME_type_with_text_plain; run splunk btool props list --debug and examine CHARSET for each source type in scope. Determine Satisfied when the character set is fixed by configuration rather than negotiated from the client.

**SRG-APP-000251-WSR-000194** — CAT II — Applicable, evidence grade C.

The web server must interpret and normalize ambiguous HTTP requests or terminate the TCP connection.

*Basis.* Splunk Enterprise operates its own HTTP listeners - the management and REST port, Splunk Web, and the HTTP Event Collector - so the requirement reaches the application rather than only a front end. The product exposes forceHttp10 on both the splunkd HTTP server and Splunk Web; set to always, the listener withholds HTTP/1.1 features including chunked transfer encoding, which removes the Content-Length and Transfer-Encoding combination the requirement describes. Max_content_length rejects requests whose content length exceeds the configured bound, and tools.proxy.on with tools.proxy.base determine whether X-Forwarded headers from a front end are consumed as authoritative. What the product does not expose is a setting that normalizes an ambiguous request, a setting that drops an unnormalizable request and closes the connection, or an HTTP/2 listener option. Where the requirement is met by front-end normalization, that half is performed by the reverse proxy or load balancer baseline placed in front of Splunk; the back-end half named in the fix text is configurable in Splunk, so the requirement is applicable and is not inherited in whole.

*Citation.* web.conf.spec:1129 forceHttp10 = auto|never|always, documented as withholding HTTP/1.1 features including chunked transfer encoding when set to always; server.conf.spec:1416 forceHttp10 for the splunkd HTTP server; server.conf.spec:1369 max_content_length, documented as rejecting HTTP requests above the configured size; web.conf.spec:1016 tools.proxy.on; web.conf.spec:867 max_upload_size. Searched all 67 .conf.spec files for smuggling, Transfer-Encoding, Content-Length, HTTP/2 and chunked vocabulary, and separately for malformed, ambiguous, normalize, invalid request, invalid header and bad request: no normalization or rejection setting and no HTTP/2 listener setting exist anywhere in the specification set. ForceHttp10 and max_content_length confirmed present and readable on a Splunk 10.4.2 instance (build 33c3bf42cd73) with splunk btool web list --debug and splunk btool server list httpServer --debug.

*Mechanism.* web.conf [settings] forceHttp10, max_upload_size, tools.proxy.on, tools.proxy.base; server.conf [httpServer] forceHttp10, max_content_length

*Assessment method.* Run splunk btool web list --debug and splunk btool server list httpServer --debug as the Splunk service account and examine forceHttp10 and max_content_length for each listener in scope. Test each listener with a request carrying both Content-Length and Transfer-Encoding headers, and with a request declaring a zero-length body, and determine whether the listener rejects the request and closes the connection. Where a reverse proxy or load balancer fronts Splunk, assess that baseline's normalization configuration as a separate determination against the same requirement.

**SRG-APP-000266-WSR-000142** — CAT II — Applicable, evidence grade C.

The web server must display a default hosted application web page, not a directory listing, when a requested web page cannot be found.

*Basis.* Splunk Web serves a static document directory, so the requirement reaches the application. The product addresses the requirement's objective at the Splunk instance rather than per directory: tools.staticdir.generate_indexes determines whether the web server generates a directory listing for static directories at all, so the enumeration technique the discussion describes can be denied outright instead of masked by placing an index page in each directory. Static_dir and static_endpoint define the document directory and the URI path at which it is exposed, and root_endpoint the URI prefix, which together bound the directories in scope for the assessment; simple_error_page determines the content of the page returned when a requested page cannot be found. The key is documented in the specification set and ships commented in the default web.conf, so it is settable; where it is not written, the documented default applies and btool reports no value for it.

*Citation.* web.conf.spec:333 tools.staticdir.generate_indexes = [1 | 0], documented default 0, described as controlling whether the webserver serves a directory listing for static directories. The same key appears commented at line 170 of the shipped default web.conf, and the spec file inside a Splunk 10.4.2 installation carries it (grep -c against the installation README copy of web.conf.spec returned 1). Scoping keys: web.conf.spec:297 root_endpoint, web.conf.spec:303 static_endpoint, web.conf.spec:308 static_dir; web.conf.spec:227 simple_error_page.

*Mechanism.* web.conf [settings] tools.staticdir.generate_indexes; scoping and supporting keys static_dir, static_endpoint, root_endpoint, simple_error_page

*Assessment method.* Run splunk btool web list --debug as the Splunk service account and examine tools.staticdir.generate_indexes, static_endpoint and static_dir; where the key is absent from btool output the documented default applies. Corroborate by requesting the static endpoint and a subdirectory of it that holds no index page, and determining whether a directory listing is returned. Determine Satisfied when directory index generation is off, or when every served document directory returns a default page.

**SRG-APP-000266-WSR-000159** — CAT II — Applicable, evidence grade C.

Warning and error messages displayed to clients must be modified to minimize the identity of the web server, patches, loaded modules, and directory paths.

*Basis.* The check text looks for a mode of operation that minimizes the information returned to clients on error conditions, and Splunk Enterprise exposes exactly that choice. Simple_error_page selects between a page carrying only the HTTP error status and a verbose page that the specification set describes as carrying debug output, referrer, crash information, a message, a results link and a byline. Request.show_tracebacks determines whether a Python traceback is rendered to the user on a fatal exception; a traceback discloses module names and paths inside the installation, which is the class of information the requirement restricts. AppServerProcessLogStderr determines whether application server standard error, which the specification set warns may carry session identifier strings, is written into the Splunk log. These are settings of the Splunk application itself, so the requirement applies to it and is not inherited from the host or the container platform.

*Citation.* web.conf.spec:227 simple_error_page, whose description contrasts a simplified page containing only the error status against a more verbose page containing the home link, message, results link, crashes, referrer, debug output and byline; web.conf.spec:910 request.show_tracebacks, described as controlling whether an exception traceback is displayed to the user on fatal exceptions; web.conf.spec:1285 appServerProcessLogStderr, whose description warns that application server code may print sensitive information such as session ID strings to standard error. All three confirmed present and readable on a Splunk 10.4.2 instance (build 33c3bf42cd73) with splunk btool web list --debug.

*Mechanism.* web.conf [settings] simple_error_page, request.show_tracebacks, appServerProcessLogStderr

*Assessment method.* Run splunk btool web list --debug as the Splunk service account and examine simple_error_page, request.show_tracebacks and appServerProcessLogStderr. Corroborate by requesting a nonexistent path and a path that forces a server-side error, then examining the returned body and headers for product name and version, build, installed modules or installation paths. Determine Satisfied when the returned page carries the error status without product or path detail.

**SRG-APP-000266-WSR-000160** — CAT II — Applicable, evidence grade C.

Debugging and trace information used to diagnose the web server must be disabled.

*Basis.* Splunk Enterprise exposes each debugging and trace facility the requirement names as a distinct setting, so the requirement is implemented through the product's own configuration. EnableWebDebug controls whether the debug REST endpoints under /debug are reachable. Request.show_tracebacks controls whether a traceback is rendered to the user. Js_logger_mode selects the client-side JavaScript logger mode and includes a mode that posts log messages to a server endpoint, with js_logger_mode_server_end_point, poll buffer and max buffer as its supporting keys. Simple_xml_perf_debug controls whether dashboards emit performance metrics to the browser console. AppServerProcessLogStderr controls whether application server standard error reaches the Splunk log. Engine.autoreload.on is a development facility that restarts the application server when a Python file changes. The assessment is an examination of these keys against the product's documented defaults.

*Citation.* web.conf.spec:1295 enableWebDebug, documented as controlling whether the debug REST endpoints, for example /debug/**splat, are accessible, default false; web.conf.spec:910 request.show_tracebacks; web.conf.spec:379 js_logger_mode = [None | Firebug | Server], default None, with web.conf.spec:390, 395 and 399 as its supporting keys; web.conf.spec:1054 simple_xml_perf_debug; web.conf.spec:1285 appServerProcessLogStderr; web.conf.spec:915 engine.autoreload.on. EnableWebDebug, request.show_tracebacks, js_logger_mode and appServerProcessLogStderr confirmed present and readable on a Splunk 10.4.2 instance (build 33c3bf42cd73) with splunk btool web list --debug.

*Mechanism.* web.conf [settings] enableWebDebug, request.show_tracebacks, js_logger_mode, simple_xml_perf_debug, appServerProcessLogStderr, engine.autoreload.on

*Assessment method.* Run splunk btool web list --debug as the Splunk service account and examine enableWebDebug, request.show_tracebacks, js_logger_mode, simple_xml_perf_debug, appServerProcessLogStderr and engine.autoreload.on; where a key is absent from btool output the documented default applies. Corroborate enableWebDebug by requesting a path under the /debug endpoint and determining whether it is served.

**SRG-APP-000295-AU-000190** — CAT II — Applicable, evidence grade C.

The Central Log Server must automatically terminate a user session after organization-defined conditions or trigger events requiring session disconnect.

*Basis.* Splunk Web expires a user session after a configured number of minutes of inactivity, and splunkd bounds the session lifetime independently as a time range. Those are the two session-termination conditions the product expresses in configuration; conditions such as time-of-day restriction or an incident-driven termination are not expressible as session-termination triggers anywhere in the specification set. The product STIG fix text names tools.session.timeout, which does not exist in 10.4.2; the implemented key is tools.sessions.timeout, which the same rule's check text spells correctly.

*Citation.* web.conf.spec:924 (tools.sessions.timeout, "number of minutes of inactivity before a user session is expired"), :403 (ui_inactivity_timeout), stanza [settings] at web.conf.spec:16; server.conf.spec:73 (sessionTimeout), stanza [general] at server.conf.spec:43. On a live Splunk Enterprise 10.4.2 instance all three keys are present in the merged surface, and a search of that surface for tools.session.timeout returns 0 lines.

*Mechanism.* web.conf [settings]: tools.sessions.timeout, ui_inactivity_timeout; server.conf [general]: sessionTimeout

*Assessment method.* splunk btool web list settings --debug and splunk btool server list general --debug, examining tools.sessions.timeout, ui_inactivity_timeout and sessionTimeout; record the organization-defined conditions from the system security plan and compare. Apply the product STIG's own role scoping: the web-tier portion is assessed on instances that run Splunk Web.

*Product reference.* SPLK-CL-000010 — renamed

**SRG-APP-000295-WSR-000012** — CAT II — Applicable, evidence grade C.

The web server must set an absolute session timeout value of eight hours or less.

*Basis.* An absolute bound on session lifetime is expressible in configuration. Server.conf sessionTimeout states the amount of time before a user session times out as a search-like time range, which admits a value of eight hours or less, and web.conf tools.sessions.restart_persist governs whether the Splunk Web session cookie survives a browser restart rather than being discarded. The requirement therefore applies to the application and is implemented by its own settings.

*Citation.* server.conf.spec:73 (sessionTimeout = <nonnegative integer>[s|m|h|d]), stanza [general] at server.conf.spec:43; web.conf.spec:924 (tools.sessions.timeout), :934 (tools.sessions.restart_persist), stanza [settings] at web.conf.spec:16. On a live Splunk Enterprise 10.4.2 instance sessionTimeout is present in the merged server configuration.

*Mechanism.* server.conf [general]: sessionTimeout; web.conf [settings]: tools.sessions.timeout, tools.sessions.restart_persist

*Assessment method.* splunk btool server list general --debug for sessionTimeout, and splunk btool web list settings --debug for tools.sessions.timeout and tools.sessions.restart_persist; convert the configured time range to hours and compare against the eight-hour bound.

*Product reference.* SPLK-CL-000010 — renamed

**SRG-APP-000295-WSR-000134** — CAT II — Applicable, evidence grade C.

The web server must set an inactive timeout for sessions.

*Basis.* Splunk Web implements an inactivity timeout directly: tools.sessions.timeout is defined as the minutes of inactivity before a user session is expired. The specification set states that the countdown is reset by browser activity until ui_inactivity_timeout is reached, so both settings are part of the mechanism and an assessment that examines only one will not establish the effective inactivity bound.

*Citation.* web.conf.spec:924-932 (tools.sessions.timeout and the statement that the countdown resets through browser activity until ui_inactivity_timeout is reached), :403-407 (ui_inactivity_timeout; a value below 1 results in no timeout notification ever being triggered), stanza [settings] at web.conf.spec:16. Both keys are present in the merged web surface of a live Splunk Enterprise 10.4.2 instance.

*Mechanism.* web.conf [settings]: tools.sessions.timeout, ui_inactivity_timeout

*Assessment method.* splunk btool web list settings --debug, examining tools.sessions.timeout and ui_inactivity_timeout together, and compare the effective bound against the risk tier assigned to the application in the system security plan.

*Product reference.* SPLK-CL-000010 — renamed

**SRG-APP-000296-AU-000560** — CAT II — Applicable, evidence grade C.

The Central Log Server must provide a logout capability for user initiated communication session.

*Basis.* Splunk Web presents a user-initiated logout control, and the configuration surface governs what that logout invalidates. InvalidateSessionTokensOnLogout extends token invalidation across search head cluster members, logoutCacheRefreshInterval governs the synchronization interval for that state, and the SAML single-logout settings propagate the logout to the identity provider. The capability is present in the product and its reliability is configurable, so the requirement applies.

*Citation.* server.conf.spec:81 (invalidateSessionTokensOnLogout), :89 (logoutCacheRefreshInterval), stanza [general] at server.conf.spec:43; authentication.conf.spec:687 (idpSLOUrl, the SP-initiated single logout endpoint), :1109 (sloBinding), :780 (redirectAfterLogoutToUrl). InvalidateSessionTokensOnLogout is present in the merged server configuration of a live Splunk Enterprise 10.4.2 instance.

*Mechanism.* server.conf [general]: invalidateSessionTokensOnLogout, logoutCacheRefreshInterval; authentication.conf [<saml-authSettings-key>]: idpSLOUrl, sloBinding, redirectAfterLogoutToUrl

*Assessment method.* splunk btool server list general --debug for invalidateSessionTokensOnLogout; then test by authenticating to Splunk Web, invoking logout, and confirming the prior session key is rejected, for example a request to /services/authentication/current-context carrying the retired key returning 401.

**SRG-APP-000315-WSR-000003** — CAT II — Applicable, evidence grade C.

Remote access to the web server must follow access policy or work in conjunction with enterprise tools designed to enforce policy requirements.

*Basis.* The requirement names IP filtering, HTTPS in place of HTTP, secure tokens and user validation as the enforcement methods, and Splunk Enterprise exposes all of them in its own configuration: transport protection and optional client-certificate requirement for Splunk Web, an ordered network access control list for admission, and delegation of user validation to an enterprise identity service through authType. The requirement applies and is implemented by the application.

*Citation.* web.conf.spec:70 (enableSplunkWebSSL), :75 (privKeyPath), :82 (serverCert), :151 (requireClientCert), :239 (sslVersions), :1080 (acceptFrom), stanza [settings] at web.conf.spec:16; authentication.conf.spec:30 (authType = [Splunk|LDAP|Scripted|SAML|ProxySSO]), :44 (authSettings), stanza [authentication] at authentication.conf.spec:26; server.conf.spec:1345 (acceptFrom), stanza [httpServer] at server.conf.spec:1291. EnableSplunkWebSSL, privKeyPath, serverCert, acceptFrom and authType are all present in the merged configuration of a live Splunk Enterprise 10.4.2 instance.

*Mechanism.* web.conf [settings]: enableSplunkWebSSL, privKeyPath, serverCert, requireClientCert, sslVersions, acceptFrom; authentication.conf [authentication]: authType, authSettings; server.conf [httpServer]: acceptFrom

*Assessment method.* splunk btool web list settings --debug for enableSplunkWebSSL, requireClientCert, sslVersions and acceptFrom; splunk btool authentication list authentication --debug for authType; compare against the remote access policy recorded in the system security plan, or identify the enterprise access tool enforcing it.

**SRG-APP-000315-WSR-000004** — CAT II — Applicable, evidence grade C.

The web server must restrict inbound connections from nonsecure zones.

*Basis.* Splunk Enterprise implements an application-level network access control list. AcceptFrom takes an ordered list of single addresses, CIDR blocks, DNS names with wildcards, or "*", and an entry prefixed with "!" rejects the connection, with the first matching rule applied. The setting is available at the Splunk Web tier, the management tier and each data input, so admission can be denied by zone inside the application. Its shipped default is "*", which accepts from anywhere, so restriction is an operator action and the requirement applies rather than being met by the product's own defaults.

*Citation.* web.conf.spec:1080-1098 (acceptFrom, rule formats, "!" reject prefix at :1091, default "*"), stanza [settings] at web.conf.spec:16; server.conf.spec:1345-1359 (acceptFrom with the same syntax, reject prefix at :1355), stanza [httpServer] at server.conf.spec:1291; inputs.conf.spec:577, :687, :908, :1309, :1327, :1796 (acceptFrom on receiving input stanzas). AcceptFrom is present in the merged web configuration of a live Splunk Enterprise 10.4.2 instance.

*Mechanism.* web.conf [settings]: acceptFrom; server.conf [httpServer]: acceptFrom; inputs.conf receiving stanzas: acceptFrom

*Assessment method.* splunk btool web list settings --debug, splunk btool server list httpServer --debug and splunk btool inputs list --debug, examining each acceptFrom rule list, in order, against the zones the organization has defined as nonsecure.

**SRG-APP-000316-WSR-000170** — CAT II — Applicable, evidence grade C.

The web server must provide the capability to immediately disconnect or disable remote access to the hosted applications.

*Basis.* The product provides graduated means of severing remote access from within its own configuration: startwebserver disables Splunk Web outright, httpport omitted or 0 prevents an HTTP listener from starting, an acceptFrom reject rule withdraws admission for a given network without stopping the service, and an individual receiving input can be disabled on its own. This satisfies the requirement's stated need to disconnect access to one hosted function without compromising the others, so the requirement applies to the application.

*Citation.* web.conf.spec:23 (startwebserver = [0|1], "0 disables Splunk Web"), :28 (httpport; if omitted or 0 no HTTP listener starts), :1080-1098 (acceptFrom with the "!" reject prefix at :1091), stanza [settings] at web.conf.spec:16; server.conf.spec:1345 (acceptFrom), stanza [httpServer] at server.conf.spec:1291. Startwebserver is present in the merged web configuration of a live Splunk Enterprise 10.4.2 instance.

*Mechanism.* web.conf [settings]: startwebserver, httpport, acceptFrom; server.conf [httpServer]: acceptFrom; inputs.conf per-input disabled setting

*Assessment method.* splunk btool web list settings --debug for startwebserver and acceptFrom; examine the documented incident procedure that names which control is used and who may invoke it; where a test is authorized, exercise the disconnection in a maintenance window and confirm that indexing continues.

**SRG-APP-000334-WSR-000024** — CAT II — Applicable, evidence grade C.

The web server must uniquely identify and authenticate source by organization, system, application, and/or individual for information transfer.

*Basis.* Splunk Enterprise authenticates the sending peer of a data transfer and attributes each received event to its origin. A receiving instance can require a certificate authority signed client certificate on the data port, a forwarder presents a client certificate on its outbound connection, and the input's host and connection_host settings fix the identity of the originating device, with index-time override available through props.conf and transforms.conf. All four settings named by the product STIG rules that share these CCIs exist in 10.4.2.

*Citation.* inputs.conf.spec:876 ([splunktcp-ssl:<port>]), :926-928 (serverCert, sslPassword, requireClientCert), :986 ([SSL]), :990, :1002, :1015; :526 and :1244 (connection_host = [ip|dns|none]); :1227 and :1314 (the udp stanzas the product STIG directs be replaced by TCP still exist, so the condition it checks is still expressible); outputs.conf.spec:652 and :884 (clientCert), :889 (sslPassword), :700 and :917 (sslVerifyServerCert); props.conf.spec:1043 (TRANSFORMS-<class>) with transforms.conf.spec:241 (DEST_KEY); web.conf.spec:70 (enableSplunkWebSSL), :75 (privKeyPath), :82 (serverCert). RequireClientCert is present in the merged input configuration of a live Splunk Enterprise 10.4.2 instance.

*Mechanism.* inputs.conf [splunktcp-ssl:<port>] and [SSL]: serverCert, sslPassword, requireClientCert; inputs.conf receiving stanzas: host, connection_host; outputs.conf [tcpout:<group>]: clientCert, sslPassword, sslVerifyServerCert; props.conf TRANSFORMS-<class> with transforms.conf DEST_KEY = MetaData:Host; web.conf [settings]: enableSplunkWebSSL, privKeyPath, serverCert

*Assessment method.* splunk btool inputs list --debug for splunktcp-ssl stanzas, requireClientCert, connection_host and any udp stanza; splunk btool outputs list --debug for clientCert; splunk btool web list settings --debug for enableSplunkWebSSL; and run the search index=_internal source=*metrics.log* group=tcpin_connections | dedup hostname | table _time hostname sourceIp destPort ssl to confirm every receiving connection reports ssl=true.

*Product reference.* SPLK-CL-000260, SPLK-CL-000270, SPLK-CL-000280, SPLK-CL-000290 — confirmed in 10 4 2

**SRG-APP-000340-WSR-000029** — CAT II — Applicable, evidence grade C.

Non-privileged accounts on the hosting system must only access web server security-relevant information and functions through a distinct administrative account.

*Basis.* Splunk Enterprise gates each security-relevant function behind a named capability and grants capabilities only through roles, so administration can be held by a distinct role that non-privileged roles do not import. ImportRoles makes the inheritance chain explicit and grantableRoles bounds what a role may delegate. Protection of the installation directory and of the service account under which the software runs is provided by the host operating system baseline, but the separation this requirement names is implemented in the application's own authorization configuration, so the requirement applies here.

*Citation.* authorize.conf.spec:67 ([role_<roleName>]), :79 (importRoles), :86 (grantableRoles), :54 ([capability::<capability>]), :447 ([capability::admin_all_objects]), :479 ([capability::change_authentication]), :483 ([capability::change_audit]). On a live Splunk Enterprise 10.4.2 instance the merged authorization surface returns 26 role stanzas and 216 capability stanzas.

*Mechanism.* authorize.conf [role_<roleName>]: capability assignments, importRoles, grantableRoles; [capability::<capability>] definitions, including change_authentication, change_audit and admin_all_objects

*Assessment method.* splunk btool authorize list --debug to enumerate roles, their granted capabilities and their importRoles chains; then confirm that no role assigned to non-privileged users holds, or imports a role holding, admin_all_objects, change_authentication or change_audit, and that administrators hold those capabilities under a separate account.

**SRG-APP-000345-AU-000400** — CAT II — Applicable, evidence grade C.

The Central Log Server must automatically lock the account until the locked account is released by an administrator when three unsuccessful login attempts in 15 minutes are exceeded.

*Basis.* Splunk native authentication counts unsuccessful logins and locks the account. The attempt count and the counting window are both configurable, so a threshold of three attempts within fifteen minutes is expressible. Two product characteristics bear on the assessment and should be stated: lockoutMins accepts a maximum of 1440, so the native lockout releases automatically within 24 hours rather than persisting until an administrator releases it, and the specification set states that lockout state applies per search head cluster member rather than cluster-wide. Where authType delegates authentication, the failed-attempt counter is held by the external provider rather than by these keys. The setting named by the product STIG exists in 10.4.2.

*Citation.* authentication.conf.spec:514 (lockoutUsers), :532 (lockoutAttempts), :543 (lockoutThresholdMins), :521-526 (lockoutMins, minimum 1, maximum 1440), :517 and :528 (lockout state per search head cluster member), stanza [splunk_auth] at authentication.conf.spec:437; authentication.conf.spec:30 (authType) determines which authority holds the counter. All four lockout keys are present in the merged authentication configuration of a live Splunk Enterprise 10.4.2 instance.

*Mechanism.* authentication.conf [splunk_auth]: lockoutUsers, lockoutAttempts, lockoutThresholdMins, lockoutMins

*Assessment method.* splunk btool authentication list splunk_auth --debug for lockoutUsers, lockoutAttempts, lockoutThresholdMins and lockoutMins, and splunk btool authentication list authentication --debug for authType; where authentication is delegated, obtain the lockout result from the identity provider's baseline instead.

*Product reference.* SPLK-CL-000070 — confirmed in 10 4 2

**SRG-APP-000357-WSR-000150** — CAT II — Applicable, evidence grade C.

The web server must use a logging mechanism that is configured to allocate log record storage capacity large enough to accommodate the logging requirements of the web server.

*Basis.* Splunk allocates storage for its web-tier log files through size and file-count settings, for its own process log output through rotation settings, and for the indexed copy through per-index, per-path and per-volume size limits with a free-space floor. Log record storage capacity allocation is therefore a product setting and the requirement applies to the application.

*Citation.* web.conf.spec:876 log.access_maxsize, :884 log.access_maxfiles, :891 log.error_maxsize, :899 log.error_maxfiles; server.conf.spec:1680 [stderr_log_rotation] with maxFileSize at :1686 and BackupIndex at :1694; indexes.conf.spec:610 maxTotalDataSizeMB, :1175 homePath.maxDataSizeMB, :1187 coldPath.maxDataSizeMB, :2078 maxVolumeDataSizeMB; server.conf.spec:1856 [diskUsage] with minFreeSpace at :1858. Confirmed readable on 10.4.2 with btool web list settings --debug, btool indexes list --debug and btool server list diskUsage --debug.

*Mechanism.* web.conf [settings] log.access_maxsize, log.access_maxfiles, log.error_maxsize, log.error_maxfiles; server.conf [stderr_log_rotation] maxFileSize and BackupIndex; indexes.conf maxTotalDataSizeMB, homePath.maxDataSizeMB, coldPath.maxDataSizeMB and [volume:<name>] maxVolumeDataSizeMB; server.conf [diskUsage] minFreeSpace

*Assessment method.* Run `splunk btool web list settings --debug`, `splunk btool indexes list --debug` and `splunk btool server list diskUsage --debug`, and compare the allocated sizes against the sizes of the underlying volumes and against the retention period and the expected daily log volume.

**SRG-APP-000358-AU-000100** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured to off-load log records onto a different system or media than the system being audited.

*Basis.* The requirement's own clause reads "Note: This is not applicable (NA) if an external application or operating system manages this function." That condition describes a delegation choice at a particular deployment rather than a property of the product, and Splunk manages off-loading natively, so the clause does not support a product-level determination of Not Applicable and grade B is unavailable.

*Citation.* outputs.conf.spec:61 [tcpout], :121 [tcpout:<target_group>], :123 server, :1058 [syslog], :1077 [syslog:<target_group>], :1082 server; inputs.conf.spec:626 [splunktcp], :876 [splunktcp-ssl:<port>]; indexes.conf.spec:543 remotePath. The referenced product STIG rule names outputs.conf on the forwarder and inputs.conf on the indexer; both files and the named stanzas exist in 10.4.2.

*Mechanism.* outputs.conf [tcpout] and [tcpout:<target_group>] server, and [syslog:<target_group>] server for a non-Splunk receiver; indexes.conf remotePath; inputs.conf [splunktcp] on the receiving instance

*Assessment method.* Run `splunk btool outputs list --debug` and record the target groups and their server settings, `splunk btool inputs list --debug` on the receiving instance for the receiving stanza, and `splunk btool indexes list --debug` for remotePath; confirm the destination is a different system or medium from the one being audited.

*Product reference.* SPLK-CL-000150 — confirmed in 10 4 2

**SRG-APP-000358-WSR-000063** — CAT II — Applicable, evidence grade C.

The web server must not impede the ability to write specified log record content to an audit log server.

*Basis.* Splunk exposes forwarding of its own records, including its web-tier records, to a separate receiver over either the Splunk-to-Splunk protocol or syslog, and exposes a file input that can read the web access log for transfer. Nothing in the product's configuration surface blocks that path, so the requirement applies to the application.

*Citation.* outputs.conf.spec:121 [tcpout:<target_group>] with server at :123, :1077 [syslog:<target_group>] with server at :1082; inputs.conf.spec:626 [splunktcp], :514 [tcp://<remote server>:<port>]; web.conf.spec:871 log.access_file names the file an input can read. A [tcpout] stanza is present in outputs.conf on 10.4.2.

*Mechanism.* outputs.conf [tcpout:<target_group>] server and [syslog:<target_group>] server; inputs.conf monitor stanza over the file named by web.conf [settings] log.access_file

*Assessment method.* Run `splunk btool outputs list --debug` for the target groups and `splunk btool inputs list --debug` for the stanza reading the web log; generate a web-tier event and confirm the record arrives at the separate audit log server.

*Product reference.* SPLK-CL-000150 — confirmed in 10 4 2

**SRG-APP-000358-WSR-000163** — CAT II — Applicable, evidence grade C.

The web server must be configurable to integrate with an organizations security infrastructure.

*Basis.* Splunk exposes export of its records to an external review-and-alert tool and exposes notification channels that deliver alerts into the organization's tooling, both through configuration. Integration with an external security infrastructure is therefore a product capability and the requirement applies to the application.

*Citation.* outputs.conf.spec:121 [tcpout:<target_group>], :1077 [syslog:<target_group>] with server at :1082; alert_actions.conf.spec:157 [email], :599 [webhook], :517 [script]; savedsearches.conf.spec:300 action.email with :304 action.email.to; health.conf.spec:217 [alert_action:*] with action.<action parameter> at :222.

*Mechanism.* outputs.conf [tcpout:<target_group>] and [syslog:<target_group>] for record export; alert_actions.conf [email], [webhook] and [script] with savedsearches.conf action.* for notification; health.conf [alert_action:*] action.<parameter>

*Assessment method.* Run `splunk btool outputs list --debug` for the export target groups, `splunk btool alert_actions list --debug` for the enabled notification channels, and `splunk btool health list --debug` for the health alert actions; confirm records and alerts reach the named organizational tool.

*Product reference.* SPLK-CL-000150 — confirmed in 10 4 2

**SRG-APP-000359-WSR-000065** — CAT II — Applicable, evidence grade C.

The web server must use a logging mechanism that is configured to provide a warning to the ISSO and SA when allocated record storage volume reaches 75% of maximum log record storage capacity.

*Basis.* The same native free-space monitoring and alert delivery that covers the index volumes covers the volume holding the web-tier logs, and the web-tier allocation the warning is measured against is itself a product setting. A scheduled alert over the indexed records is a second product path to the same objective, so the requirement applies to the application.

*Citation.* server.conf.spec:1858 minFreeSpace; health.conf.spec:93 alert.actions, :101 alert.threshold_color, :217 [alert_action:*] with action.<action parameter> at :222; web.conf.spec:876 log.access_maxsize, :884 log.access_maxfiles; savedsearches.conf.spec:270 alert_condition, :300 action.email, :304 action.email.to. Confirmed readable on 10.4.2 with btool web list settings --debug and btool health list alert_action:email --debug.

*Mechanism.* server.conf [diskUsage] minFreeSpace with health.conf [feature:disk_space] indicator thresholds and [alert_action:email] action.to and action.cc; web.conf [settings] log.access_maxsize and log.access_maxfiles define the web-tier allocation; savedsearches.conf alert_condition with action.email.to as an alternative delivery path

*Assessment method.* Run `splunk btool web list settings --debug` for the web-tier log allocation, `splunk btool server list diskUsage --debug` for minFreeSpace on the volume holding those logs, and `splunk btool health list --debug` for the thresholds and recipients; confirm the warning threshold corresponds to 75 percent of the allocated capacity.

*Product reference.* SPLK-CL-000160 — confirmed in 10 4 2

**SRG-APP-000364-AU-000190** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured to perform audit reduction that supports on-demand audit review and analysis.

*Basis.* Splunk exposes summarization paths that write reduced record sets to a separate destination on a schedule without altering the original records, and report definitions that can be reviewed on demand over a selectable range. Audit reduction supporting on-demand review and analysis is therefore a product capability and the requirement applies to the application.

*Citation.* savedsearches.conf.spec:772 auto_summarize.command, :776 auto_summarize.timespan, :785 auto_summarize.cron_schedule, :797 auto_summarize.max_summary_size, :439 action.summary_index with :443 action.summary_index._name and :462 action.summary_index.inline; datamodels.conf.spec:29 acceleration with :100 acceleration.cron_schedule; metric_rollups.conf.spec:38 defaultAggregation, :91 aggregation.<metric_name>.

*Mechanism.* savedsearches.conf auto_summarize with auto_summarize.timespan and auto_summarize.cron_schedule, and action.summary_index with action.summary_index._name; datamodels.conf acceleration with acceleration.cron_schedule; metric_rollups.conf defaultAggregation and aggregation.<metric_name>

*Assessment method.* Run `splunk btool savedsearches list --debug` for the auto_summarize and action.summary_index settings and `splunk btool datamodels list --debug` for acceleration; run a reduced report on demand and confirm that the original records are unaltered.

**SRG-APP-000374-WSR-000172** — CAT II — Applicable, evidence grade C.

The web server must generate log records that can be mapped to Coordinated Universal Time (UTC) or Greenwich Mean Time (GMT).

*Basis.* Splunk Web is a component of Splunk Enterprise served by the same instance, not a separate web server baseline, so the web server requirement falls inside the application boundary. The access log is named in web.conf, the emitting process time zone comes from the environment set in splunk-launch.conf, and props.conf maps the record timestamp to UTC on ingestion.

*Citation.* web.conf.spec:16 [settings], :23 startwebserver, :926 log.access_file (default web_access.log); splunk-launch.conf.spec:35 (any desired environment variable can be set to any value); props.conf.spec:533 TIME_PREFIX, :558 TIME_FORMAT, :584 TZ, :596 TZ_ALIAS [10.4.2 spec set]. A 10.4.2 instance carries a [splunk_web_access] source type stanza in the product default props.conf with TIME_PREFIX set, confirmed through btool props list --debug, and the access record layout carries a bracketed timestamp with an explicit numeric UTC offset.

*Mechanism.* web.conf [settings] log.access_file; splunk-launch.conf process environment; props.conf [splunk_web_access] TIME_PREFIX, TIME_FORMAT, TZ, TZ_ALIAS

*Assessment method.* splunk btool web list --debug for log.access_file; read the first record of $SPLUNK_HOME/var/log/splunk/web_access.log and confirm the bracketed timestamp carries a numeric UTC offset; splunk btool props list --debug for the splunk_web_access stanza.

**SRG-APP-000375-WSR-000171** — CAT II — Applicable, evidence grade C.

The web server must record time stamps for log records to a minimum granularity of one second.

*Basis.* Splunk Web is a component of the application, so the requirement is inside the application boundary. Its access record layout is fixed by the product and carries a fractional-second field, and the precision retained on ingestion is set in props.conf.

*Citation.* web.conf.spec:926 log.access_file, :931 log.access_maxsize, :946 log.error_maxsize; props.conf.spec:558 TIME_FORMAT, :688 ADD_EXTRA_TIME_FIELDS [10.4.2 spec set]. Access records written by a 10.4.2 instance carry a millisecond fraction within the bracketed timestamp.

*Mechanism.* web.conf [settings] log.access_file; props.conf [splunk_web_access] TIME_FORMAT, ADD_EXTRA_TIME_FIELDS

*Assessment method.* Read the first record of $SPLUNK_HOME/var/log/splunk/web_access.log and confirm the timestamp resolves to one second or finer; splunk btool props list --debug for the splunk_web_access stanza.

**SRG-APP-000380-WSR-000072** — CAT II — Applicable, evidence grade C.

The web server application, libraries, and configuration files must only be accessible to privileged users.

*Basis.* This requirement's assessment objective, as written in its own check text, is whether the product provides distinct account roles that segment administration and whether a limited role is prevented from making configuration changes outside its scope. Splunk implements that through named capabilities bound to roles, per-endpoint capability requirements by HTTP method, and per-object metadata access control lists. The requirement is implementable and testable in the application. Filesystem ownership and mode on the installation tree, which the title also reaches, are provided by the host operating system baseline and are assessed there.

*Citation.* authorize.conf.spec:54 ([capability::<capability>]), :67 ([role_<roleName>]), :79 (importRoles), :447 ([capability::admin_all_objects]), :479 ([capability::change_authentication]), :570 ([capability::edit_httpauths]), :589 ([capability::edit_local_apps]), :760 ([capability::install_apps]); restmap.conf.spec:111-117; default.meta.spec (app, category and object access layers, 'access = read : [...], write : [...]'). Presence on a live Splunk 10.4.2 instance confirmed: btool authorize list --debug returns the capability and role stanzas.

*Mechanism.* authorize.conf [role_<roleName>] with importRoles, and [capability::<capability>] including admin_all_objects, edit_local_apps, install_apps, change_authentication, edit_httpauths; restmap.conf capability.<post|delete|get|put>; default.meta access = read/write

*Assessment method.* Run, as the Splunk service account: splunk btool authorize list --debug to enumerate roles and their capabilities. Then authenticate as a limited role such as an auditor or developer role and attempt a configuration change outside its capability set, confirming the attempt is refused.

**SRG-APP-000383-WSR-000175** — CAT II — Applicable, evidence grade C.

The web server must prohibit or restrict the use of nonsecure or unnecessary ports, protocols, modules, and/or services.

*Basis.* Splunk exposes a disable setting for each listener and protocol surface it offers, and separate settings that select the TLS versions, cipher suites and elliptic curves used on the management port, the receiving ports and the web interface, together with a setting that requires client certificate authentication. Nonsecure and unnecessary ports, protocols and modules are therefore restricted through the application's own configuration, and the requirement is assessed against the enabled set relative to the PPSM CAL.

*Citation.* web.conf.spec:23 (startwebserver), :28 (httpport), :70 (enableSplunkWebSSL); server.conf.spec:714 ([sslConfig]), :724 (enableSplunkdSSL), :765 (sslVersions), :858 (requireClientCert), :940 (cipherSuite), :955 (ecdhCurves); inputs.conf.spec:1227 ([udp://<remote server>:<port>]), :1314 ([udp:<port>]), :602 ([tcp:<port>]), :876 ([splunktcp-ssl:<port>]), :939 ([tcp-ssl:<port>]), :1486/:1632/:2010 (disabled); outputs.conf.spec:201 (disabled); server.conf.spec:5234 ([kvstore] disabled).

*Mechanism.* web.conf [settings] startwebserver, httpport, enableSplunkWebSSL; server.conf [sslConfig] enableSplunkdSSL, sslVersions, cipherSuite, ecdhCurves, requireClientCert; inputs.conf [udp:<port>], [tcp:<port>], [splunktcp-ssl:<port>] with disabled; outputs.conf disabled; server.conf [kvstore] disabled

*Assessment method.* Run, as the Splunk service account: splunk btool inputs list --debug; splunk btool outputs list --debug; splunk btool server list --debug; splunk btool web list settings --debug. Enumerate every enabled listener, its transport and its TLS settings, and reconcile each against the PPSM CAL and the documented mission need.

**SRG-APP-000391-AU-002290** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured to accept the DoW common access card (CAC) credential to support identity management and personal authentication.

*Basis.* Splunk Enterprise 10.4.2 accepts CAC and PIV credentials natively through client certificate authentication in the web tier, including extraction of the DoD EDIPI and of the PIV identifier from the presented certificate. The requirement applies to the Splunk application and is implemented through the product's own configuration.

*Citation.* web.conf.spec:120 enableCertBasedUserAuth; :133-143 certBasedUserAuthMethod declares CommonName, EDIPI and PIV extraction methods; :144 certBasedUserAuthPivOidList; :151 requireClientCert; :108 sslRootCAPath. Subsystem presence confirmed on a 10.4.2 instance: splunk btool web list --debug returns certBasedUserAuthPivOidList from shipped defaults.

*Mechanism.* web.conf [settings]: enableCertBasedUserAuth, requireClientCert, certBasedUserAuthMethod, certBasedUserAuthPivOidList, sslRootCAPath

*Assessment method.* splunk btool web list --debug - examine [settings] for enableCertBasedUserAuth, requireClientCert and certBasedUserAuthMethod; where an SSO proxy path is used instead, splunk btool authentication list --debug for authType and splunk btool web list --debug for SSOMode, trustedIP and remoteUser.

*Product reference.* SPLK-CL-000490 — confirmed in 10 4 2

**SRG-APP-000392-AU-002300** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured to electronically verify the DoW common access card (CAC) credential.

*Basis.* Electronic verification of a presented CAC credential decomposes into trust path validation, identity extraction and revocation status checking, and the product exposes a configuration key for each of the three. The requirement applies to the Splunk application.

*Citation.* web.conf.spec:151 requireClientCert and :108 sslRootCAPath supply path validation; :133 certBasedUserAuthMethod and :144 certBasedUserAuthPivOidList supply identity extraction; server.conf.spec:1125 certificateStatusValidationMethod = crl supplies status checking, and its scope statement at :1129-1131 covers the Splunk Web channel.

*Mechanism.* web.conf [settings]: requireClientCert, sslRootCAPath, certBasedUserAuthMethod, certBasedUserAuthPivOidList; server.conf [sslConfig]: certificateStatusValidationMethod

*Assessment method.* splunk btool web list --debug for requireClientCert, sslRootCAPath and certBasedUserAuthMethod; splunk btool server list --debug for [sslConfig] certificateStatusValidationMethod.

**SRG-APP-000416-WSR-000118** — CAT II — Applicable, evidence grade C.

The web server must implement required cryptographic protections using cryptographic modules complying with applicable federal laws, Executive Orders, directives, policies, regulations, standards, and guidance when encrypting data that must be compartmentalized.

*Basis.* DISA's published implementation for this requirement is to enable FIPS 140-2 mode before the instance first starts by adding settings to the launch file, and the setting it names still exists in 10.4.2 under the same name with the same one-time semantics. The product also exposes the cipher suite and protocol version settings that govern which cryptographic primitives the instance offers. Which data is compartmentalized is an organizational determination recorded outside the product; the cryptographic module used to protect it is a product setting, so the requirement applies.

*Citation.* splunk-launch.conf.spec:110-127 (SPLUNK_FIPS = [0|1], 'the algorithms and restrictions that apply to the FIPS Publication 140-2 standard'; one-time only; reinstall required to reverse) confirms SPLK-CL-000390's named setting in 10.4.2. The companion lines in the sunsetted fix text are not enumerated keys: SPLUNK_COMMON_CRITERIA appears only as a mode referenced from server.conf.spec:5398-5399, and splunk-launch.conf.spec:129-139 documents PYTHONHTTPSVERIFY and PYTHONUTF8 but not PYTHONDONTWRITEBYTECODE, although the file's generic form at splunk-launch.conf.spec:33 still accepts any environment variable. Supporting cipher and protocol settings: server.conf.spec:714 ([sslConfig]) with :1776 and :6277 (cipherSuite and sslVersions behavior under FIPS mode); web.conf.spec:246.

*Mechanism.* splunk-launch.conf SPLUNK_FIPS; server.conf [sslConfig] cipherSuite, sslVersions, sslRootCAPath; web.conf [settings] cipherSuite, sslVersions; indexes.conf [volume:<volume_name>] remote.*.encryption keys for compartmentalized data held on remote storage

*Assessment method.* Run `splunk show fips-mode` as the Splunk service account, which must report FIPS mode enabled; examine the launch file for SPLUNK_FIPS; run `splunk btool server list --debug` and `splunk btool web list --debug` for [sslConfig] cipherSuite and sslVersions; examine the organization's data classification policy to identify which data is compartmentalized.

*Product reference.* SPLK-CL-000390 — confirmed in 10 4 2

**SRG-APP-000427-AU-000040** — CAT II — Applicable, evidence grade C.

The Central Log Server must only allow the use of DoW Public Key Infrastructure (PKI)-established certificate authorities for verification of the establishment of protected sessions.

*Basis.* Every protected session this product establishes takes its trust anchor from a certificate authority file named in configuration: the inter-node management channel, the forwarder-to-indexer channel, the browser connection to Splunk Web, and the directory and identity provider connections each read a PEM certificate authority path from a named key, and each has a companion key that turns peer certificate verification on. Restricting verification to approved certificate authorities is therefore implementable inside the application boundary. The sunsetted product rule prescribes inspecting the certificate file with openssl and names no configuration key; the keys that carry the trust anchors in 10.4.2 are cited here.

*Citation.* server.conf.spec:714 ([sslConfig]) with :996 (sslRootCAPath = <path>), :1026 (caCertFile), :971 (serverCert), :798 (sslVerifyServerCert), :858 (requireClientCert), :5392-5412 (sslCRLPath, used in Common Criteria and FIPS modes). Web.conf.spec:108-118 (sslRootCAPath) and :82 (serverCert). Outputs.conf.spec:691 (sslRootCAPath) and :700 (sslVerifyServerCert). Inputs.conf.spec:1729 (serverCert), :1747 (caCertFile), :1801 (requireClientCert). Authentication.conf.spec:1552 and :1694 (sslRootCAPath for the directory and identity provider connections).

*Mechanism.* server.conf [sslConfig] sslRootCAPath, caCertFile, serverCert, sslVerifyServerCert, requireClientCert, sslCRLPath; web.conf [settings] sslRootCAPath, serverCert; outputs.conf [tcpout] sslRootCAPath, sslVerifyServerCert; inputs.conf [splunktcp-ssl] serverCert, caCertFile, requireClientCert; authentication.conf sslRootCAPath

*Assessment method.* Run `splunk btool server list --debug`, `splunk btool web list --debug`, `splunk btool outputs list --debug`, `splunk btool inputs list --debug` and `splunk btool authentication list --debug` as the Splunk service account to resolve every trust anchor path; then run `openssl x509 -text -inform PEM -in <path>` on each referenced file and confirm the issuer is an approved certificate authority.

*Product reference.* SPLK-CL-000450 — confirmed in 10 4 2

**SRG-APP-000427-WSR-000186** — CAT II — Applicable, evidence grade C.

The web server must only accept client certificates (user and machine) issued by DOD PKI or DOD-approved PKI Certificate Authorities (CAs).

*Basis.* The check text's Not Applicable condition is 'If the web server does not provide PKI-based user authentication intermediary services, this is not applicable.' That condition does not hold for Splunk Enterprise 10.4.2. The product carries certificate-based user authentication that derives a user identity from a presented client certificate, with a method setting whose documented values include EDIPI and PIV and a default object identifier list for locating the identifier in the Subject Alternative Name extension; it also validates presented client certificates against a configured root certificate authority and can check the common name and alternative names. Grade B is therefore unavailable, and the product rule DISA published against this requirement corroborates the applicable determination.

*Citation.* web.conf.spec:120-131 (enableCertBasedUserAuth = <boolean>, 'splunkd uses a digital certificate to identify and grant a user access'); :133-142 (certBasedUserAuthMethod: CommonName, EDIPI 'the 10-digit numeric identifier from the Common Name', PIV); :144-149 (certBasedUserAuthPivOidList, with a default object identifier list); :151-167 (requireClientCert, 'must present a certificate that was signed by the same certificate authority'); :108-118 (sslRootCAPath, 'to authenticate client certificates', used when requireClientCert and enableCertBasedUserAuth are both true); :169-185 (sslCommonNameToCheck, sslAltNameToCheck). Server.conf.spec:858 (requireClientCert) and :996 (sslRootCAPath).

*Mechanism.* web.conf [settings] requireClientCert, enableCertBasedUserAuth, certBasedUserAuthMethod, certBasedUserAuthPivOidList, sslRootCAPath, sslCommonNameToCheck, sslAltNameToCheck; server.conf [sslConfig] requireClientCert, sslRootCAPath, sslCRLPath

*Assessment method.* Run `splunk btool web list --debug` and `splunk btool server list --debug` as the Splunk service account to resolve requireClientCert, enableCertBasedUserAuth, certBasedUserAuthMethod and sslRootCAPath; run `openssl x509 -text -inform PEM -in <sslRootCAPath>` and confirm the issuer; then attempt a session with a client certificate issued by another authority and confirm it is refused.

*Product reference.* SPLK-CL-000450 — confirmed in 10 4 2

**SRG-APP-000435-WSR-000147** — CAT II — Applicable, evidence grade C.

The web server must be protected from being stopped by a non-privileged user.

*Basis.* Splunk Enterprise governs who may stop or restart the Splunk instance through role capabilities and not only through file permissions: a role that is not granted restart_splunkd cannot restart splunkd through Splunk Web or the REST server control handler, and the product names the Splunk Web pid file through configuration. The companion objective of restricting file access to the pid file and the start/stop utility is provided by the host operating system baseline, but an application-level mechanism exists, so the requirement is applicable to the application.

*Citation.* authorize.conf.spec:900 [capability::restart_splunkd] - "Lets a user restart the Splunk platform through the Splunk instance control handler"; authorize.conf.spec:665 [capability::edit_server]; web.conf.spec:1035 pid_path. Both capability stanzas were confirmed present on a live Splunk Enterprise 10.4.2 instance through "splunk btool authorize list --debug" (one match each).

*Mechanism.* authorize.conf, [capability::restart_splunkd] and [capability::edit_server], granted or withheld per role; web.conf, [settings], pid_path

*Assessment method.* splunk btool authorize list --debug (run as the Splunk service account) and enumerate every role granted restart_splunkd or edit_server; then examine the ownership and mode of the pid file named by web.conf pid_path and of the splunk start/stop binary under the host operating system assessment.

**SRG-APP-000435-WSR-000148** — CAT II — Applicable, evidence grade C.

The web server must be tuned to handle the operational requirements of the hosted application.

*Basis.* The product exposes connection, thread, timeout and search-admission limits on each of its HTTP listeners and on the search tier; these are the parameters through which a capacity analysis is implemented. The specification text states the purpose of the HTTP Event Collector limits directly: "Set this setting to constrain resource usage."

*Citation.* web.conf.spec:1098 maxThreads, 1106 maxSockets; server.conf.spec:1379 maxSockets, 1389 maxThreads, 1362 streamInWriteTimeout, 1407 busyKeepAliveIdleTimeout; inputs.conf.spec:1683 maxSockets, 1695 maxThreads; limits.conf.spec:445 base_max_searches, 457 max_searches_per_cpu; workload_pools.conf.spec provides pool-level CPU and memory admission control. All of these keys resolve in the merged configuration of a live 10.4.2 instance through btool.

*Mechanism.* web.conf [settings] maxThreads, maxSockets; server.conf [httpServer] maxThreads, maxSockets, streamInWriteTimeout, busyKeepAliveIdleTimeout; inputs.conf [http] maxThreads, maxSockets; limits.conf [search] base_max_searches, max_searches_per_cpu; workload_pools.conf pool definitions

*Assessment method.* splunk btool web list --debug; splunk btool server list --debug; splunk btool inputs list --debug; splunk btool limits list --debug - then examine the thread, socket and search-concurrency limits against the documented capacity and risk analysis for the hosted workload.

**SRG-APP-000439-WSR-000152** — CAT II — Applicable, evidence grade C.

Web server session IDs must be sent to the client using SSL/TLS.

*Basis.* The session identifier Splunk Web issues is carried in a session cookie, and the product exposes settings that require the browser to transmit that cookie only over HTTPS, including a setting for the case where TLS terminates on an upstream proxy. The REST server issues its own authentication cookie and exposes equivalent settings.

*Citation.* web.conf.spec:951 tools.sessions.secure ("the browser must transmit the session cookie over HTTPS connections"), 962 tools.sessions.forceSecure (sets the secure bit when a proxy terminates HTTPS and the back end connects over HTTP), 70 enableSplunkWebSSL; server.conf.spec:1520 allowCookieAuth, 1525 cookieAuthHttpOnly. All resolve in the merged configuration of a live 10.4.2 instance through btool.

*Mechanism.* web.conf [settings] enableSplunkWebSSL, tools.sessions.secure, tools.sessions.forceSecure; server.conf [httpServer] allowCookieAuth

*Assessment method.* splunk btool web list --debug to examine enableSplunkWebSSL, tools.sessions.secure and tools.sessions.forceSecure; then authenticate to the interface and confirm the Set-Cookie response header for the session cookie carries the Secure attribute and that the exchange occurred over TLS.

*Product reference.* SPLK-CL-000460 — confirmed in 10 4 2

**SRG-APP-000439-WSR-000153** — CAT II — Applicable, evidence grade C.

Web server cookies, such as session cookies, sent to the client using SSL/TLS must not be compressed.

*Basis.* The product exposes a setting that governs whether the Splunk instance lets a client negotiate TLS-layer data compression, which is the compression path the CRIME attack described in the requirement relies on, together with a separate setting for HTTP-layer response compression. The embedded clause "If the transmission is through a SSL/TLS connection, but the cookie is not being compressed, this finding is NA" is conditioned on two configurable states, TLS in use and compression not negotiated, so it is a per-instance condition and not a property of the product; grade B is therefore not available and the requirement is applicable.

*Citation.* web.conf.spec:1176 allowSslCompression ("Whether or not the Splunk instance lets clients negotiate SSL-layer data compression"); server.conf.spec:1070 allowSslCompression; web.conf.spec:346 enable_gzip; outputs.conf.spec:764 useClientSSLCompression for the Splunk-to-Splunk channel. The inventory records has_own_na_clause as false for this requirement, but its check text does carry the NA condition quoted above; the condition was read and found to be instance-dependent.

*Mechanism.* web.conf [settings] allowSslCompression and enable_gzip; server.conf [sslConfig] allowSslCompression; outputs.conf [tcpout:<group>] useClientSSLCompression

*Assessment method.* splunk btool web list --debug and splunk btool server list --debug to examine allowSslCompression on each TLS listener; then confirm with a TLS client that the Splunk instance does not select a compression method in the handshake.

*Product reference.* SPLK-CL-000460 — confirmed in 10 4 2

**SRG-APP-000439-WSR-000154** — CAT II — Applicable, evidence grade C.

Cookies exchanged between the web server and the client, such as session cookies, must have cookie properties set to prohibit client-side scripts from reading the cookie data.

*Basis.* The product exposes a setting that marks the Splunk Web session cookie so it is not readable by scripts running in the browser, and a separate setting that applies the same flag to the cookie the REST server issues for cookie-based authentication. Both are application configuration keys, so the requirement is implemented inside the application boundary.

*Citation.* web.conf.spec:943 tools.sessions.httponly ("Whether or not the session cookie is available to running JavaScript scripts"); server.conf.spec:1525 cookieAuthHttpOnly ("mark returned cookies with the \"httponly\" flag to tell the client not to allow javascript code to access its value"). Both resolve in the merged configuration of a live 10.4.2 instance through btool.

*Mechanism.* web.conf [settings] tools.sessions.httponly; server.conf [httpServer] cookieAuthHttpOnly

*Assessment method.* splunk btool web list --debug and splunk btool server list --debug to examine tools.sessions.httponly and cookieAuthHttpOnly; then authenticate and confirm each Set-Cookie response header carries the HttpOnly attribute.

*Product reference.* SPLK-CL-000460 — confirmed in 10 4 2

**SRG-APP-000439-WSR-000155** — CAT II — Applicable, evidence grade C.

Cookies exchanged between the web server and the client, such as session cookies, must have cookie properties set to force the encryption of cookies.

*Basis.* The product exposes the cookie Secure attribute that this requirement describes as the means of forcing cookie encryption, both for the ordinary case and for the case where TLS terminates upstream of the application, along with the SameSite attribute that interacts with it. These are application configuration keys.

*Citation.* web.conf.spec:951 tools.sessions.secure, 962 tools.sessions.forceSecure ("setting this to \"true\" forces the session cookie being sent back to the client over HTTPS to have the secure bit set"), 664 cookieSameSite, whose text records that the Splunk instance adds the Secure attribute for HTTPS connections and points to tools.sessions.secure to configure that behavior. All resolve in the merged configuration of a live 10.4.2 instance through btool.

*Mechanism.* web.conf [settings] tools.sessions.secure, tools.sessions.forceSecure, cookieSameSite

*Assessment method.* splunk btool web list --debug to examine tools.sessions.secure, tools.sessions.forceSecure and cookieSameSite; then authenticate and confirm each Set-Cookie response header carries the Secure attribute.

*Product reference.* SPLK-CL-000460 — confirmed in 10 4 2

**SRG-APP-000439-WSR-000156** — CAT II — Applicable, evidence grade C.

A web server must maintain the confidentiality of controlled information during transmission through the use of an approved TLS version.

*Basis.* The product exposes per-listener and per-client protocol version selection, with exclusion syntax for individual versions, on every TLS channel it operates, so the approved-version objective is met through application configuration. An assessor should note that the version vocabulary documented in 10.4.2 is "ssl3", "tls1.0", "tls1.1" and "tls1.2": the token tls1.3 appears nowhere in the specification set, so this setting cannot name TLS 1.3, which bears on the NIST SP 800-52 Rev 2 expectation that a server support TLS 1.3.

*Citation.* web.conf.spec:239 sslVersions ("The versions available are \"ssl3\", \"tls1.0\", \"tls1.1\", and \"tls1.2\""); server.conf.spec:765 sslVersions and 780 sslVersionsForClient; inputs.conf.spec:1035 sslVersions and 1760 sslVersions; outputs.conf.spec:779 sslVersions; alert_actions.conf.spec:428 sslVersions. A case-insensitive search of all 71 specification files for "tls1.3", "tls1_3" and "TLSv1.3" returned zero matches.

*Mechanism.* web.conf [settings] sslVersions; server.conf [sslConfig] sslVersions and sslVersionsForClient; inputs.conf [SSL] and [http] sslVersions; outputs.conf [tcpout:<group>] sslVersions; alert_actions.conf sslVersions

*Assessment method.* splunk btool web list --debug, splunk btool server list --debug, splunk btool inputs list --debug and splunk btool outputs list --debug to examine sslVersions on every TLS channel; then test each port with "openssl s_client -connect <host>:<port> -tls1" and "-tls1_1" and confirm both are refused, and with "-tls1_2" and "-tls1_3" to record which approved versions the listener negotiates.

*Product reference.* SPLK-CL-000460 — confirmed in 10 4 2

**SRG-APP-000439-WSR-000188** — CAT II — Applicable, evidence grade C.

The web server must remove all export ciphers to protect the confidentiality and integrity of transmitted information.

*Basis.* The product accepts an OpenSSL cipher string on each TLS listener and client, which is the mechanism by which export and other weak suites are excluded, together with named-curve and Diffie-Hellman parameter settings that bound the key exchange. Enabling FIPS mode narrows the algorithm set further.

*Citation.* server.conf.spec:940 cipherSuite ("A list of cipher suites for splunkd to use"), 955 ecdhCurves, 1036 dhFile; web.conf.spec:255 cipherSuite ("used to confirm that the Splunk instance does not accept connections using weak encryption protocols"), 276 ecdhCurves, 290 dhFile; inputs.conf.spec:1052 and 1773 cipherSuite; outputs.conf.spec:664 cipherSuite; splunk-launch.conf.spec:110 SPLUNK_FIPS.

*Mechanism.* server.conf [sslConfig] cipherSuite, ecdhCurves, dhFile; web.conf [settings] cipherSuite, ecdhCurves, dhFile; inputs.conf [SSL] and [http] cipherSuite; outputs.conf [tcpout:<group>] cipherSuite

*Assessment method.* splunk btool server list --debug, splunk btool web list --debug, splunk btool inputs list --debug and splunk btool outputs list --debug to examine cipherSuite on every TLS channel; then enumerate the suites each port actually offers with a TLS scanner and confirm no EXPORT, NULL, anonymous or 40/56-bit suite is accepted.

*Product reference.* SPLK-CL-000460 — confirmed in 10 4 2

**SRG-APP-000439-WSR-000192** — CAT II — Applicable, evidence grade C.

The web server must use HTTP/2, at a minimum.

*Basis.* The determination of Not Applicable is withdrawn: the requirement carries no Not Applicable clause and its check text reads "If the web server does not use HTTP/2 at a minimum, this is a finding", so absence of the mandated capability is the finding the benchmark anticipates rather than an exemption from it, and a requirement the product cannot meet is assessed Other Than Satisfied and carried as a POA&M item for the system owner. The original basis itself names a TLS-terminating front end as the implementer, which is grade D reasoning supporting at most OUTSIDE_BOUNDARY and never NOT_APPLICABLE; and because the requirement's discussion extends the objective to back-end servers and to communications between web servers, which the product performs through its HEC HTTP server and its HTTP output, a client-facing front end cannot discharge the whole objective in any case. Grade A was also claimed from a configuration search alone, which cannot establish absence of HTTP/2 because ALPN negotiation requires no configuration key; a negotiation test was needed and was available.

*Citation.* A case-insensitive search of all 71 specification files for "http2", "http/2", "alpn", "h2c", "nghttp", "protocolVersion" and "http_version" returned zero line hits, confirming the original search as to the configuration surface only. A negotiation test offering "h2,http/1.1" by ALPN, and requesting --http2, against the Splunk Web listener and the splunkd management listener of a 10.4.2 instance selected HTTP/1.1 in both cases; that instance's HEC listener was not accepting connections and was not tested, so the third HTTP server is unconfirmed. Server-to-server HTTP is documented at inputs.conf.spec:1729 [http] and outputs.conf.spec:884 [httpout]. The original citation web.conf.spec:1130 is the first bullet of the setting; the key is at web.conf.spec:1129.

*Mechanism.* web.conf [settings] forceHttp10 (web.conf.spec:1129), server.conf [httpServer] forceHttp10 (server.conf.spec:1416) and inputs.conf [http] forceHttp10 (inputs.conf.spec:1872) are the protocol-version settings of the product's three HTTP servers and are the examination target; web.conf [settings] tools.proxy.on and tools.proxy.base (web.conf.spec:1016, 1031) configure the application's participation behind an HTTP/2-capable reverse proxy. No key in the specification set selects HTTP/2.

*Assessment method.* splunk btool web list settings --debug | grep -c forceHttp10 ; then for each of the three HTTP servers: openssl s_client -alpn h2,http/1.1 -connect <host>:<port> and curl -k --http2 -o /dev/null -w '%{http_version}\n' https://<host>:<port>/ , recording the protocol selected; then examine web.conf [settings] tools.proxy.on and tools.proxy.base, and where a front end is present obtain its HTTP/2 configuration from that front end's own baseline.

*Product reference.* SPLK-CL-000460 — confirmed in 10 4 2

**SRG-APP-000439-WSR-000193** — CAT II — Applicable, evidence grade C.

The web server must disable HTTP/1.x downgrading.

*Basis.* The determination of Not Applicable is withdrawn because the product does operate a request-forwarding front end with a configuration key that disables it: web.conf registers exposed splunkd REST endpoints and controls, per endpoint, whether splunkd forwards a request it has received to a remote node through the "remote-proxy" endpoint, with a companion setting governing how the forwarded request's arguments are re-encoded, while a search head cluster replays received REST methods to other members and proxies received requests to the captain. The objective — that a front end not hand a back end a request it has rewritten into a less strictly validated form — therefore has a referent inside the application boundary and an examination target. The benchmark provides no Not Applicable clause here but a severity modifier ("If HTTP downgrading is operationally necessary, and the rewritten request is validated against HTTP/1.x specification ..., mark as a CAT III finding"), which presupposes the requirement attaches; and the grade A premise that no listener accepts HTTP/2 was drawn from a configuration search, which cannot establish ALPN behavior.

*Citation.* web.conf.spec:1545-1553 allowRemoteProxy — "Determines whether or not splunkd lets the exposed REST endpoint be proxied to remote nodes using the 'remote-proxy' REST endpoint"; web.conf.spec:1556-1565 documents double-encoding of the forwarded request's GET arguments. Restmap.conf.spec:465-476 [restreplayshc] — "methods = ... REST methods that are replayed", with "shc" replaying to all other nodes in a search head cluster. Server.conf.spec:4847-4874 documents sid_proxying, ss_proxying, ra_proxying and alert_proxying under [shclustering]. AllowRemoteProxy resolves in the merged web.conf of a live 10.4.2 instance. The HTTP/2 term search returned zero line hits across all 71 specification files, and a negotiation test offering h2 by ALPN to the Splunk Web and splunkd management listeners of a 10.4.2 instance selected HTTP/1.1, but that instance's HEC listener was not reachable, so capability absence is not established for all three HTTP servers.

*Mechanism.* web.conf [expose:<unique_name>] allowRemoteProxy (web.conf.spec:1545) and remoteProxyLegacyRequireDoubleEncodedUriArgs (web.conf.spec:1556); restmap.conf [restreplayshc] methods and nodelists (restmap.conf.spec:466, 470); server.conf [shclustering] sid_proxying, ss_proxying, ra_proxying and alert_proxying (server.conf.spec:4848, 4855, 4862, 4869).

*Assessment method.* splunk btool web list --debug | grep -c allowRemoteProxy ; splunk btool restmap list restreplayshc --debug ; splunk btool server list shclustering --debug | grep -cE 'sid_proxying|ss_proxying|ra_proxying|alert_proxying' ; then offer h2 by ALPN and by h2c upgrade to each of the three HTTP servers and record the protocol selected.

*Product reference.* SPLK-CL-000460 — confirmed in 10 4 2

**SRG-APP-000439-WSR-000196** — CAT II — Applicable, evidence grade C.

The web server must only use forward proxies that route HTTP/2 requests upstream.

*Basis.* The rejection of grade B is sound and is retained — whether a forward proxy is used is a configurable state of an instance, so the clause "If a forward proxy is not used, this is not applicable" cannot be invoked at the product level — but the disposition does not follow from it. The benchmark's fix text directs "Configure the web server to only use forward proxies that route HTTP/2 requests upstream", which is an act of configuration performed on the application: the product names its forward proxy and scopes which destinations are routed through it in its own configuration file, and the original evidence cites exactly those keys, which is grade C mechanism evidence recorded against a disposition stating the application owes nothing. The upstream protocol remains a property of the proxy and must be obtained from that proxy's own baseline; that dependency belongs in the basis, not in the disposition.

*Citation.* server.conf.spec:1201 [proxyConfig]; server.conf.spec:1206 http_proxy — "If set, splunkd sends all HTTP requests through the proxy server that you specify"; proxy_rules (1217) and no_proxy (1241) scope which destinations are routed. Server.conf.spec:1268-1284 enable_tls_proxy was omitted from the original evidence although it sits within the stanza cited: it launches a helper process that proxies outbound connections over TLS, so the assertion that the application contributes no upstream protocol selection is incomplete. The original citations for this stanza do not resolve as given — the quoted CONNECT-method note is at server.conf.spec:1202-1204, not 1197-1199, and http_proxy, https_proxy, proxy_rules and no_proxy are at 1206, 1211, 1217 and 1241, not 1207, 1213, 1219 and 1242. The [proxyConfig] stanza resolves in the merged server.conf of a live 10.4.2 instance.

*Mechanism.* server.conf [proxyConfig] http_proxy (server.conf.spec:1206), https_proxy (1211), proxy_rules (1217), no_proxy (1241) and enable_tls_proxy (1268).

*Providing baseline.* The forward (egress) HTTP proxy server or appliance, assessed under its own product STIG or the applicable Web Server SRG; the Splunk application selects only whether to use it, through server.conf [proxyConfig].

*Assessment method.* splunk btool server list proxyConfig --debug to determine whether http_proxy, https_proxy or proxy_rules name a forward proxy and whether enable_tls_proxy is set; where a proxy is named, obtain its upstream HTTP/2 configuration from that proxy's own product STIG or the applicable Web Server SRG assessment.

*Product reference.* SPLK-CL-000460 — confirmed in 10 4 2

**SRG-APP-000441-WSR-000181** — CAT II — Applicable, evidence grade C.

The web server must maintain the confidentiality and integrity of information during preparation for transmission.

*Basis.* The product stages data for transmission in forwarder output queues and optional on-disk persistent queues, and exposes the TLS settings, peer verification and indexer acknowledgment that protect that data in transit and confirm its delivery; it also exposes TLS settings for the mail queue that the requirement's discussion names as its example. At-rest protection of the persistent queue file itself is provided by the host operating system baseline, but application settings exist, so the requirement is applicable.

*Citation.* outputs.conf.spec:349 maxQueueSize, 165 persistentQueueSize, 832 useACK, 647 sslPassword, 652 clientCert, 700 sslVerifyServerCert, 741 sslCommonNameToCheck, 779 sslVersions; alert_actions.conf.spec:287 use_ssl, 293 use_tls, 428 sslVersions, 441 sslVerifyServerCert; inputs.conf.spec:554 persistentQueueSize. UseACK and maxQueueSize resolve in the merged outputs.conf of a live 10.4.2 instance.

*Mechanism.* outputs.conf [tcpout:<group>] clientCert, sslPassword, sslVersions, sslVerifyServerCert, sslCommonNameToCheck, useACK, maxQueueSize, persistentQueueSize; alert_actions.conf [email] use_ssl, use_tls, sslVersions, sslVerifyServerCert

*Assessment method.* splunk btool outputs list --debug and splunk btool alert_actions list --debug to examine the TLS, peer-verification and acknowledgment settings on every configured output and on the mail action; then examine the ownership and mode of any persistent queue directory under the host operating system assessment.

**SRG-APP-000442-WSR-000182** — CAT II — Applicable, evidence grade C.

The web server must maintain the confidentiality and integrity of information during reception.

*Basis.* Every channel on which the product receives data is a configurable TLS listener: the Splunk-to-Splunk receiver, the raw TCP receiver, the HTTP Event Collector, the management port and the browser interface each expose a server certificate, protocol version and cipher selection, and optional client certificate authentication. The requirement is therefore implemented through the application's own configuration.

*Citation.* inputs.conf.spec:876 [splunktcp-ssl:<port>], 939 [tcp-ssl:<port>], 986 [SSL] with serverCert (990), sslPassword (1002), requireClientCert (1015), sslVersions (1035), cipherSuite (1052); inputs.conf.spec:1627 [http] with enableSSL (1665), serverCert (1729), requireClientCert (1801); server.conf.spec:724 enableSplunkdSSL, 858 requireClientCert; web.conf.spec:70 enableSplunkWebSSL, 151 requireClientCert. EnableSSL, serverCert and requireClientCert resolve in the merged inputs.conf of a live 10.4.2 instance.

*Mechanism.* inputs.conf [splunktcp-ssl:<port>], [tcp-ssl:<port>] and [SSL] serverCert, requireClientCert, sslVersions, cipherSuite; inputs.conf [http] enableSSL, requireClientCert; server.conf [sslConfig] enableSplunkdSSL, requireClientCert; web.conf [settings] enableSplunkWebSSL, requireClientCert

*Assessment method.* splunk btool inputs list --debug, splunk btool server list --debug and splunk btool web list --debug to enumerate every receiving stanza and confirm each has TLS enabled and that no plaintext equivalent is defined; then test each receiving port with "openssl s_client -connect <host>:<port>" and confirm a plaintext connection to the same port is refused.

**SRG-APP-000503-AU-000280** — CAT II — Applicable, evidence grade C.

The Central Log Server must generate audit records when successful/unsuccessful logon attempts occur.

*Basis.* Splunk writes its own authentication events to an audit trail whose routing and format are set in audit.conf, and 10.4.2 adds per-REST-path control over which actions are logged while naming the authentication categories as protected actions that the product does not allow to be sampled. The requirement applies to the application.

*Citation.* audit.conf.spec:28 [auditTrail], :29 queueing, :36 logging_format = v1|v2|both, :47 [auditconfig:/path], :48 enabled, :57 disabled, :64 sampling.<action>, :70 (the system ignores sampling for protected actions - delete and the authentication categories); inputs.conf.spec:1526 signedaudit, :1523 (_audit index), :1531 (audittrail source type) [10.4.2 spec set]. Audit.conf is readable through btool audit list --debug on a 10.4.2 instance, which returns [auditTrail] and several [auditconfig:...] stanzas.

*Mechanism.* audit.conf [auditTrail] queueing, logging_format; audit.conf [auditconfig:/path] enabled, disabled, sampling.<action>; inputs.conf [monitor://...] signedaudit, index

*Assessment method.* splunk btool audit list --debug and examine [auditTrail] plus every [auditconfig:...] stanza for disabled or sampling values that would reach authentication actions; then confirm both a successful and a failed logon produce a record in the audit trail.

**SRG-APP-000516-AU-000330** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured to retain the identity of the original source host or device where the event occurred as part of the log record.

*Basis.* Splunk assigns a host field to every record it indexes, and each receiving stanza carries a setting that derives that field from the sending connection's address or its resolved name. Separate transform and property settings override or extract the host value from the record itself where the originating device is further upstream. Retention of the original source identity is therefore implementable through the application's own configuration. The requirement's discussion also calls for the source to be bound to the record by cryptographic means; the product's nearest mechanism computes hashes over indexed rawdata slices at the bucket level rather than binding a host value to an individual record, and an assessment should record that distinction.

*Citation.* inputs.conf.spec:526, :611, :779, :845, :889, :1244, :1320 ('connection_host = [ip|dns|none]'), :2083 ('connection_host = [ip|dns|proxied_ip|none]'), :60 (host), :244 (host_regex), :256 (host_segment); transforms.conf.spec:241 (DEST_KEY), :930 ('MetaData:Host : The host associated with the event'), :256 ('DEST_KEY = MetaData:Host'); props.conf.spec:1043 (TRANSFORMS-<class>), :90 and :105 ([host::<host>] stanza form); indexes.conf.spec:594 (enableDataIntegrityControl). Presence on a live Splunk 10.4.2 instance confirmed: btool inputs list --debug returns connection_host.

*Mechanism.* inputs.conf connection_host = [ip|dns|none] (and [ip|dns|proxied_ip|none] on the HTTP Event Collector) with host, host_regex and host_segment; transforms.conf DEST_KEY = MetaData:Host with SOURCE_KEY and REGEX; props.conf TRANSFORMS-<class> and [host::<host>] stanzas; indexes.conf enableDataIntegrityControl

*Assessment method.* Run, as the Splunk service account: splunk btool inputs list --debug; splunk btool props list --debug; splunk btool transforms list --debug; splunk btool indexes list --debug. Then search a sample of aggregated records from each in-scope device class and confirm a host value traceable to the originating device is present on each record.

*Product reference.* SPLK-CL-000260, SPLK-CL-000270, SPLK-CL-000280, SPLK-CL-000290 — confirmed in 10 4 2

**SRG-APP-000516-AU-000340** — CAT II — Applicable, evidence grade C.

The Central Log Server that aggregates log records from hosts and devices must be configured to use TCP for transmission.

*Basis.* The product offers both TCP and UDP receiving stanzas, so the transport used to aggregate records from hosts and devices is selected by configuration. The UDP receiving stanzas remain present in the 10.4.2 specification set, which is what makes this requirement assessable rather than moot: an instance can be built either way, and the determination of which transport is in use belongs to the assessment.

*Citation.* inputs.conf.spec:626 ([splunktcp]), :770 ([splunktcp://[<remote server>]:<port>]), :839 ([splunktcp:<port>]), :876 ([splunktcp-ssl:<port>]), :602 ([tcp:<port>]), :939 ([tcp-ssl:<port>]), :1227 ([udp://<remote server>:<port>]), :1314 ([udp:<port>]); outputs.conf.spec:201 (disabled). The sunsetted product STIG rule SPLK-CL-000270 names the inputs.conf UDP surface, and that surface is present in the 10.4.2 specification set.

*Mechanism.* inputs.conf [splunktcp], [splunktcp://[<remote server>]:<port>], [splunktcp:<port>], [splunktcp-ssl:<port>], [tcp:<port>], [tcp-ssl:<port>] in place of [udp:<port>] and [udp://<remote server>:<port>]; outputs.conf [tcpout:<target_group>]

*Assessment method.* Run, as the Splunk service account: splunk btool inputs list --debug. Enumerate every input stanza and confirm no UDP receiving stanza is enabled; corroborate by enumerating the instance's listening UDP sockets.

*Product reference.* SPLK-CL-000260, SPLK-CL-000270, SPLK-CL-000280, SPLK-CL-000290 — confirmed in 10 4 2

**SRG-APP-000516-AU-000350** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured to notify the System Administrator (SA) and Information System Security Officer (ISSO), at a minimum, when an attack is detected on multiple devices and hosts within its scope of coverage.

*Basis.* The requirement carries its own Not Applicable clause: 'Note: This is not applicable (NA) if the Central Log Server (e.g., syslog, SIEM) does not perform analysis. This is NA if notifications are performed by another device.' Neither condition holds as a property of the product. Splunk Enterprise performs analysis - scheduled correlation searches with alert conditions are a native function documented in the configuration surface - so the first condition is false. Whether notification is delegated to another device is a site design fact rather than a property of Splunk Enterprise, and there is no site in an applicability determination, so the second condition cannot carry it. The product exposes scheduled alerting with an email action addressed to named recipients, which is the mechanism.

*Citation.* savedsearches.conf.spec:73 (enableSched), :79 (cron_schedule), :249 (counttype), :270 (alert_condition), :300 (action.email), :304 (action.email.to), :318 (action.email.subject), :887 (alert.severity); alert_actions.conf.spec:157 ([email]). Presence on a live Splunk 10.4.2 instance confirmed by btool reads of savedsearches and alert_actions. The sunsetted rule SPLK-CL-000280 names the Reporting and Alert tools, and that function is present in 10.4.2.

*Mechanism.* savedsearches.conf enableSched, cron_schedule, counttype, alert_condition, action.email with action.email.to, action.email.subject and alert.severity; alert_actions.conf [email]

*Assessment method.* Run, as the Splunk service account: splunk btool savedsearches list --debug; splunk btool alert_actions list --debug. Identify scheduled searches whose alert condition covers an attack observed across multiple hosts within the scope of coverage, confirm the email action names the SA and ISSO recipients, and interview the ISSO to confirm receipt.

*Product reference.* SPLK-CL-000260, SPLK-CL-000270, SPLK-CL-000280, SPLK-CL-000290 — confirmed in 10 4 2

**SRG-APP-000516-AU-000360** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured to automatically create trouble tickets for organization-defined threats and events of interest as they are detected in real time (within seconds).

*Basis.* The requirement carries its own Not Applicable clause: 'Note: This is not applicable (NA) if the Central Log Server (e.g., syslog) does not perform analysis.' Splunk Enterprise performs analysis through scheduled correlation searches, so that condition is false and the clause cannot be used. The product exposes a generic alert action framework in which a triggered search dispatches to a webhook or to a custom alert action, by which a trouble ticket is raised in an external ticketing system. The ticketing system itself is a separate baseline, but the detection, triggering and dispatch mechanism is in the application and is what this requirement is assessed against.

*Citation.* savedsearches.conf.spec:283 ('action.<action_name> = <boolean>'), :290 ('action.<action_name>.<parameter> = <value>'), :403-407 (action.script, action.script.filename), :270 (alert_condition), :79 (cron_schedule); alert_actions.conf.spec:599-600 ([webhook], param.user_agent), :623 ([<custom_alert_action>]), :87 (command), :96 (is_custom), :100 (payload_format). Presence on a live Splunk 10.4.2 instance confirmed: btool alert_actions list --debug returns the webhook action.

*Mechanism.* savedsearches.conf action.<action_name> and action.<action_name>.<parameter>, action.script with action.script.filename; alert_actions.conf [webhook] and [<custom_alert_action>] with command, is_custom and payload_format

*Assessment method.* Run, as the Splunk service account: splunk btool savedsearches list --debug; splunk btool alert_actions list --debug. Identify the alert actions bound to the organization-defined threats and events of interest, confirm each dispatches to the ticketing system, and confirm the triggering searches run on a real-time or near-real-time schedule.

*Product reference.* SPLK-CL-000260, SPLK-CL-000270, SPLK-CL-000280, SPLK-CL-000290 — confirmed in 10 4 2

**SRG-APP-000516-AU-000370** — CAT II — Applicable, evidence grade C.

For devices and hosts within the scope of coverage, the Central Log Server must be configured to automatically aggregate events that indicate account actions.

*Basis.* Splunk indexes received records by default and discards them only where a property and transform pair routes them to the null queue. This requirement asks that records of account actions not be filtered out, so it is assessed against the routing transforms present on the instance and the index routing of the inputs that carry account events. Both are settings in the application, so the requirement is implementable and assessable there.

*Citation.* transforms.conf.spec:921-926 ('queue : Specify which queue to send the event to (can be nullQueue, indexQueue)'; 'nullQueue is a destination which causes the events to be dropped entirely'), :241 (DEST_KEY), :115 (FORMAT), :80 (REGEX); props.conf.spec:1043 (TRANSFORMS-<class>); inputs.conf.spec:128 and :146 (queue = [parsingQueue|indexQueue]). Presence on a live Splunk 10.4.2 instance confirmed by btool reads of props and transforms.

*Mechanism.* props.conf TRANSFORMS-<class> paired with transforms.conf DEST_KEY = queue and FORMAT = nullQueue; inputs.conf index and queue; indexes.conf per-index stanzas; eventtypes.conf

*Assessment method.* Run, as the Splunk service account: splunk btool props list --debug; splunk btool transforms list --debug. Enumerate every transform whose FORMAT routes to nullQueue and confirm none matches account creation, modification, deletion, enable, disable or privilege change records. Then search for account-action records originating from each device and host within the scope of coverage.

*Product reference.* SPLK-CL-000260, SPLK-CL-000270, SPLK-CL-000280, SPLK-CL-000290 — confirmed in 10 4 2

**SRG-APP-000516-AU-000380** — CAT II — Applicable, evidence grade C.

The Central Log Server must be configured with the organization-defined severity or criticality levels of each event that is being sent from individual devices or hosts.

*Basis.* Splunk carries a severity setting on each scheduled alert and exposes field calculation, field alias and lookup settings by which a sending device's native severity value is normalized onto the organization's levels, either at index time or at search time. Event types paired with tags classify records into the categories against which those levels are assigned. The requirement is therefore implementable through the application's own configuration; the levels themselves are defined in the system security plan and are an input to the assessment rather than a product property.

*Citation.* savedsearches.conf.spec:887 ('alert.severity = <integer>'), :850-865 (alert.suppress and its fields); props.conf.spec:1313 (EVAL-<fieldname>), :1265 (FIELDALIAS-<class>), :1043 (TRANSFORMS-<class>); transforms.conf.spec:80 (REGEX), :115 (FORMAT); eventtypes.conf.spec and tags.conf.spec are both present in the shipped specification set. Presence on a live Splunk 10.4.2 instance confirmed by btool reads of savedsearches and props.

*Mechanism.* savedsearches.conf alert.severity; props.conf EVAL-<fieldname>, FIELDALIAS-<class> and TRANSFORMS-<class>; transforms.conf lookup and extraction stanzas; eventtypes.conf paired with tags.conf

*Assessment method.* Obtain the system security plan's criticality levels for each system within the scope of coverage. Run, as the Splunk service account: splunk btool savedsearches list --debug; splunk btool props list --debug; splunk btool eventtypes list --debug; splunk btool tags list --debug. Confirm each documented level is represented in the alert severities and in the normalized severity field, and that each device class maps to a level.

*Product reference.* SPLK-CL-000260, SPLK-CL-000270, SPLK-CL-000280, SPLK-CL-000290 — confirmed in 10 4 2

**SRG-APP-000516-AU-000410** — CAT II — Applicable, evidence grade C.

Analysis, viewing, and indexing functions, services, and applications used as part of the Central Log Server must be configured to comply with DoW-trusted path and access requirements.

*Basis.* The analysis, viewing and indexing functions of this product are Splunk Web, the search tier and the indexing tier, and each carries its own transport protection and access control settings in the application: TLS with a server certificate and private key on the web interface, TLS with optional client certificate authentication and an explicit cipher suite on the management and receiving ports, capability-based access control on the search and administrative interfaces, and configured distributed search between tiers. Trusted path and access requirements are therefore implementable through the application's own configuration.

*Citation.* web.conf.spec:70 (enableSplunkWebSSL), :75 (privKeyPath), :82 (serverCert), :93 (sslPassword); server.conf.spec:724 (enableSplunkdSSL), :858 (requireClientCert), :940 (cipherSuite), :765 (sslVersions), :996 (sslRootCAPath); inputs.conf.spec:986-1015 ([SSL] with serverCert at :990, sslPassword at :1002, requireClientCert at :1015), :876 ([splunktcp-ssl:<port>]); authorize.conf.spec:54 and :67; distsearch.conf.spec:29 ([distributedSearch]). Presence on a live Splunk 10.4.2 instance confirmed by btool reads of web, server, inputs, authorize and distsearch.

*Mechanism.* web.conf [settings] enableSplunkWebSSL, privKeyPath, serverCert; server.conf [sslConfig] enableSplunkdSSL, requireClientCert, cipherSuite, sslVersions, sslRootCAPath; inputs.conf [SSL] serverCert, sslPassword, requireClientCert; authorize.conf [role_<roleName>] and [capability::<capability>]; distsearch.conf [distributedSearch]

*Assessment method.* Run, as the Splunk service account: splunk btool web list settings --debug; splunk btool server list sslConfig --debug; splunk btool inputs list --debug; splunk btool authorize list --debug; splunk btool distsearch list --debug. Confirm TLS is in force on the web, management and receiving interfaces and that access to the analysis and viewing functions is capability-gated.

*Product reference.* SPLK-CL-000260, SPLK-CL-000270, SPLK-CL-000280, SPLK-CL-000290 — confirmed in 10 4 2

**SRG-APP-000516-WSR-000079** — CAT II — Applicable, evidence grade C.

All accounts installed with the web server software and tools must have passwords assigned and default passwords changed.

*Basis.* Splunk establishes its initial administrative account from a seed stanza that accepts either a password or a password hash, and the specification text states that the seed is not used once the native credential store exists. The product also carries a native password policy with character-class minimums, an expiry interval, a password history control and a setting that forces a change of a weak password. The requirement is therefore implementable and assessable against the application's own account and password settings.

*Citation.* user-seed.conf.spec ([user_info] with USERNAME, PASSWORD and HASHED_PASSWORD; 'Use HASHED_PASSWORD for a more secure installation'; 'If the $SPLUNK_HOME/etc/passwd file is present, the settings in this file (user-seed.conf) are not used'); authentication.conf.spec:437 ([splunk_auth]), :441 (minPasswordLength), :450 (minPasswordUppercase), :459 (minPasswordLowercase), :468 (minPasswordDigit), :477 (minPasswordSpecial), :487 (expirePasswordDays), :509 (forceWeakPasswordChange), :514 (lockoutUsers), :554 (enablePasswordHistory). Presence on a live Splunk 10.4.2 instance confirmed: btool authentication list --debug returns the authentication stanza.

*Mechanism.* user-seed.conf [user_info] USERNAME, PASSWORD, HASHED_PASSWORD; authentication.conf [splunk_auth] minPasswordLength, minPasswordUppercase, minPasswordLowercase, minPasswordDigit, minPasswordSpecial, expirePasswordDays, forceWeakPasswordChange, enablePasswordHistory, lockoutUsers

*Assessment method.* Run, as the Splunk service account: splunk btool authentication list --debug to examine the password policy. Enumerate the native user store through the authentication/users REST endpoint and confirm every interactive account carries a password. Attempt authentication with the vendor's documented default credential and confirm it is refused.

*Product reference.* SPLK-CL-000260, SPLK-CL-000270, SPLK-CL-000280, SPLK-CL-000290 — confirmed in 10 4 2

**SRG-APP-000516-WSR-000174** — CAT II — Applicable, evidence grade C.

The web server must be configured in accordance with the security configuration settings based on DoD security configuration or implementation guidance, including STIGs, NSA configuration guides, CTOs, and DTMs.

*Basis.* Every security-relevant parameter this requirement reaches is a setting in a Splunk configuration file, and the product resolves those settings through a documented precedence order that an assessment reads in a single pass with the configuration tool. The requirement is therefore implementable and assessable within the application. Because DISA has sunsetted the product-specific STIG for Splunk Enterprise and has published none for the 10.x line, the applicable guidance for this requirement is the set of Security Requirements Guides from which this group is drawn, as tailored and approved in the system security plan; that tailoring is an input to the assessment, not a property of the product.

*Citation.* The shipped specification set comprises 128 files that document the complete configuration surface, 71 of them specification files, 61 of which carry the 'Version 10.0.0' header. Product version confirmed on a live instance as Splunk 10.4.2 (build 33c3bf42cd73). The only product-specific DISA guidance is the sunsetted Splunk Enterprise 8.x for Linux STIG V2R3, which targets a prior major version; the rules it carries for this requirement (SPLK-CL-000260, 000270, 000280, 000290) name props.conf, inputs.conf, outputs.conf and web.conf settings that are all present in the 10.4.2 specification set.

*Mechanism.* The product's layered configuration surface in aggregate - server.conf, web.conf, authorize.conf, authentication.conf, inputs.conf, outputs.conf, limits.conf, indexes.conf, app.conf and the remaining files of the shipped specification set - resolved through the directory precedence those files document

*Assessment method.* Run, as the Splunk service account: splunk btool check to confirm no configuration file is malformed, then splunk btool <conf> list --debug for each conf file named by the group's other determinations. Reconcile each result with the system security plan's tailoring decisions and approved deviations, and record the absence of a 10.x product STIG as the reason the SRG baseline is the governing guidance.

*Product reference.* SPLK-CL-000260, SPLK-CL-000270, SPLK-CL-000280, SPLK-CL-000290 — confirmed in 10 4 2

**SRG-APP-000700-WSR-000100** — CAT II — Applicable, evidence grade C.

The web server must disable accounts when the accounts have expired.

*Basis.* The prior determination rests on two claims, and neither holds. First, it places the account objects with an external provider. Splunk Enterprise is its own authentication authority by default and maintains its own account store: authentication.conf authType accepts Splunk and defaults to Splunk, [splunk_auth] is described in the specification as Splunk's internal authentication system, passwordHashAlgorithm governs how hashed passwords are written to the product's own passwd file, and authTypePreferredForUserCollision exists specifically to resolve username collisions between native authentication users and SAML users, which establishes that native accounts persist alongside provider accounts rather than being displaced by them. A providing baseline that does not hold all accounts in scope cannot carry the control, so grade D fails on its own terms. Second, the claim that the product exposes no mechanism keyed to account expiry is contradicted by the specification set. Splunk Enterprise 10.4.2 implements the service-provider side of System for Cross-Domain Identity Management, the protocol by which an identity provider applies account expiration and deactivation to the account objects a service holds: splunkd launches a supervisor process that handles authorization tokens for SCIM operations, Splunk Web exposes Automated User Management controls for SCIM, and the authentication configuration carries a SCIM provider domain allowlist together with a boolean governing synchronization of user deletions. The expiration decision may originate with an identity provider, but this requirement directs that the Splunk instance disable the account, and the mechanism that applies disablement to the Splunk account object is the application's own configuration. The requirement is therefore APPLICABLE and its result is obtained from the application. The prior evidence is additionally defective in method: the specification set contains 71 specification files, not 128 (that count includes 56 example configuration files and one XML file shipped beside them), and two account lifecycle settings resolve in authentication.conf on a 10.4.2 instance while appearing in no specification file, so a search over a guessed term list cannot establish capability absence. The prior reading of expireUserAccounts as password expiration is correct and is retained; it is not the only relevant mechanism.

*Citation.* Native account store inside the application boundary: authentication.conf.spec:30 and :33 (authType = [Splunk|LDAP|Scripted|SAML|ProxySSO], Default: Splunk); :437-438 ([splunk_auth], "Settings for Splunk's internal authentication system"); :58-60 (passwordHashAlgorithm controls how hashed passwords are stored in the product's passwd file for the default Splunk authType); :35-42 (authTypePreferredForUserCollision, "The authentication scheme to use when the Splunk platform detects username collision between native authentication and SAML users"); user-seed.conf.spec:12 (the passwd file takes precedence over user-seed.conf). SCIM account lifecycle mechanism: server.conf.spec:6584-6591 ([teleport_supervisor], disabled = <boolean>, "splunkd launches the teleport supervisor process, which handles authorization tokens for System for Cross-Domain Identity Management (SCIM) operations"); web-features.conf.spec:400-409 ([feature:identity_sidecar_scim], enabled = <boolean>, "Automated User Management (AUM) controls for System for Cross-Domain Identity Management (SCIM)"). Confirmed to exist and resolve on a Splunk 10.4.2 instance (build 33c3bf42cd73) read-only: btool server list teleport_supervisor returns the stanza and its disabled key; btool web-features list returns [feature:identity_sidecar_scim] and its enabled key; btool authentication list returns scimSupportedDomains under [authentication] and scsSyncUserDeletes under [splunk_auth]. Method defect in the prior evidence: the specification set is 71 *.spec files (56 example *.conf files and one *.xml account for the remainder of the 128 files); a case-insensitive search of all 71 specification files for scimSupportedDomains returns 0 lines and for scsSyncUserDeletes returns 0 lines, yet both settings resolve on the instance. Password aging citations in the prior evidence are confirmed: authentication.conf.spec:487, :495, :504-507 (expireUserAccounts, "Specifies whether password expiration is enabled").

*Mechanism.* server.conf [teleport_supervisor] disabled; web-features.conf [feature:identity_sidecar_scim] enabled; authentication.conf [authentication] scimSupportedDomains and [splunk_auth] scsSyncUserDeletes; authentication.conf [authentication] authType with [splunk_auth] as the native account store governing which accounts the application itself holds

*Providing baseline.* The organization's directory service (LDAP or Active Directory) or SAML identity provider, bound to the application through authentication.conf [authentication] authType and the roleMap and userToRoleMap stanzas; that baseline holds the account expiration state.

*Assessment method.* Run, as the splunk user: splunk btool server list teleport_supervisor --debug; splunk btool web-features list --debug and select [feature:identity_sidecar_scim]; splunk btool authentication list --debug and select authType, scimSupportedDomains and scsSyncUserDeletes. Then enumerate the accounts the application itself holds, GET services/authentication/users over the management port, and examine each against the expiration state held by the authority that issues the identity. Determine Satisfied where every account the application holds is either governed by SCIM-driven deprovisioning from that authority or shown to have been removed on expiration.

**SRG-APP-000705-AU-000110** — CAT II — Applicable, evidence grade C.

The Central Log Server must disable accounts when the accounts are no longer associated to a user.

*Basis.* The prior determination asserts that the product exposes no de-association trigger anywhere in its configuration surface, and the specification set contradicts this twice over. First, Splunk Enterprise 10.4.2 implements the service-provider side of System for Cross-Domain Identity Management, which is the protocol an identity provider uses to deactivate and delete the account objects a service holds when the holder departs or the account no longer maps to an individual: splunkd launches a supervisor process handling authorization tokens for SCIM operations, Splunk Web exposes Automated User Management controls for SCIM, and the authentication configuration carries a SCIM provider domain allowlist together with a boolean governing synchronization of user deletions. Second, the prior evidence cites the orphaned scheduled search check as proof of absence, but the specification text it cites describes the product recognizing exactly the de-association condition this requirement names: the check exists for the case where a user creates scheduled searches and then departs the organization, causing that account to be deactivated, and the product raises an administrative notification on a recurring basis as a result. That is a configurable application mechanism keyed to the de-association condition, not evidence of its absence. The check notifies rather than disables, so it does not satisfy the requirement on its own, but it defeats the claim on which the prior grade rests. The boundary claim fails independently: the application maintains its own account store and is its own authentication authority by default, so the named provider does not hold all accounts in scope and cannot carry the control.

*Citation.* SCIM account lifecycle mechanism: server.conf.spec:6584-6591 ([teleport_supervisor], disabled = <boolean>, "splunkd launches the teleport supervisor process, which handles authorization tokens for System for Cross-Domain Identity Management (SCIM) operations"); web-features.conf.spec:400-409 ([feature:identity_sidecar_scim], enabled = <boolean>, "Automated User Management (AUM) controls for System for Cross-Domain Identity Management (SCIM)"). De-association detection: limits.conf.spec:4436 ([system_checks]) with :4486-4497 (orphan_searches = enabled|disabled; "Scheduled saved searches with invalid owners are considered 'orphaned'"; "Typically, this situation occurs when a user creates scheduled searches then departs the organization or company, causing their account to be deactivated"; "this check and any resulting notifications occur on system startup and every 24 hours thereafter") - the same lines the prior determination cited to establish absence. Native account store inside the boundary: authentication.conf.spec:30 and :33 (authType, Default: Splunk); :437-438 ([splunk_auth], Splunk's internal authentication system); :58-60 (hashed passwords in the product's own passwd file); :35-42 (authTypePreferredForUserCollision resolves collisions between native authentication and SAML users, so native accounts persist under SAML). Confirmed to exist and resolve on a Splunk 10.4.2 instance (build 33c3bf42cd73) read-only: btool server list teleport_supervisor; btool web-features list ([feature:identity_sidecar_scim]); btool authentication list (scimSupportedDomains under [authentication], scsSyncUserDeletes under [splunk_auth]); btool limits list system_checks (orphan_searches). Method defect: the specification set is 71 *.spec files, not 128 (56 example *.conf files and one *.xml make up the rest); scimSupportedDomains and scsSyncUserDeletes each return 0 lines across all 71 specification files yet both resolve on the instance, so a term-list search of that set cannot establish capability absence.

*Mechanism.* server.conf [teleport_supervisor] disabled; web-features.conf [feature:identity_sidecar_scim] enabled; authentication.conf [authentication] scimSupportedDomains and [splunk_auth] scsSyncUserDeletes; limits.conf [system_checks] orphan_searches as the application-side detection of an account that no longer maps to an individual

*Providing baseline.* The organization's directory service (LDAP or Active Directory) or SAML identity provider, bound through authentication.conf [authentication] authType and the roleMap and userToRoleMap stanzas; that baseline records the association between an account and an individual.

*Assessment method.* Run, as the splunk user: splunk btool server list teleport_supervisor --debug; splunk btool web-features list --debug and select [feature:identity_sidecar_scim]; splunk btool authentication list --debug and select authType, scimSupportedDomains and scsSyncUserDeletes; splunk btool limits list system_checks --debug and select orphan_searches. Enumerate the accounts the application holds with GET services/authentication/users over the management port and reconcile each against the authority that issues the identity. Determine Satisfied where de-association at that authority propagates to the application account object through SCIM-driven deprovisioning, and where the orphaned scheduled search check is enabled so that accounts no longer mapping to an individual are surfaced to administrators.

**SRG-APP-000705-WSR-000110** — CAT II — Applicable, evidence grade C.

The web server must disable accounts when the accounts are no longer associated to a user.

*Basis.* The prior determination delegates twice, and the first hop never leaves the application. Splunk Web authenticating users through splunkd is delegation between two components of the same product under assessment, so citing the management endpoint that Splunk Web uses to reach splunkd does not place the requirement outside the application boundary; it relocates the requirement within that boundary. The second hop then fails for the same reason it fails for the application as a whole: the product is its own authentication authority by default and maintains its own account store, so the named identity provider does not hold all accounts in scope. The claim that the configuration surface contains no account de-association trigger at either tier is also incorrect, and the web tier is where the clearest counter-evidence sits: web-features.conf defines the Automated User Management controls for System for Cross-Domain Identity Management, the protocol by which an identity provider deactivates and deletes the account objects a service holds. SCIM is supported on the splunkd side by a supervisor process that handles its authorization tokens and by a SCIM provider domain allowlist and a user-deletion synchronization setting in the authentication configuration. Both tiers of the application therefore carry configuration that bears on account de-association, and the requirement is APPLICABLE.

*Citation.* Web-tier mechanism: web-features.conf.spec:400-409 ([feature:identity_sidecar_scim], enabled = <boolean>, "Whether or not Splunk Web displays Automated User Management (AUM) controls for System for Cross-Domain Identity Management (SCIM) in the SAML configuration dialog page"). Supporting splunkd mechanism: server.conf.spec:6584-6591 ([teleport_supervisor], disabled = <boolean>, SCIM authorization tokens). Intra-application delegation, not a boundary: web.conf.spec:16 ([settings]) with :35-37 (mgmtHostPort, "The host port of the splunkd process") names a component of the same product; authentication.conf.spec:26-30 and :33 place the single authentication authority inside that product, with authType defaulting to Splunk, and :437-438 describe [splunk_auth] as Splunk's internal authentication system, :58-60 placing the account store in the product's own passwd file and :35-42 (authTypePreferredForUserCollision) showing native accounts persist alongside SAML accounts. Confirmed to exist and resolve on a Splunk 10.4.2 instance (build 33c3bf42cd73) read-only: btool web-features list returns [feature:identity_sidecar_scim] and its enabled key; btool server list teleport_supervisor returns the stanza; btool authentication list returns scimSupportedDomains under [authentication] and scsSyncUserDeletes under [splunk_auth]. Method defect: the prior search is described as covering a 128-file specification set; the set holds 71 *.spec files alongside 56 example *.conf files and one *.xml, and scimSupportedDomains and scsSyncUserDeletes each return 0 lines across all 71 specification files while both resolve on the instance, so the search as run cannot support a claim of capability absence at either tier.

*Mechanism.* web-features.conf [feature:identity_sidecar_scim] enabled for the web tier; server.conf [teleport_supervisor] disabled and authentication.conf [authentication] scimSupportedDomains with [splunk_auth] scsSyncUserDeletes for the splunkd tier that Splunk Web authenticates against; authentication.conf [authentication] authType identifying the authentication authority within the application

*Providing baseline.* The organization's directory service (LDAP or Active Directory) or SAML identity provider, bound through authentication.conf [authentication] authType; Splunk Web delegates all account existence and status decisions to that authority by way of splunkd.

*Assessment method.* Run, as the splunk user: splunk btool web-features list --debug and select [feature:identity_sidecar_scim]; splunk btool server list teleport_supervisor --debug; splunk btool authentication list --debug and select authType, scimSupportedDomains and scsSyncUserDeletes; splunk btool web list settings --debug and select mgmtHostPort to identify the splunkd instance the web tier authenticates against. Enumerate accounts with GET services/authentication/users on that instance and reconcile against the authority that issues the identity. Determine Satisfied where accounts reachable through Splunk Web are subject to SCIM-driven deprovisioning from that authority, or are shown to have been removed when no longer associated with an individual.

**SRG-APP-000745-AU-000120** — CAT II — Applicable, evidence grade C.

The Central Log Server must implement the capability to centrally review and analyze audit records from multiple components within the system.

*Basis.* Splunk aggregates records from multiple components through its receiving inputs and searches across them through distributed search, both of which are application configuration. The requirement applies to the application.

*Citation.* distsearch.conf.spec:29 [distributedSearch], :81 servers; inputs.conf.spec:239 [monitor://<path>], :630 [splunktcp], :880 [splunktcp-ssl:<port>], :1652 [http]; authorize.conf.spec:367 srchIndexesAllowed [10.4.2 spec set]. Distsearch.conf and inputs.conf are readable through btool on a 10.4.2 instance.

*Mechanism.* inputs.conf [splunktcp], [splunktcp-ssl:<port>], [http]; distsearch.conf [distributedSearch] servers; authorize.conf [role_<roleName>] srchIndexesAllowed

*Assessment method.* splunk btool inputs list --debug for receiving stanzas; splunk btool distsearch list --debug for [distributedSearch] servers; compare the set of reporting components against the scope of coverage recorded in the system security plan.

*Product reference.* SPLK-CL-000100 — confirmed in 10 4 2

**SRG-APP-000745-WSR-000120** — CAT II — Applicable, evidence grade C.

The web server must implement the capability to centrally review and analyze audit records from multiple components within the system.

*Basis.* Splunk Web is the application's own review and analysis interface, served by the same instance, so this web server requirement is inside the application boundary rather than inherited. The interface is enabled in web.conf and the breadth of records it can reach is set by distributed search and role index scope.

*Citation.* web.conf.spec:16 [settings], :23 startwebserver; distsearch.conf.spec:29 [distributedSearch], :81 servers; authorize.conf.spec:69 [role_<roleName>], :367 srchIndexesAllowed [10.4.2 spec set].

*Mechanism.* web.conf [settings] startwebserver; distsearch.conf [distributedSearch] servers; authorize.conf [role_<roleName>] srchIndexesAllowed

*Assessment method.* splunk btool web list --debug for startwebserver; splunk btool distsearch list --debug for [distributedSearch] servers; splunk btool authorize list --debug for srchIndexesAllowed on the roles used for audit review.

*Product reference.* SPLK-CL-000100 — confirmed in 10 4 2

**SRG-APP-000750-AU-000130** — CAT II — Applicable, evidence grade C.

The Central Log Server must implement an audit reduction capability that supports on-demand audit review and analysis.

*Basis.* Audit reduction in Splunk is the search-time knowledge layer applied over indexed records: field extraction, field aliasing, lookups, macros and data models all reduce raw records to reviewable fields and are set in configuration. The requirement applies to the application.

*Citation.* props.conf.spec:1173 REPORT-<class>, :1190 EXTRACT-<class>, :1353 FIELDALIAS-<class>, :1401 EVAL-<fieldname>, :1417 LOOKUP-<class>; transforms.conf.spec:241 DEST_KEY; macros.conf.spec:24 [<STANZA_NAME>], :52 definition; datamodels.conf.spec:26 [<datamodel_name>], :29 acceleration [10.4.2 spec set].

*Mechanism.* props.conf [<source type>] REPORT-<class>, EXTRACT-<class>, FIELDALIAS-<class>, EVAL-<fieldname>, LOOKUP-<class>; transforms.conf; macros.conf definition; datamodels.conf

*Assessment method.* splunk btool props list --debug and splunk btool transforms list --debug for the audit source types in scope; splunk btool macros list --debug and splunk btool datamodels list --debug; confirm a reviewer can reduce an audit record set to named fields on request.

**SRG-APP-000755-AU-000140** — CAT II — Applicable, evidence grade C.

The Central Log Server must implement an audit reduction capability that supports on-demand reporting requirements.

*Basis.* The same search-time knowledge layer that performs reduction feeds saved reports, and both the reduction and the report that consumes it are set in application configuration. The requirement applies to the application.

*Citation.* props.conf.spec:1173 REPORT-<class>, :1417 LOOKUP-<class>; macros.conf.spec:52 definition; savedsearches.conf.spec:44 search, :86 enableSched, :92 cron_schedule, :418 action.email.sendpdf [10.4.2 spec set].

*Mechanism.* props.conf REPORT-<class>, LOOKUP-<class>; macros.conf definition; savedsearches.conf [<stanza name>] search, enableSched, cron_schedule, action.email.sendpdf

*Assessment method.* splunk btool props list --debug and splunk btool macros list --debug for the reduction definitions; splunk btool savedsearches list --debug for the reports that consume them.

**SRG-APP-000760-AU-000150** — CAT II — Applicable, evidence grade C.

The Central Log Server must implement an audit reduction capability that supports after-the-fact investigations of incidents.

*Basis.* Reduction for after-the-fact investigation has to reach records still held in the index, so both the search-time knowledge layer and index retention are the application settings in question. The requirement applies to the application.

*Citation.* props.conf.spec:1173 REPORT-<class>, :1190 EXTRACT-<class>, :1417 LOOKUP-<class>; indexes.conf.spec:441-442 (PER INDEX OPTIONS), :761 frozenTimePeriodInSecs, :892 coldToFrozenDir; savedsearches.conf.spec:599 dispatch.earliest_time [10.4.2 spec set].

*Mechanism.* props.conf REPORT-<class>, EXTRACT-<class>, LOOKUP-<class>; indexes.conf [<index>] frozenTimePeriodInSecs, coldToFrozenDir

*Assessment method.* splunk btool indexes list --debug for frozenTimePeriodInSecs and coldToFrozenDir on each audit index; splunk btool props list --debug for the extractions applied to those source types; confirm a reduction over the oldest retained record returns fields.

**SRG-APP-000765-AU-000160** — CAT II — Applicable, evidence grade C.

The Central Log Server must implement a report generation capability that supports on-demand audit review and analysis.

*Basis.* Report generation supporting on-demand review and analysis is a saved search object in Splunk, with its scope, time range and the roles permitted to run it all set in configuration. The requirement applies to the application.

*Citation.* savedsearches.conf.spec:31 [<stanza name>], :44 search, :599 dispatch.earliest_time, :606 dispatch.latest_time; authorize.conf.spec:1088 [capability::search], :1081 [capability::schedule_search], :367 srchIndexesAllowed [10.4.2 spec set].

*Mechanism.* savedsearches.conf [<stanza name>] search, dispatch.earliest_time, dispatch.latest_time; authorize.conf [capability::search], [capability::schedule_search], srchIndexesAllowed

*Assessment method.* splunk btool savedsearches list --debug for report stanzas over the audit indexes; splunk btool authorize list --debug for the capabilities and index scope of the reviewing roles.

**SRG-APP-000770-AU-000170** — CAT II — Applicable, evidence grade C.

The Central Log Server must implement a report generation capability that supports on-demand reporting requirements.

*Basis.* Splunk sets both report scheduling and report delivery in configuration, which is what carries a report generation capability past ad hoc search into on-demand reporting. The requirement applies to the application.

*Citation.* savedsearches.conf.spec:86 enableSched, :92 cron_schedule, :228 schedule_window, :335 action.email, :339 action.email.to, :418 action.email.sendpdf; alert_actions.conf.spec:176 [email], :656 [webhook] [10.4.2 spec set].

*Mechanism.* savedsearches.conf [<stanza name>] enableSched, cron_schedule, schedule_window, action.email, action.email.to, action.email.sendpdf; alert_actions.conf [email], [webhook]

*Assessment method.* splunk btool savedsearches list --debug and splunk btool alert_actions list --debug; confirm a report can be produced and delivered on request as well as on its schedule.

**SRG-APP-000775-AU-000180** — CAT II — Applicable, evidence grade C.

The Central Log Server must implement a report generation capability that supports after-the-fact investigations of incidents.

*Basis.* A report generation capability for after-the-fact investigation depends on a retrospective dispatch range over retained records, both set in application configuration. The requirement applies to the application.

*Citation.* savedsearches.conf.spec:44 search, :599 dispatch.earliest_time, :606 dispatch.latest_time, :736 durable.track_time_type; indexes.conf.spec:761 frozenTimePeriodInSecs, :892 coldToFrozenDir [10.4.2 spec set].

*Mechanism.* savedsearches.conf [<stanza name>] search, dispatch.earliest_time, dispatch.latest_time; indexes.conf [<index>] frozenTimePeriodInSecs, coldToFrozenDir

*Assessment method.* splunk btool savedsearches list --debug for the dispatch range on investigative reports; splunk btool indexes list --debug for retention on the audit indexes; produce a report over the oldest retained audit record.

**SRG-APP-000780-AU-000190** — CAT II — Applicable, evidence grade C.

The Central Log Server must implement an audit reduction capability that does not alter original content or time ordering of audit records.

*Basis.* Splunk reduces audit records at search time over the stored rawdata journal, and the specification set draws the line between index-time settings, which write to the stored event, and search-time settings, which do not. The product also exposes content-altering settings, so the requirement applies and the determination rests on whether those keys are applied to audit data.

*Citation.* props.conf.spec:1042-1046 (TRANSFORMS is index-time; REPORT and EXTRACT are search-time), :1331 SEDCMD-<class>; transforms.conf.spec:241 DEST_KEY, :286 (default _raw); field_filters.conf.spec:32 [<fieldFilterName>], :37 action; indexes.conf.spec:671 enableDataIntegrityControl (hashes computed on rawdata slices for future data integrity checks) [10.4.2 spec set].

*Mechanism.* props.conf SEDCMD-<class> and TRANSFORMS-<class>; transforms.conf DEST_KEY = _raw; field_filters.conf [<fieldFilterName>] action; indexes.conf [<index>] enableDataIntegrityControl

*Assessment method.* splunk btool props list --debug and splunk btool transforms list --debug for SEDCMD- entries and index-time transforms writing to _raw on audit source types; splunk btool field_filters list --debug; splunk btool indexes list --debug for enableDataIntegrityControl, then run splunk check-integrity on a bucket of an audit index.

**SRG-APP-000785-AU-000200** — CAT II — Applicable, evidence grade C.

The Central Log Server must implement a report generation capability that does not alter original content or time ordering of audit records.

*Basis.* A Splunk report is a search over indexed records, so content and ordering in the report are governed by the report's own search string and by the search-time settings applied to the source types it reads. The requirement applies to the application.

*Citation.* savedsearches.conf.spec:44 search; props.conf.spec:1331 SEDCMD-<class>, :1401 EVAL-<fieldname>, :1173 REPORT-<class>; field_filters.conf.spec:37 action (null(), sha256(), sha512(), string literal, sed() on _raw); indexes.conf.spec:671 enableDataIntegrityControl [10.4.2 spec set].

*Mechanism.* savedsearches.conf [<stanza name>] search; props.conf SEDCMD-<class>, EVAL-<fieldname>; field_filters.conf [<fieldFilterName>] action

*Assessment method.* splunk btool savedsearches list --debug and read each audit report's search string for commands that rewrite _raw or reorder _time; splunk btool field_filters list --debug for filters whose index clause covers an audit index.

**SRG-APP-000790-AU-000210** — CAT II — Applicable, evidence grade C.

The Central Log Server must implement the capability to process, sort, and search audit records for events of interest based on organization-defined audit fields within audit records.

*Basis.* Splunk exposes field definition, extraction and indexing as configuration, which is what lets records be processed, sorted and searched on organization-defined audit fields. The requirement applies to the application; the field list itself is an organization-defined parameter that the system security plan records.

*Citation.* props.conf.spec:1190 EXTRACT-<class>, :1173 REPORT-<class>, :1353 FIELDALIAS-<class>, :1401 EVAL-<fieldname>, :1417 LOOKUP-<class>; fields.conf.spec:43 [<field name>|<metadata>::<metadata_name>::<wildcard expression>], :78 TOKENIZER, :93 INDEXED; transforms.conf.spec:241 DEST_KEY; authorize.conf.spec:160 srchFilter, :367 srchIndexesAllowed [10.4.2 spec set].

*Mechanism.* props.conf EXTRACT-<class>, REPORT-<class>, FIELDALIAS-<class>, EVAL-<fieldname>, LOOKUP-<class>; fields.conf [<field name>] INDEXED, TOKENIZER; transforms.conf; authorize.conf [role_<roleName>] srchFilter, srchIndexesAllowed

*Assessment method.* splunk btool props list --debug and splunk btool fields list --debug for the organization-defined audit fields; then search and sort audit records on each of those fields and confirm each resolves.

**SRG-APP-000795-AU-000220** — CAT II — Applicable, evidence grade C.

The Central Log Server must alert organization-defined personnel or roles upon detection of unauthorized access, modification, or deletion of audit information.

*Basis.* Splunk implements alerting as a saved search with a trigger condition and a notification action, and the audit trail and index integrity hashing supply the detection source for access to, modification of, or deletion of audit information. The requirement applies to the application; the personnel or roles to notify are an organization-defined parameter.

*Citation.* savedsearches.conf.spec:44 search, :284 counttype, :305 alert_condition, :335 action.email, :339 action.email.to, :922 alert.severity, :946 alert.track; alert_actions.conf.spec:176 [email], :572 [script], :656 [webhook]; audit.conf.spec:47 [auditconfig:/path], :48 enabled (protected actions such as delete always remain logged); indexes.conf.spec:671 enableDataIntegrityControl [10.4.2 spec set].

*Mechanism.* savedsearches.conf [<stanza name>] search, alert_condition, counttype, action.email, action.email.to; alert_actions.conf [email], [script], [webhook]; audit.conf [auditconfig:/path] enabled; indexes.conf [<index>] enableDataIntegrityControl

*Assessment method.* splunk btool savedsearches list --debug for alert stanzas whose search covers the audit trail and whose action names a recipient; splunk btool alert_actions list --debug; splunk btool audit list --debug; then generate an unauthorized access attempt against audit data and confirm the notification is produced.

*Product reference.* SPLK-CL-000140 — confirmed in 10 4 2

**SRG-APP-000795-WSR-000130** — CAT II — Applicable, evidence grade C.

The web server must alert organization-defined personnel or roles upon detection of unauthorized access, modification, or deletion of audit information.

*Basis.* Splunk Web is a component of the application rather than a separate web server baseline, and the alerting mechanism that serves this objective is the same saved search and alert action surface reached through it. The requirement applies to the application.

*Citation.* web.conf.spec:16 [settings], :23 startwebserver, :926 log.access_file; savedsearches.conf.spec:305 alert_condition, :335 action.email, :339 action.email.to; alert_actions.conf.spec:176 [email], :656 [webhook]; audit.conf.spec:47 [auditconfig:/path] [10.4.2 spec set].

*Mechanism.* savedsearches.conf [<stanza name>] alert_condition, action.email, action.email.to; alert_actions.conf [email], [webhook]; web.conf [settings] startwebserver, log.access_file

*Assessment method.* splunk btool savedsearches list --debug for alert stanzas covering the web access and audit records; splunk btool alert_actions list --debug for the named recipient; confirm a notification is produced on an unauthorized access attempt against audit data.

*Product reference.* SPLK-CL-000140 — confirmed in 10 4 2

**SRG-APP-000800-AU-000230** — CAT II — Applicable, evidence grade C.

The Central Log Server must implement the capability for organization-defined individuals or roles to change the auditing to be performed on organization-defined system components based on organization-defined selectable event criteria within organization-defined time thresholds.

*Basis.* Splunk 10.4.2 exposes selectable auditing per REST path, restricts who may change it through a named capability, and applies the change on a reload rather than a restart, which together cover the role, the selectable criteria and the time threshold. The requirement applies to the application; the individuals, components, criteria and thresholds are organization-defined parameters the system security plan records.

*Citation.* audit.conf.spec:47 [auditconfig:/path], :48 enabled, :57 disabled, :64 sampling.<action>, :79-80 (settings take effect when you reload the audit subsystem or the audit.conf file using the REST API); authorize.conf.spec:578 [capability::change_audit] (lets a user change audit settings through the audit endpoints and reload audit settings), :69 [role_<roleName>]; app.conf.spec:199 [triggers], :205 reload.<conf_file_name> [10.4.2 spec set]. On a 10.4.2 instance, btool authorize list --debug returns [capability::change_audit] and btool audit list --debug returns [auditTrail] and [auditconfig:...] stanzas.

*Mechanism.* audit.conf [auditconfig:/path] enabled, disabled, sampling.<action>; authorize.conf [role_<roleName>] and [capability::change_audit]; app.conf [triggers] reload.audit

*Assessment method.* splunk btool authorize list --debug for the roles holding change_audit; splunk btool audit list --debug for the [auditconfig:...] stanzas; splunk btool app list --debug for reload.audit; then change an audit action for a component and confirm the change is in effect within the organization-defined threshold without a restart.

**SRG-APP-000805-AU-000240** — CAT II — Applicable, evidence grade C.

The Central Log Server must automatically generate audit records of the enforcement actions.

*Basis.* Splunk writes a configuration change record for every tracked change to a configuration file beneath its system, apps, users and peer-apps directories, under a dedicated stanza whose mode setting selects whether the changed setting values are recorded or only the fact of the change. A separate stanza routes the product's audit events into the audit index so they are searchable and retained alongside other records. Those are the enforcement-action audit records this requirement reaches, and both are governed by settings in the application.

*Citation.* server.conf.spec:598-640 ('[config_change_tracker]'; disabled at :599 - 'Whether or not splunkd writes configuration changes to the configuration change log'; 'mode = [auto|diff|track-only]' at :609; tracked directories enumerated at :626-632; denylist at :636; log_throttling_disabled at :641); audit.conf.spec:23-29 ('[auditTrail]'; 'queueing = <boolean>'; 'Whether or not audit events are sent to the indexQueue'). Presence on a live Splunk 10.4.2 instance confirmed: btool server list --debug returns config_change_tracker and btool audit list --debug returns the auditTrail stanza.

*Mechanism.* server.conf [config_change_tracker] disabled, mode = [auto|diff|track-only], denylist, exclude_fields, log_throttling_disabled; audit.conf [auditTrail] queueing

*Assessment method.* Run, as the Splunk service account: splunk btool server list config_change_tracker --debug; splunk btool audit list --debug. Then make a tracked configuration change on a test instance and confirm a corresponding record appears in the configuration change log and in the audit index, and that the exclude_fields and denylist settings do not suppress security-relevant stanzas.

**SRG-APP-000805-WSR-000140** — CAT II — Applicable, evidence grade C.

The web server must automatically generate audit records of the enforcement actions.

*Basis.* The web interface and the management interface of this product share one configuration layer, and the product records changes to that layer automatically under a dedicated stanza, with a mode setting that selects whether changed values are captured. The product's audit event stream is routed to the audit index by a separate setting, and the capability to alter audit configuration is itself a named capability that can be withheld. Automatic generation of audit records for configuration-change enforcement actions is therefore implementable through the application's own configuration.

*Citation.* server.conf.spec:598-640 ([config_change_tracker] disabled at :599, mode at :609, tracked directories at :626-632, denylist at :636, exclude_fields at :666); audit.conf.spec:23-29 ([auditTrail] queueing); authorize.conf.spec:483 ([capability::change_audit]). Presence on a live Splunk 10.4.2 instance confirmed by btool reads of server, audit and authorize.

*Mechanism.* server.conf [config_change_tracker] disabled, mode = [auto|diff|track-only], denylist, exclude_fields; audit.conf [auditTrail] queueing; authorize.conf [capability::change_audit]

*Assessment method.* Run, as the Splunk service account: splunk btool server list config_change_tracker --debug; splunk btool audit list --debug; splunk btool authorize list --debug. Make a configuration change through the web interface on a test instance and confirm a corresponding record is written to the configuration change log and indexed in the audit index, and that change_audit is held only by administrative roles.

**SRG-APP-000810-AU-000250** — CAT II — Applicable, evidence grade C.

The Central Log Server must prevent the installation of organization-defined software and firmware components without verification that the component has been digitally signed using a certificate that is recognized and approved by the organization.

*Basis.* Splunk exposes settings by which installation of software components through the application is prevented: the installation capabilities are withheld from roles, and the instance's access to the remote applications repository is denied. The product exposes no verification of a digital signature on a package at install time - an exhaustive search of the specification set returns no code-signing setting of any kind - so the signature-verification element of this requirement is provided by the host operating system package management baseline for the vendor's product packages and by the organization's app and add-on vetting process for Splunk add-ons. The requirement applies to the application because the prevention element is implementable within it, and an assessment must record the signature-verification dependency explicitly rather than treat the requirement as inherited in full.

*Citation.* authorize.conf.spec:760-763 ('[capability::install_apps]'; 'Lets a user install, uninstall, create, and update apps on the local Splunk platform instance through the apps/local endpoint'), :589-592 ([capability::edit_local_apps]), :885 ([capability::rest_apps_management]); server.conf.spec:1727-1735 ('[applicationsManagement]'; 'allowInternetAccess = <boolean>'; 'Lets the Splunk platform instance access the remote applications repository'); limits.conf.spec:4450 (installed_files_integrity). Search of all 128 files of the shipped specification set for package or module signature verification returns no match: all 56 matches for '\\bsign(ed|ing|ature)?\\b' concern TLS certificates, remote-storage request signing, SmartStore checksum algorithms or fschange signed audit events. Presence of the cited settings on a live Splunk 10.4.2 instance confirmed by btool reads of authorize, server and limits.

*Mechanism.* authorize.conf [capability::install_apps], [capability::edit_local_apps], [capability::rest_apps_management]; server.conf [applicationsManagement] allowInternetAccess; limits.conf [system_checks] installed_files_integrity

*Assessment method.* Run, as the Splunk service account: splunk btool authorize list --debug to enumerate roles holding install_apps, edit_local_apps and rest_apps_management; splunk btool server list applicationsManagement --debug to examine allowInternetAccess; splunk btool limits list system_checks --debug. Examine the host package manager's signature verification setting for the vendor repository and the organization's add-on vetting records for every installed app.

**SRG-APP-000815-AU-000260** — CAT II — Applicable, evidence grade C.

The Central Log Server must require users to be individually authenticated before granting access to the shared accounts or resources.

*Basis.* Splunk Enterprise binds each session to an individual account and reaches shared objects only through role capabilities attached to that account; the specification set declares no shared or group credential authentication path. The requirement applies and is implemented through the product's own configuration.

*Citation.* authentication.conf.spec:30 authType = [Splunk|LDAP|Scripted|SAML|ProxySSO] establishes the per-user identity source; authorize.conf.spec:67 [role_<roleName>] carries capability grants and importRoles, and states that capabilities are disabled by default. A 10.4.2 instance returns 26 role_* stanzas from splunk btool authorize list --debug.

*Mechanism.* authentication.conf [authentication]: authType; authorize.conf [role_<roleName>]: capability grants and importRoles

*Assessment method.* splunk btool authentication list --debug for authType; splunk btool authorize list --debug to enumerate role_* stanzas; examine the roleMap stanzas for individual-account-to-role assignment, and the designation record covering any shared administrative account.

**SRG-APP-000815-WSR-000160** — CAT II — Applicable, evidence grade C.

The web server must require users to be individually authenticated before granting access to the shared accounts or resources.

*Basis.* Splunk Web is a component of the Splunk application and holds no credential store of its own; it establishes each session against the splunkd authentication system and binds that session to an individual account. The requirement applies to the web tier through that delegation.

*Citation.* web.conf.spec declares no password-policy or credential-store key - grep -c -E '^(minPassword|expirePassword|passwordHistory|passwordHash|enablePasswordHistory|forceWeakPassword)' web.conf.spec returns 0. Per-user session handling at web.conf.spec:920 tools.sessions.on; identity source at authentication.conf.spec:30; role binding at authorize.conf.spec:67.

*Mechanism.* web.conf [settings]: tools.sessions.*; authentication.conf [authentication]: authType; authorize.conf [role_<roleName>]

*Assessment method.* splunk btool web list --debug for tools.sessions.*; splunk btool authentication list --debug for authType; confirm no web-tier credential store independent of splunkd authentication is in use.

**SRG-APP-000820-WSR-000170** — CAT II — Applicable, evidence grade C.

The web server must implement multifactor authentication for local; network; and/or remote access to privileged accounts; and/or nonprivileged accounts such that one of the factors is provided by a device separate from the system gaining access.

*Basis.* Splunk Enterprise supports a second authentication factor carried on a device separate from the accessing system, either through a multifactor vendor integration or through a client certificate held on a hardware token. The requirement applies and is implemented through the product's own configuration.

*Citation.* authentication.conf.spec:87 externalTwoFactorAuthVendor, which states that a valid vendor string enables multifactor authentication and that Duo and RSA are supported; :95 externalTwoFactorAuthSettings; :1421 [<duo-externalTwoFactorAuthSettings-key>]; :1583 [<rsa-externalTwoFactorAuthSettings-key>]. Hardware token path at web.conf.spec:120 enableCertBasedUserAuth with :151 requireClientCert.

*Mechanism.* authentication.conf [authentication]: externalTwoFactorAuthVendor, externalTwoFactorAuthSettings, with [<duo-externalTwoFactorAuthSettings-key>] or [<rsa-externalTwoFactorAuthSettings-key>]; web.conf [settings]: enableCertBasedUserAuth with requireClientCert

*Assessment method.* splunk btool authentication list --debug for externalTwoFactorAuthVendor, externalTwoFactorAuthSettings and the referenced vendor stanza; or splunk btool web list --debug for enableCertBasedUserAuth and requireClientCert.

**SRG-APP-000825-AU-000280** — CAT II — Applicable, evidence grade C.

The Central Log Server must implement multifactor authentication for local; network; and/or remote access to privileged accounts; and/or nonprivileged accounts such that the device meets organization-defined strength of mechanism requirements.

*Basis.* The setting that selects the second factor's device class is a Splunk configuration key, so the requirement applies to the application; the strength of mechanism value is an organizational assignment that the configuration then implements. The product does not itself evaluate a device against a strength threshold, so the assessment compares the configured device class against the organizational assignment.

*Citation.* authentication.conf.spec:87 externalTwoFactorAuthVendor and :95 externalTwoFactorAuthSettings, with vendor stanzas at :1421 and :1583; web.conf.spec:120 enableCertBasedUserAuth and :133-143 certBasedUserAuthMethod, which extracts EDIPI and PIV identifiers from a hardware credential.

*Mechanism.* authentication.conf [authentication]: externalTwoFactorAuthVendor, externalTwoFactorAuthSettings; web.conf [settings]: enableCertBasedUserAuth, certBasedUserAuthMethod

*Assessment method.* splunk btool authentication list --debug for externalTwoFactorAuthVendor and its vendor stanza, and splunk btool web list --debug for enableCertBasedUserAuth and certBasedUserAuthMethod; compare the configured device class against the organization-defined strength of mechanism in the authentication policy.

*Product reference.* SPLK-CL-000490 — confirmed in 10 4 2

**SRG-APP-000825-WSR-000180** — CAT II — Applicable, evidence grade C.

The web server must implement multifactor authentication for local; network; and/or remote access to privileged accounts; and/or nonprivileged accounts such that the device meets organization-defined strength of mechanism requirements.

*Basis.* The web tier carries the second factor through client certificate authentication configured in web.conf, and through the multifactor vendor configured at the splunkd authentication layer that Splunk Web uses. The requirement applies to the Splunk application.

*Citation.* web.conf.spec:120 enableCertBasedUserAuth, :151 requireClientCert, :133-143 certBasedUserAuthMethod, :144 certBasedUserAuthPivOidList; authentication.conf.spec:87 externalTwoFactorAuthVendor. Web.conf.spec declares no independent credential store, so the factor configured at the authentication layer governs web sessions.

*Mechanism.* web.conf [settings]: enableCertBasedUserAuth, requireClientCert, certBasedUserAuthMethod, certBasedUserAuthPivOidList; authentication.conf [authentication]: externalTwoFactorAuthVendor

*Assessment method.* splunk btool web list --debug for enableCertBasedUserAuth, requireClientCert and certBasedUserAuthMethod; splunk btool authentication list --debug for externalTwoFactorAuthVendor; compare the configured device class against the organization-defined strength of mechanism.

*Product reference.* SPLK-CL-000490 — confirmed in 10 4 2

**SRG-APP-000845-AU-000320** — CAT II — Applicable, evidence grade C.

The Central Log Server must for password-based authentication, verify when users create or update passwords, that the passwords are not found on the list of commonly-used, expected, or compromised passwords in IA-5 (1) (a).

*Basis.* Splunk Enterprise verifies candidate passwords at creation and change time against composition rules and against the account's own password history, so this objective has an object in the product and the requirement applies. The product exposes no deny list screening key, so the commonly used and compromised element of the objective has no implementing setting and an instance relying solely on native authentication will be assessed Other Than Satisfied on that element.

*Citation.* authentication.conf.spec:554 enablePasswordHistory, :561 passwordHistoryCount, and the minPassword* family at :441-477, each of which states that non-conforming password modification attempts are explicitly rejected. The enumeration of all 22 password-named keys across the 71 specification files returns no deny list or dictionary screening key. DISA's SPLK-CL-000410 names enablePasswordHistory and passwordHistoryCount, both present in 10.4.2, but those settings implement reuse history rather than screening against a commonly used or compromised list.

*Mechanism.* authentication.conf [splunk_auth]: enablePasswordHistory, passwordHistoryCount, minPasswordLength, minPasswordUppercase, minPasswordLowercase, minPasswordDigit, minPasswordSpecial

*Assessment method.* splunk btool authentication list --debug - examine [splunk_auth] for enablePasswordHistory, passwordHistoryCount and the minPassword* family, and [authentication] authType to establish whether native authentication is in use; where deny list screening is required, examine the external identity provider named by authType.

*Product reference.* SPLK-CL-000410 — confirmed in 10 4 2

**SRG-APP-000845-WSR-000220** — CAT II — Applicable, evidence grade C.

The web server must, for password-based authentication, verify when users create or update passwords, that the passwords are not found on the list of commonly-used, expected, or compromised passwords in IA-5 (1) (a).

*Basis.* Password creation and change for web tier accounts is processed by the splunkd authentication system, which verifies candidates against composition rules and password history, so the requirement applies through that delegation. No deny list screening key exists, so that element of the objective has no implementing setting in the product.

*Citation.* grep -c -E '^(minPassword|expirePassword|passwordHistory|passwordHash|enablePasswordHistory|forceWeakPassword)' web.conf.spec returns 0, establishing that the web tier carries no separate password verification path; the verification settings are at authentication.conf.spec:554, :561 and :441-477. The enumeration of all 22 password-named keys across the 71 specification files returns no deny list or screening key.

*Mechanism.* authentication.conf [splunk_auth]: enablePasswordHistory, passwordHistoryCount, minPasswordLength, minPasswordUppercase, minPasswordLowercase, minPasswordDigit, minPasswordSpecial

*Assessment method.* splunk btool authentication list --debug - examine [authentication] authType and [splunk_auth] for the password history and composition settings; confirm by splunk btool web list --debug that no separate web-tier credential store is configured.

*Product reference.* SPLK-CL-000410 — confirmed in 10 4 2

**SRG-APP-000850-WSR-000230** — CAT II — Applicable, evidence grade C.

The web server must, for password-based authentication, store passwords using an approved salted key derivation function, preferably using a keyed hash.

*Basis.* Splunk Enterprise stores native-authentication credentials as salted iterated hashes and the algorithm is selectable through configuration, so the requirement applies to the application. The selectable set includes MD5-crypt, which is not an approved algorithm, so the configured value is the assessable element; the product offers no keyed-hash option, and the requirement states the keyed hash as a preference rather than a mandate.

*Citation.* authentication.conf.spec:58 passwordHashAlgorithm = [SHA512-crypt|SHA256-crypt|SHA512-crypt-<num_rounds>|SHA256-crypt-<num_rounds>|MD5-crypt], described at :59-79 as controlling how hashed passwords are stored for the default Splunk authType, applying a salt over 5000 rounds of SHA-256 or SHA-512 by default with a configurable round count of at least 1000. Splunk-launch.conf.spec:110 SPLUNK_FIPS constrains the algorithms available. Key presence confirmed on a 10.4.2 instance by splunk btool authentication list --debug.

*Mechanism.* authentication.conf [authentication]: passwordHashAlgorithm

*Assessment method.* splunk btool authentication list --debug - examine [authentication] passwordHashAlgorithm and confirm a SHA-2 family value rather than MD5-crypt; splunk show fips-mode.

**SRG-APP-000860-AU-000350** — CAT II — Applicable, evidence grade C.

The Central Log Server must for password-based authentication, allow user selection of long passwords and passphrases, including spaces and all printable characters.

*Basis.* Splunk Enterprise sets a minimum password length through configuration and the specification set declares no maximum length key, so long passwords and passphrases are permitted; the requirement applies to the application. The product documents one printable character exclusion, which is the assessable element against the all printable characters element of this objective.

*Citation.* authentication.conf.spec:441 minPasswordLength = <positive integer>, specifying the minimum permitted password length when passwords are set or modified. The enumeration of all 22 declared keys containing 'password' across the 71 specification files returns no maximum length key and no character-set key. Authentication.conf.spec:480 states of minPasswordSpecial: 'The semicolon character is not allowed.'

*Mechanism.* authentication.conf [splunk_auth]: minPasswordLength

*Assessment method.* splunk btool authentication list --debug for [splunk_auth] minPasswordLength; on a test account, set a long passphrase containing spaces and printable special characters and record whether it is accepted, and confirm the documented semicolon exclusion.

**SRG-APP-000860-WSR-000250** — CAT II — Applicable, evidence grade C.

The web server must, for password-based authentication, allow user selection of long passwords and passphrases, including spaces and all printable characters.

*Basis.* Password length and character acceptance for web tier accounts is governed by the splunkd authentication system, which sets a minimum length and imposes no documented maximum, so the requirement applies through that delegation. The documented semicolon exclusion is the assessable element against the all printable characters element of this objective.

*Citation.* grep -c -E '^(minPassword|expirePassword|passwordHistory|passwordHash|enablePasswordHistory|forceWeakPassword)' web.conf.spec returns 0, so the web tier imposes no length or character rule of its own; the governing setting is authentication.conf.spec:441 minPasswordLength, with the character exclusion stated at :480.

*Mechanism.* authentication.conf [splunk_auth]: minPasswordLength

*Assessment method.* splunk btool authentication list --debug for [splunk_auth] minPasswordLength and [authentication] authType; through the web interface, set a long passphrase containing spaces and printable special characters on a test account and record whether it is accepted.

**SRG-APP-000870-WSR-000270** — CAT II — Applicable, evidence grade C.

The web server must, for password-based authentication, enforce organization-defined composition and complexity rules.

*Basis.* Splunk Enterprise enforces password composition and complexity for native authentication through a dedicated settings family, and all six settings DISA named for this objective are present in 10.4.2 under unchanged names. Where authType delegates authentication to a directory service or identity provider, composition is enforced at that provider instead, which the assessment must establish before examining these settings.

*Citation.* authentication.conf.spec:441 minPasswordLength, :450 minPasswordUppercase, :459 minPasswordLowercase, :468 minPasswordDigit, :477 minPasswordSpecial, :487 expirePasswordDays; each composition setting carries the statement that password modification attempts which do not meet the requirement are explicitly rejected. All six confirmed readable on a 10.4.2 instance by splunk btool authentication list --debug.

*Mechanism.* authentication.conf [splunk_auth]: minPasswordLength, minPasswordUppercase, minPasswordLowercase, minPasswordDigit, minPasswordSpecial, expirePasswordDays

*Assessment method.* splunk btool authentication list --debug - examine [authentication] authType to establish whether native authentication is in use, then [splunk_auth] for the six composition settings, and compare each against the organization-defined composition and complexity rules.

*Product reference.* SPLK-CL-000340, SPLK-CL-000350, SPLK-CL-000360, SPLK-CL-000370, SPLK-CL-000380, SPLK-CL-000400 — confirmed in 10 4 2

**SRG-APP-000875-AU-000380** — CAT II — Applicable, evidence grade C.

The Central Log Server must for public key-based authentication, implement a local cache of revocation data to support path discovery and validation.

*Basis.* Splunk Enterprise performs certificate status validation from revocation lists held locally on the instance in PEM form, which is the local cache this objective calls for, so the requirement applies to the application. The product declares no OCSP mechanism, so revocation checking is list-based and requires no network path to the issuer at validation time, which is the availability condition the requirement's discussion describes.

*Citation.* server.conf.spec:1125 certificateStatusValidationMethod = crl, with :1131-1133 stating that crl is the only acceptable value and that any other value turns validation off; :1139-1141 states that CRL files reside at $SPLUNK_HOME/auth/crl and must be in PEM format; :5392 sslCRLPath for the KV store channel. No declared OCSP key exists in any of the 71 specification files - the sole 'ocsp' substring in the set is incidental text inside a base64 value in livetail.conf.

*Mechanism.* server.conf [sslConfig]: certificateStatusValidationMethod; server.conf [kvstore]: sslCRLPath

*Assessment method.* splunk btool server list --debug - examine [sslConfig] certificateStatusValidationMethod and [kvstore] sslCRLPath; confirm revocation list files are present in the instance's auth/crl directory, are PEM encoded, and fall within their validity period.

**SRG-APP-000875-WSR-000280** — CAT II — Applicable, evidence grade C.

The web server must, for public key-based authentication, implement a local cache of revocation data to support path discovery and validation.

*Basis.* The certificate status validation setting states in its own scope that it covers the Splunk Web channel, and web.conf declares no revocation key, so the web tier takes the splunkd setting while supplying its own trust anchor for client certificate validation. The requirement applies to the Splunk application.

*Citation.* server.conf.spec:1129-1131 states that when certificate status validation is active it is active for any Splunk platform network communication using SSL, including the Splunk Web channel; the setting itself at :1125 certificateStatusValidationMethod = crl, with local PEM revocation files at :1139-1141. Trust anchor for client certificates at web.conf.spec:108 sslRootCAPath with :151 requireClientCert. Grep -n -i CRL web.conf.spec returns no declared revocation key in the web specification.

*Mechanism.* server.conf [sslConfig]: certificateStatusValidationMethod; web.conf [settings]: sslRootCAPath, requireClientCert

*Assessment method.* splunk btool server list --debug for [sslConfig] certificateStatusValidationMethod; splunk btool web list --debug for sslRootCAPath and requireClientCert; confirm the local revocation list files cover the certificate authorities that issue the accepted client certificates.

**SRG-APP-000880-WSR-000290** — CAT II — Applicable, evidence grade C.

The web server must protect nonlocal maintenance sessions by separating the maintenance session from other network sessions with the system by logically separated communications paths.

*Basis.* Splunk Enterprise 10.4.2 exposes its administrative and maintenance access through two listeners that are distinct from the search and data-ingestion listeners: the splunkd REST management listener and the Splunk Web administrative interface. The product permits each of these to be bound to a nominated IP address and port, to carry TLS independently of every other listener, to demand a client certificate, and to be restricted by a network access control list. Logical separation of the maintenance path by encryption, the method the requirement's own discussion names, is therefore attainable through the product's own configuration, and the requirement applies to the application. The specification set uses none of the SRG's nonlocal-maintenance vocabulary, but absence of the term is not absence of the mechanism. Where an organization elects the physically separated branch of the control instead, that path is furnished by the network baseline; the application still carries the logical-separation branch, so the requirement is not inherited away.

*Citation.* server.conf.spec:1612 [httpServerListener:<ip:><port>], documented at :1613-1616 as binding the REST listener to a specific interface, with ssl at :1624, listenOnIPv6 at :1631 and acceptFrom at :1635; server.conf.spec:724 [sslConfig] enableSplunkdSSL (TLS on the management port) and :858 requireClientCert; server.conf.spec:1291 [httpServer] with acceptFrom at :1345; web.conf.spec:35 mgmtHostPort, :70 enableSplunkWebSSL, :151 requireClientCert. Live 10.4.2 instance, read-only: btool web list --debug resolves mgmtHostPort and enableSplunkWebSSL; btool server list --debug resolves [sslConfig] enableSplunkdSSL and [httpServer] acceptFrom. Exhaustive search of all 128 specification files for the terms nonlocal, non-local, "maintenance session", out-of-band, "out of band" and "diagnostic session" returned 0 matching files for every term except non-local (2 files, unrelated usage), confirming the product names no dedicated maintenance-session construct while still exposing the separation mechanism above. Has_own_na_clause is false for this requirement, so no benchmark Not Applicable clause is available, and capability is present, so no capability-absent grade is available.

*Mechanism.* web.conf [settings]: mgmtHostPort, httpport, enableSplunkWebSSL, requireClientCert. Server.conf [sslConfig]: enableSplunkdSSL, requireClientCert. Server.conf [httpServerListener:<ip>:<port>]: ssl, listenOnIPv6, acceptFrom. Server.conf [httpServer]: acceptFrom.

*Assessment method.* Examine: run `splunk btool web list settings --debug` and `splunk btool server list --debug` against the instance and record mgmtHostPort, httpport, enableSplunkWebSSL and web.conf requireClientCert; [sslConfig] enableSplunkdSSL and requireClientCert; [httpServer] acceptFrom; and every [httpServerListener:...] stanza with its ssl and acceptFrom values. Test: confirm the administrative interface and the management REST port negotiate TLS and reject cleartext, and that the recorded acceptFrom rules admit only the administrative network. Then examine the system's network documentation to determine whether the resulting management path is separated from search and data-ingestion sessions. Record Other Than Satisfied where the management listener or the administrative web interface carries no TLS, or where it accepts connections from the same unrestricted path as non-maintenance sessions.

**SRG-APP-000910-AU-000390** — CAT II — Applicable, evidence grade C.

The Central Log Server must include only approved trust anchors in trust stores or certificate stores managed by the organization.

*Basis.* The product maintains its own trust store for the splunkd and Splunk-to-Splunk channels: a single concatenated PEM file of certificate authority certificates is named by configuration, a separate setting selects whether the instance uses that store, the operating system store, or both, and peer certificate verification and revocation checking are configurable. Restricting the store to approved anchors is therefore an application configuration action, with the caveat that selecting the operating system store moves the anchor list to the host baseline.

*Citation.* server.conf.spec:996 sslRootCAPath ("The path to the certificate authority (CA), or root certificate store... A file that contains one or more CA certificates"), 902 caTrustStore = <[splunk],[OS]>, 922 caTrustStorePath, 798 sslVerifyServerCert, 858 requireClientCert, 1125 certificateStatusValidationMethod = crl, 5392 sslCRLPath; outputs.conf.spec:691 sslRootCAPath. SslRootCAPath and caTrustStore resolve in the merged server.conf of a live 10.4.2 instance. DISA's SPLK-CL-000450 requires a DOD-approved certificate and a copy of the DOD root CA certificate in PEM format placed for Splunk use; the keys that consume those files exist in 10.4.2.

*Mechanism.* server.conf [sslConfig] sslRootCAPath, caTrustStore, caTrustStorePath, sslVerifyServerCert, certificateStatusValidationMethod, sslCRLPath; outputs.conf [tcpout:<group>] sslRootCAPath

*Assessment method.* splunk btool server list --debug and splunk btool outputs list --debug to locate sslRootCAPath and caTrustStore; then enumerate every certificate in the referenced PEM bundle with "openssl crl2pkcs7 -nocrl -certfile <bundle> | openssl pkcs7 -print_certs -noout" and compare each issuer against the organization's approved trust anchor list.

*Product reference.* SPLK-CL-000450 — confirmed in 10 4 2

**SRG-APP-000910-WSR-000300** — CAT II — Applicable, evidence grade C.

The web server must include only approved trust anchors in trust stores or certificate stores managed by the organization.

*Basis.* The browser-facing interface has its own trust anchor setting for validating client certificates, which falls back to the splunkd trust store when it is not given a value, and the trust store type selector and revocation setting apply to the Splunk Web channel as well. Restricting the anchors the web interface will trust is therefore an application configuration action.

*Citation.* web.conf.spec:108 sslRootCAPath ("The path to a root certificate authority (CA) certificate, in privacy-enhanced mail (PEM) format, that splunkd is to use to authenticate client certificates"), 151 requireClientCert; server.conf.spec:902 caTrustStore, 996 sslRootCAPath, 1125 certificateStatusValidationMethod whose text states that certificate status validation "is active for any kind of Splunk platform-related network communication that uses SSL, including the Splunk Web, splunkd, and Splunk-to-Splunk (S2S) communication channels". SslRootCAPath resolves in the merged web.conf of a live 10.4.2 instance.

*Mechanism.* web.conf [settings] sslRootCAPath, requireClientCert; server.conf [sslConfig] caTrustStore, sslRootCAPath, certificateStatusValidationMethod

*Assessment method.* splunk btool web list --debug to locate sslRootCAPath for the web channel, falling back to server.conf when unset; then print every certificate in the referenced PEM bundle with "openssl pkcs7 -print_certs -noout" and compare the issuers against the organization's approved trust anchor list.

*Product reference.* SPLK-CL-000450 — confirmed in 10 4 2

**SRG-APP-000915-AU-000400** — CAT II — Applicable, evidence grade C.

The Central Log Server must provide protected storage for cryptographic keys with organization-defined safeguards and/or hardware protected key store.

*Basis.* The product lets the location of each private key be placed under configuration control and protects the key's passphrase at rest: a passphrase entered in plain text is encrypted and rewritten by the instance on first use, and credentials written through the storage endpoint are always encrypted. No PKCS#11, HSM or TPM interface appears anywhere in the specification set, so the requirement's hardware-protected-key-store alternative is not reachable through the application and the objective is met through the organization-defined-safeguards branch, with file permissions on the key provided by the host operating system baseline.

*Citation.* server.conf.spec:971 serverCert, 989 sslPassword; inputs.conf.spec:990 serverCert and 1002-1006 sslPassword - "Configure this setting to a plain-text value initially. Upon first use, the input encrypts and rewrites the password"; passwords.conf.spec:18-23 [credential:<realm>:<username>:] - "The password can be in clear text, however when saved from splunkd the password will always be encrypted." A case-insensitive search of all 71 specification files for "pkcs11", "PKCS#11", "HSM", "TPM" and "hardware security" returned zero matches.

*Mechanism.* server.conf [sslConfig] serverCert, sslPassword, sslRootCAPath; inputs.conf [SSL] serverCert, sslPassword; passwords.conf [credential:<realm>:<username>:] encrypted credential storage

*Assessment method.* splunk btool server list --debug and splunk btool inputs list --debug to locate serverCert and sslPassword; confirm the stored sslPassword value is an encrypted string rather than plain text, and examine the ownership and mode of the key file with "stat -c '%U %G %a' <key path>" under the host operating system assessment.

*Product reference.* SPLK-CL-000450 — confirmed in 10 4 2

**SRG-APP-000915-WSR-000310** — CAT II — Applicable, evidence grade C.

The web server must provide protected storage for cryptographic keys with organization-defined safeguards and/or hardware protected key store.

*Basis.* The browser-facing interface takes its private key by a dedicated configurable path and exposes a setting for the passphrase protecting that key, so the key can be placed on storage with safeguards the organization defines and the passphrase is held by the application rather than left alongside the key in the clear. The hardware-protected-key-store alternative is not reachable through the application, as no PKCS#11, HSM or TPM interface exists in the specification set, and file permissions on the key are provided by the host operating system baseline.

*Citation.* web.conf.spec:75 privKeyPath, 82 serverCert, 93 sslPassword ("Password that protects the private key specified by 'privKeyPath'"); passwords.conf.spec:18-23 for encrypted credential storage. PrivKeyPath, serverCert and sslPassword resolve in the merged web.conf of a live 10.4.2 instance. A case-insensitive search of all 71 specification files for "pkcs11", "PKCS#11", "HSM" and "TPM" returned zero matches.

*Mechanism.* web.conf [settings] privKeyPath, serverCert, sslPassword

*Assessment method.* splunk btool web list --debug to locate privKeyPath and confirm sslPassword is stored encrypted rather than in plain text; then examine the key file's ownership and mode with "stat -c '%U %G %a' <key path>" and confirm it is readable only by the Splunk service account.

*Product reference.* SPLK-CL-000450 — confirmed in 10 4 2

**SRG-APP-000920-AU-000410** — CAT II — Applicable, evidence grade C.

The Central Log Server must synchronize system clocks within and between systems or system components.

*Basis.* That the host operating system sets the clock is accepted and the named provider is correct for that function, but the disposition is withdrawn because it records the whole objective as inherited while the requirement reads "within and between systems or system components" and the product is itself a multi-component system. The application carries a configurable share of the inter-component half: it bounds the clock difference it tolerates between a search head and a search peer, refuses to register a peer outside the configured bound, logs when the tolerance is exceeded, and at the ingest boundary reconciles the time representation of events arriving from other components, including a time zone conveyed by the forwarder. A per-host time service also cannot by itself produce agreement between components, which requires a common authoritative source designated by the organization and not named in the original provider statement; and the original search found only one of the two skew settings the specification set contains, so the basis for inheriting the entire control is incomplete.

*Citation.* limits.conf.spec:529-535 max_tolerable_skew — "Absolute value of the largest time skew, in seconds, that is tolerated between the native clock on the search head and the native clock on the peer (independent of time zone). If this time skew is exceeded, a warning is logged." Unlike addpeer_skew_limit, which the specification restricts to manually added peers at limits.conf.spec:498-499, max_tolerable_skew carries no such restriction; it was not cited in the original evidence although it lies within the same section of the same specification file. Props.conf.spec:580-611 TZ and TZ_ALIAS and props.conf.spec:613-680 MAX_DAYS_AGO, MAX_DAYS_HENCE, MAX_DIFF_SECS_AGO and MAX_DIFF_SECS_HENCE reconcile event time across components, and props.conf.spec:586-588 states the forwarder-supplied time zone is used where the forwarder-indexer connection uses the version 6.0 and higher forwarding protocol. Both skew settings resolve in the merged limits.conf of a live 10.4.2 instance. The term search is independently confirmed: "ntp", "timesync", "time synchron", "authoritative time", "time server", "chrony" and "drift" return no configuration setting across all 71 specification files.

*Mechanism.* limits.conf [search] max_tolerable_skew (limits.conf.spec:529) and addpeer_skew_limit (limits.conf.spec:493); props.conf per-host, per-source and per-sourcetype TZ (props.conf.spec:580), TZ_ALIAS (592), MAX_DAYS_AGO (613), MAX_DAYS_HENCE (629), MAX_DIFF_SECS_AGO (649) and MAX_DIFF_SECS_HENCE (668). The clock-setting function itself is inherited from the host operating system's time service, which remains the provider for that element.

*Providing baseline.* The host operating system baseline's time service, assessed under that operating system's STIG time-synchronization requirement (chronyd or ntpd on Linux, the Windows Time service on Windows); for a containerized instance, the container host, whose kernel clock the container shares.

*Assessment method.* splunk btool limits list search --debug | grep -cE 'addpeer_skew_limit|max_tolerable_skew' , then record both settings; splunk btool props list --debug | grep -cE '^(TZ|TZ_ALIAS|MAX_DAYS_|MAX_DIFF_SECS_)' ; then examine the host time service configuration and the organization's designated authoritative time source under the operating system baseline.

**SRG-APP-000920-WSR-000320** — CAT II — Applicable, evidence grade C.

The web server must synchronize system clocks within and between systems or system components.

*Basis.* The observation that web.conf holds no clock or time-source key is accurate but does not place the requirement outside the application boundary, because the SRG requirement addresses the product that operates the browser-facing interface rather than one configuration file of it, and the product-level mechanisms for clock agreement between its components are configurable within the application. The disposition is withdrawn for the same reason as its Central Log Server counterpart: the application bounds and reports the clock difference it tolerates between components and reconciles event time at the ingest boundary, so the Splunk team owns a configurable share of this objective, while the clock-setting function alone is inherited from the host operating system's time service. The original search also missed one of the two skew settings in the specification set, and a per-host time service does not by itself achieve agreement between components, which needs an organization-designated common authoritative source that the provider statement does not name.

*Citation.* limits.conf.spec:529-535 max_tolerable_skew — "Absolute value of the largest time skew, in seconds, that is tolerated between the native clock on the search head and the native clock on the peer" — was not cited in the original evidence; limits.conf.spec:493-500 addpeer_skew_limit refuses registration of a peer outside the configured bound. User-prefs.conf.spec:53-56 tz sets the per-user time zone for the interface and falls back to the time zone of the Splunk server or search head, so uniformity of displayed time between components depends on an application setting. Props.conf.spec:580-680 reconciles event time across components, including the forwarder-supplied time zone at props.conf.spec:586-588. Both skew settings resolve in the merged limits.conf of a live 10.4.2 instance, and the term search for "ntp", "timesync", "time synchron", "authoritative time", "time server", "chrony" and "drift" returns no configuration setting across all 71 specification files.

*Mechanism.* limits.conf [search] max_tolerable_skew (limits.conf.spec:529) and addpeer_skew_limit (limits.conf.spec:493); user-prefs.conf [general] tz (user-prefs.conf.spec:53); props.conf TZ (props.conf.spec:580) and the MAX_DAYS and MAX_DIFF_SECS timestamp bounds (props.conf.spec:613-680). The clock-setting function is inherited from the host operating system's time service, which remains the provider for that element.

*Providing baseline.* The host operating system baseline's time service, assessed under that operating system's STIG time-synchronization requirement (chronyd or ntpd on Linux, the Windows Time service on Windows); for a containerized instance, the container host.

*Assessment method.* splunk btool limits list search --debug | grep -cE 'addpeer_skew_limit|max_tolerable_skew' ; splunk btool web list settings --debug and splunk btool user-prefs list general --debug | grep -c '^tz' ; then examine the host time service configuration and the organization's designated authoritative time source under the operating system baseline.

**SRG-APP-000925-AU-000420** — CAT II — Applicable, evidence grade C.

The Central Log Server must compare the internal system clocks on an organization-defined frequency with organization-defined authoritative time source.

*Basis.* The finding that neither organization-defined parameter — the authoritative time source and the comparison frequency — has an application configuration surface is accepted, and the operating system's time service remains the provider for the comparison against the authoritative source. The disposition is withdrawn because the specification set does contain a clock-comparison mechanism that the original evidence did not find: a configurable tolerance for the difference between the native clock on the search head and the native clock on the peer, which logs a warning when exceeded and which the specification does not restrict to peer registration. That is a comparison of internal system clocks performed by the application against a configurable threshold, so the Splunk team owns a share of this objective and the row cannot be recorded as wholly inherited; the two skew settings must be examined on the instance and set to values the organization has approved.

*Citation.* limits.conf.spec:529-535 max_tolerable_skew — "Absolute value of the largest time skew, in seconds, that is tolerated between the native clock on the search head and the native clock on the peer (independent of time zone). If this time skew is exceeded, a warning is logged. This estimate is approximate and tries to account for network delays." The original evidence cites addpeer_skew_limit at limits.conf.spec:493-497 and authentication.conf.spec:936 assertionTimeSkew but not max_tolerable_skew, which sits thirty-six lines further into the same section of the same specification file; addpeer_skew_limit is restricted to manually added peers at limits.conf.spec:498-499 while max_tolerable_skew is not. Both resolve in the merged limits.conf of a live 10.4.2 instance. The term search for "ntp", "timesync", "time synchron", "authoritative time" and "time server" is independently confirmed to return no configuration setting across all 71 specification files.

*Mechanism.* limits.conf [search] max_tolerable_skew (limits.conf.spec:529) and addpeer_skew_limit (limits.conf.spec:493). The organization-defined authoritative time source and the polling interval against it have no application configuration surface and are provided by the host operating system's time service.

*Providing baseline.* The host operating system baseline's time service, which polls the organization-defined authoritative source at its configured interval and is assessed under that operating system's STIG; for a containerized instance, the container host.

*Assessment method.* splunk btool limits list search --debug | grep -cE 'addpeer_skew_limit|max_tolerable_skew' , then record both settings and compare them against the organization-defined tolerance; then obtain the authoritative time source and the comparison interval from the host operating system's time service configuration under that baseline.

**SRG-APP-000925-WSR-000330** — CAT II — Applicable, evidence grade C.

The web server must compare the internal system clocks on an organization-defined frequency with organization-defined authoritative time source.

*Basis.* That web.conf carries no clock or time-source key is accurate, and the operating system's time service remains the provider for the comparison against the organization-defined authoritative source at the organization-defined frequency. The disposition is withdrawn because the claim that "the application performs no comparison of its clock against an authoritative source" was supported by a search that missed the one setting in the specification set that compares internal system clocks on a configurable tolerance and logs on exceedance, and because the requirement addresses the product operating the browser-facing interface rather than one of its configuration files. The application therefore owns a configurable share of the comparison objective and the row cannot be recorded as wholly inherited.

*Citation.* limits.conf.spec:529-535 max_tolerable_skew compares "the native clock on the search head and the native clock on the peer" and logs a warning when the configured tolerance is exceeded; the original evidence cites only limits.conf.spec:493 addpeer_skew_limit, which the specification restricts to manually added peers at limits.conf.spec:498-499. Both settings resolve in the merged limits.conf of a live 10.4.2 instance. The term search for "ntp", "timesync", "time synchron", "authoritative time" and "time server" is independently confirmed to return no configuration setting across all 71 specification files, and web.conf.spec is confirmed to carry no clock or time-source key.

*Mechanism.* limits.conf [search] max_tolerable_skew (limits.conf.spec:529) and addpeer_skew_limit (limits.conf.spec:493). The authoritative time source and the comparison frequency have no application configuration surface and are provided by the host operating system's time service.

*Providing baseline.* The host operating system baseline's time service, which performs the comparison against the organization-defined authoritative source at its configured frequency and is assessed under that operating system's STIG; for a containerized instance, the container host.

*Assessment method.* splunk btool limits list search --debug | grep -cE 'addpeer_skew_limit|max_tolerable_skew' , then record both settings and compare them against the organization-defined tolerance; then obtain the authoritative time source and the comparison interval from the host operating system's time service configuration under that baseline.

**SRG-APP-000068-AU-000035** — CAT III — Applicable, evidence grade C.

The Central Log Server must display the Standard Mandatory DoW Notice and Consent Banner before granting access to the Central Log Server.

*Basis.* Splunk Web exposes a setting that places custom content on the login page, which is the interface at which a human user is granted access, so the product provides a mechanism for presenting the notice before access is granted. The 10.4.2 specification adds that this setting sanitizes HTML by removing potentially dangerous tags and attributes, which means the script-driven modal the sunsetted product STIG prescribes is not a viable implementation on this version even though the setting it names still exists.

*Citation.* web.conf.spec:233-237 login_content - "Lets you add custom content to the login page. Supports any text including HTML. The Splunk platform sanitizes HTML for security purposes by removing potentially dangerous tags and attributes." The sunsetted SPLK-CL-000080 fix text sets login_content to a <script> block invoking alert(). The only other login-page settings in the specification set are cosmetic: web.conf.spec:1335 loginCustomLogo, :1348 loginBackgroundImageOption, :1355 loginCustomBackgroundImage. Global-banner.conf.spec:26-43 provides a post-authentication banner above the Splunk bar and does not act before access is granted.

*Mechanism.* web.conf [settings] login_content

*Assessment method.* Run as the Splunk service account: splunk btool web list --debug | grep login_content to resolve the configured value and its layer. Then test the rendered result, because the sanitizer acts at render time and not at configuration time: request the Splunk Web login page unauthenticated and examine the returned document for the DoW notice text, for example curl -sk https://<splunk-web-host>:<web-port>/en-US/account/login. Compare the rendered wording against DTM-08-060. Per SPLK-CL-000080 this applies to the instance serving the search head role, which may be a separate instance in a distributed deployment.

*Product reference.* SPLK-CL-000080 — confirmed in 10 4 2

**SRG-APP-000069-AU-000420** — CAT III — Applicable, evidence grade C.

The Central Log Server must retain the Standard Mandatory DoW Notice and Consent Banner on the screen until users acknowledge the usage conditions and take explicit actions to log on for further access.

*Basis.* The same login page setting renders the notice persistently on the login page, where it remains until the user submits credentials, which is the explicit action to log on that this requirement describes. Splunk Enterprise exposes no separate acknowledgement control, and because login_content strips dangerous tags the click-through modal that would force a positive OK action cannot be built from the product's configuration surface, so an assessment applying the strict click-through reading of AC-8 b should expect Other Than Satisfied.

*Citation.* web.conf.spec:233-237 login_content, with the sanitization clause "The Splunk platform sanitizes HTML for security purposes by removing potentially dangerous tags and attributes"; a search of all 71 specification files for an acknowledgement or click-through control returned no login-related result (grep -iE 'consent|acknowled|click.?through|splash' over *.spec: hits only in federated.conf.spec:113-115 needs_consent, which concerns federated search definitions, and the indexer acknowledgment settings in inputs.conf.spec, indexes.conf.spec and outputs.conf.spec).

*Mechanism.* web.conf [settings] login_content

*Assessment method.* Run as the Splunk service account: splunk btool web list --debug | grep login_content, then test the rendered login page unauthenticated, for example curl -sk https://<splunk-web-host>:<web-port>/en-US/account/login, and examine whether the notice remains displayed through the point of credential submission and whether any positive acknowledgement control is presented. Record the result against the site's stated interpretation of AC-8 b.

**SRG-APP-000086-AU-000020** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to aggregate log records from organization-defined devices and hosts within its scope of coverage.

*Basis.* Splunk Enterprise aggregates records from other hosts through its own receiving input stanzas, and sending instances are pointed at the aggregation tier through outputs.conf. The scope-of-coverage list against which the configuration is compared is an organizational artifact, but the aggregation itself is product configuration.

*Citation.* inputs.conf.spec:630 '[splunktcp]', :774 '[splunktcp://[<remote server>]:<port>]', :1233 '[udp://<remote server>:<port>]', :239 '[monitor://<path>]', :1652 '[http]' (HTTP Event Collector). Outputs.conf.spec:61 '[tcpout]', :63 'defaultGroup = <comma-separated list>', :123 'server = <comma-separated list>'. SPLK-CL-000110's fix text names outputs.conf on forwarders and inputs.conf on indexers; both files and both stanza families exist in 10.4.2. Confirmed readable on the live instance via btool inputs list --debug and btool outputs list --debug.

*Mechanism.* inputs.conf receiving stanzas [splunktcp], [splunktcp://[<remote server>]:<port>], [udp://<remote server>:<port>], [monitor://<path>], [http]; outputs.conf [tcpout] defaultGroup and [tcpout:<target_group>] server on sending instances

*Assessment method.* splunk btool inputs list --debug and splunk btool outputs list --debug on each instance in scope; enumerate hosts actually reporting with the search '| metadata type=hosts index=*' and reconcile that list against the documented scope of coverage.

*Product reference.* SPLK-CL-000100, SPLK-CL-000110 — confirmed in 10 4 2

**SRG-APP-000086-AU-000030** — CAT III — Applicable, evidence grade C.

Time stamps recorded on the log records in the Central Log Server must be configured to synchronize to within one second of the host server or, if NTP is configured directly in the log server, the NTP time source must be the same as the host and devices within its scope of coverage.

*Basis.* The requirement is disjunctive, not conditional on an NTP client: the title reads "must be configured to synchronize to within one second of the host server or, if NTP is configured directly in the log server, the NTP time source must be the same as the host." The prior assessor established only that the second disjunct's precondition is unmet, and no mechanism for it exists; that search reproduces and is correct as far as it goes. The first disjunct carries no precondition, and Splunk Enterprise 10.4.2 exposes the configuration that governs it. Props.conf carries a dedicated timestamp extraction section whose keys select which clock supplies the time stamp recorded on a log record and whether it agrees with the host server's clock: DATETIME_CONFIG chooses between the host's current system time, the input layer's time (the forwarder's clock for Splunk-to-Splunk traffic, the file modification time for monitor and batch inputs) and the text extractor, and TZ overrides, per source type, the time zone the product otherwise takes from the system running splunkd. A per-source-type TZ or TZ_ALIAS override displaces recorded time stamps by whole hours from the host server while the host's own time service remains synchronized, which is the precise divergence the requirement is written against. The MAX_DAYS_AGO, MAX_DAYS_HENCE, MAX_DIFF_SECS_AGO and MAX_DIFF_SECS_HENCE keys bound acceptable divergence and rewrite out-of-bound time stamps, indexes.conf quarantinePastSecs and quarantineFutureSecs bound how far an event's time stamp may sit from the current time before the indexer diverts it, and limits.conf max_tolerable_skew and addpeer_skew_limit are in-application clock-skew bounds between a search head and a search peer that log a warning and refuse the peer respectively. Grade D is therefore not reachable: the host operating system's time service is a supporting dependency assessed under the applicable operating system STIG, but the product's own configuration determines whether the time stamps it records agree with that clock, so the control is not implemented wholly by another baseline. The requirement discussion's note scopes NTP configuration out to the host operating system and network device management STIGs; it does not scope out the time stamps the log server records. As written, OUTSIDE_BOUNDARY would represent to the Authorizing Official that the Splunk administrator owes nothing on this requirement, and the configuration surface contradicts that.

*Citation.* Timestamp extraction section header at props.conf.spec:499, with DATETIME_CONFIG at props.conf.spec:502 ("'CURRENT' to assign the current system time to each event"; "'NONE' leaves the event time set to whatever time was selected by the input layer"), TIME_PREFIX at :529, MAX_TIMESTAMP_LOOKAHEAD at :540, TIME_FORMAT at :554, DETERMINE_TIMESTAMP_DATE_WITH_SYSTEM_TIME at :566, TZ at :580 with the fallback stated at :589 ("Otherwise, use the timezone of the system that is running splunkd"), TZ_ALIAS at :592, MAX_DAYS_AGO at :613, MAX_DAYS_HENCE at :629, MAX_DIFF_SECS_AGO at :649, MAX_DIFF_SECS_HENCE at :668; all stanza-scoped to props.conf [<spec>] (props.conf.spec:80). QuarantinePastSecs at indexes.conf.spec:1056 and quarantineFutureSecs at :1066, both within the per-index options section beginning at indexes.conf.spec:382. Max_tolerable_skew at limits.conf.spec:529 and addpeer_skew_limit at limits.conf.spec:493, both under limits.conf [search] (limits.conf.spec:315). Cross-host time correlation through the forwarding protocol at props.conf.spec:586-588 ("If the event was forwarded, and the forwarder-indexer connection uses the version 6.0 and higher forwarding protocol, use the timezone provided by the forwarder"). Each key confirmed present and readable in the effective configuration of a live Splunk 10.4.2 instance (build 33c3bf42cd73) by 'splunk btool props list --debug', 'splunk btool indexes list --debug' and 'splunk btool limits list --debug' run as the splunk service account; counted occurrences rather than value readings, and no value is recorded here. The prior row's NTP search reproduces: case-insensitive '\bntp\b' across all 71 .spec files and across all 128 files of the specification set returns exactly one hit, a syslog facility enumeration, but it is at outputs.conf.spec:1127, not the cited :1140, which reads "0 Emergency: system is unusable" - a citation defect in a row offered at grade D.

*Mechanism.* props.conf [<spec>] DATETIME_CONFIG, TZ, TZ_ALIAS, TIME_PREFIX, TIME_FORMAT, MAX_TIMESTAMP_LOOKAHEAD, DETERMINE_TIMESTAMP_DATE_WITH_SYSTEM_TIME, MAX_DAYS_AGO, MAX_DAYS_HENCE, MAX_DIFF_SECS_AGO, MAX_DIFF_SECS_HENCE; indexes.conf per-index stanza quarantinePastSecs, quarantineFutureSecs; limits.conf [search] max_tolerable_skew, addpeer_skew_limit

*Providing baseline.* Host operating system time synchronization service (chronyd or ntpd), assessed under the applicable operating system STIG. Where Splunk runs in a container, the container shares the host kernel clock and there is no separate in-container time service, so the providing baseline is the container host's operating system.

*Assessment method.* Run as the splunk service account, never as root. (1) 'splunk btool props list --debug' and examine DATETIME_CONFIG, TZ, TZ_ALIAS, TIME_PREFIX, TIME_FORMAT, MAX_DAYS_AGO, MAX_DAYS_HENCE, MAX_DIFF_SECS_AGO and MAX_DIFF_SECS_HENCE for each source type in the scope of coverage, confirming no per-source-type time zone override displaces recorded time stamps from the host server's clock. (2) 'splunk btool indexes list --debug' and examine quarantinePastSecs and quarantineFutureSecs per index. (3) 'splunk btool limits list --debug' and examine max_tolerable_skew and addpeer_skew_limit. (4) Test the recorded receipt time against the host clock with a search over a recent window: 'index=* earliest=-5m | eval skew_secs=abs(_indextime-now()) | stats max(skew_secs) by host, sourcetype', and separately compare _time to _indextime: 'index=* earliest=-5m | eval parse_delta=abs(_time-_indextime) | stats max(parse_delta) by sourcetype'. (5) Compare the host clock reading from the operating system time service against the same reference the forwarding hosts use. Other Than Satisfied where any source type's recorded time stamps differ from the host server's clock by more than one second for reasons attributable to product configuration.

*Product reference.* SPLK-CL-000100, SPLK-CL-000110 — confirmed in 10 4 2

**SRG-APP-000090-AU-000070** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to allow only the Information System Security Manager (ISSM) (or individuals or roles appointed by the ISSM) to select which auditable events are to be retained.

*Basis.* Splunk Enterprise restricts who may change which events are collected and retained through its role and capability model, and binds those roles to directory groups through authentication.conf role mapping. The identification of the ISSM and the individuals the ISSM appoints is an organizational input against which the role roster is compared; the restriction itself is enforced by configuration.

*Citation.* authorize.conf.spec:55 '[capability::<capability>]', :69 '[role_<roleName>]', :76 '<capability> = enabled'; the capabilities that govern event selection and retention are :693 '[capability::edit_monitor]' / 'Lets a user add inputs and edit settings for monitoring files', :823 '[capability::edit_tcp]' / 'Lets a user change settings for receiving general TCP inputs', :651 '[capability::edit_forwarders]', :880 '[capability::indexes_edit]' / 'Lets a user change any index settings', :578 '[capability::change_audit]' / 'Lets a user change audit settings through the audit endpoints'. Authentication.conf.spec:353 '[roleMap_<authSettings-key>]' and :1347 '[roleMap_<saml-authSettings-key>]' bind a directory or assertion group to a role. Confirmed readable on the live instance via btool authorize list --debug.

*Mechanism.* authorize.conf [role_<roleName>] with <capability> = enabled, restricting edit_monitor, edit_tcp, edit_forwarders, indexes_edit and change_audit; authentication.conf [roleMap_<authSettings-key>] and [roleMap_<saml-authSettings-key>]

*Assessment method.* splunk btool authorize list --debug and enumerate every role holding edit_monitor, edit_tcp, edit_forwarders, indexes_edit or change_audit; splunk btool authentication list --debug for the group-to-role mappings; list members with the REST endpoint /services/authentication/users and compare the resulting roster against the ISSM's written appointment of authorized individuals. SPLK-CL-000140's fix text is procedural and names no configuration key; it also covers only LDAP group mapping, so a SAML deployment requires the [roleMap_<saml-authSettings-key>] stanza to be examined as well.

*Product reference.* SPLK-CL-000140 — confirmed in 10 4 2

**SRG-APP-000092-AU-000670** — CAT III — Applicable, evidence grade C.

The Central Log Server must initiate session auditing upon startup.

*Basis.* The splunkd audit trail is produced by the process itself rather than by a separately started auditing service, and no configuration key was found that defers or delays its start; what is configurable, and therefore what this requirement turns on, is whether audit events reach an index and which REST actions are audited, both of which can suppress records generated during startup.

*Citation.* audit.conf.spec:28-34 '[auditTrail]' / 'queueing = <boolean>' / 'Whether or not audit events are sent to the indexQueue' / 'If set to "false", you must add an inputs.conf stanza to tail the audit log for the events reach your index'; :36-45 'logging_format = v1|v2|both'; :47-62 '[auditconfig:/path]' with 'enabled = <comma-separated list>' and 'disabled = <comma-separated list>', where 'A value of "all" deactivates logging for every action in the stanza'. A search of all 71 live 10.4.2 specification files found no setting that defers the start of auditing. The live instance exposes three [auditconfig:...] stanzas carrying 'disabled = all', confirming the suppression mechanism is real and reachable.

*Mechanism.* audit.conf [auditTrail] queueing and logging_format; audit.conf [auditconfig:/path] enabled / disabled; inputs.conf [monitor://<path>] where queueing is set to false and the audit log must be tailed instead

*Assessment method.* splunk btool audit list --debug and record queueing, logging_format and every [auditconfig:<path>] suppression; splunk btool inputs list --debug where queueing is false. Then, during an approved maintenance window, restart the instance and confirm that 'index=_audit' holds records bearing timestamps at or before the first splunkd startup-complete message in splunkd.log, and that audit.log is written from process start.

**SRG-APP-000095-AU-000050** — CAT III — Applicable, evidence grade C.

The System Administrator (SA) and Information System Security Manager (ISSM) must configure the retention of the log records based on criticality level, event type, and/or retention period, at a minimum.

*Basis.* Retention is set per index in indexes.conf, routing by criticality or event type into separate indexes is done with props.conf and transforms.conf, and the privilege to change those index settings is granted through a named role capability. The documented retention schedule and the designation of the SA and ISSM are organizational inputs against which the configuration is compared.

*Citation.* indexes.conf.spec:761 'frozenTimePeriodInSecs = <nonnegative integer>', :687 'maxTotalDataSizeMB', :790 'coldToFrozenScript', :892 'coldToFrozenDir' (what happens at freeze); authorize.conf.spec:880 '[capability::indexes_edit]' / 'Lets a user change any index settings such as file size and memory limits', with :69 '[role_<roleName>]' and :76 '<capability> = enabled' granting it; props.conf.spec:1131 'TRANSFORMS-<class>' routes records to a destination index by criticality or event type. SPLK-CL-000120's fix text names indexes.conf frozenTimePeriodInSecs, which exists in 10.4.2 at indexes.conf.spec:761. Confirmed readable on the live instance via btool indexes list --debug and btool authorize list --debug.

*Mechanism.* indexes.conf per-index frozenTimePeriodInSecs, maxTotalDataSizeMB, coldToFrozenDir / coldToFrozenScript; authorize.conf [role_<roleName>] granting indexes_edit; props.conf TRANSFORMS-<class> with transforms.conf for index routing

*Assessment method.* splunk btool indexes list --debug and read frozenTimePeriodInSecs for every index in scope, then compare against the documented retention period for the hosts and devices feeding that index; splunk btool authorize list --debug to enumerate the roles holding indexes_edit and confirm they correspond to the designated SA and ISSM. SPLK-CL-000120 scopes its check to the indexer role.

*Product reference.* SPLK-CL-000120 — confirmed in 10 4 2

**SRG-APP-000095-AU-000680** — CAT III — Applicable, evidence grade C.

The Central Log Server must produce audit records containing information to establish what type of events occurred.

*Basis.* For the product's own records, the audit trail format carries the action performed and is selectable in audit.conf, and per-path audit suppression can remove actions from the record. For records received from hosts and devices, event type is derived at index time or search time through props.conf extraction and eventtypes.conf classification.

*Citation.* audit.conf.spec:36-45 'logging_format = v1|v2|both' / 'A value of "v2" means Splunk software sends audit events in a new JSONL format with enriched metadata'; :47-62 '[auditconfig:/path]' enabled / disabled, which select the audit actions logged per REST resource. Props.conf.spec:1190 'EXTRACT-<class>', :1173 'REPORT-<class>', :1401 'EVAL-<fieldname>'; eventtypes.conf.spec:51 'search = <string>'; inputs.conf.spec:113 'sourcetype = <string>'. Confirmed readable on the live instance via btool audit list --debug, which shows logging_format and three [auditconfig:...] stanzas.

*Mechanism.* audit.conf [auditTrail] logging_format and [auditconfig:/path] enabled / disabled; props.conf EXTRACT-<class>, REPORT-<class>, EVAL-<fieldname>; eventtypes.conf [<eventtype>] search; inputs.conf sourcetype

*Assessment method.* splunk btool audit list --debug for logging_format and any [auditconfig:<path>] suppression; then run 'index=_audit | stats count by action' and confirm the action field is populated and spans the expected action set. For received records, run '| tstats count by sourcetype' and sample each sourcetype to confirm an event-type attribute is present.

**SRG-APP-000096-AU-000690** — CAT III — Applicable, evidence grade C.

The Central Log Server must produce audit records containing information to establish when (date and time) the events occurred.

*Basis.* Splunk Enterprise assigns an event time to every record through per-sourcetype timestamp settings in props.conf and stamps an independent receipt time at index time, and the audit record format carries its own timestamp metadata. Timestamp recognition is therefore product configuration for each sourcetype in scope.

*Citation.* props.conf.spec:506 'DATETIME_CONFIG = [<filename relative to $SPLUNK_HOME> | CURRENT | NONE]', :533 'TIME_PREFIX = <regular expression>', :544 'MAX_TIMESTAMP_LOOKAHEAD = <integer>', :558 'TIME_FORMAT = <strptime-style format>', :584 'TZ = <timezone identifier>'. Audit.conf.spec:36 'logging_format = v1|v2|both', the v2 format carrying 'enriched metadata'. Confirmed readable on the live instance: btool props list --debug returns 41 lines carrying TIME_FORMAT or TZ.

*Mechanism.* props.conf per-sourcetype DATETIME_CONFIG, TIME_PREFIX, MAX_TIMESTAMP_LOOKAHEAD, TIME_FORMAT, TZ; the index-time _indextime attribute; audit.conf logging_format

*Assessment method.* splunk btool props list --debug and read the timestamp keys for every sourcetype in scope, noting any sourcetype falling back to DATETIME_CONFIG = CURRENT, which substitutes receipt time for event time; then run 'index=* | eval skew=_indextime-_time | stats max(skew) by sourcetype' to detect sourcetypes whose event time is not being recognized.

**SRG-APP-000097-AU-000700** — CAT III — Applicable, evidence grade C.

The Central Log Server must produce audit records containing information to establish where the events occurred.

*Basis.* Splunk Enterprise records where an event originated through the indexed host, source, sourcetype and splunk_server attributes, each of which is assignable or rewritable through its own configuration. The determination is that these mechanisms exist in the product.

*Citation.* inputs.conf.spec:60 'host = <string>', :93 'index = <string>', :113 'sourcetype = <string>', :248 'host_regex = <regular expression>', :260 'host_segment = <integer>'; props.conf.spec:1131 'TRANSFORMS-<class>' with transforms.conf for host and source rewriting. For the product's own records, audit.conf.spec:36 'logging_format = v1|v2|both' selects the enriched v2 format carrying component metadata. Confirmed readable on the live instance via btool inputs list --debug and btool props list --debug.

*Mechanism.* inputs.conf per-stanza host, index, sourcetype, host_regex, host_segment; props.conf TRANSFORMS-<class> with transforms.conf for host and source rewriting; audit.conf logging_format for the product's own component attribution

*Assessment method.* splunk btool inputs list --debug and read host, host_regex, host_segment, source and sourcetype assignment per input; splunk btool props list --debug and btool transforms list --debug for host or source rewriting; then run '| tstats count by host, source, sourcetype' and confirm the values identify a real originating component rather than a default or placeholder.

**SRG-APP-000098-AU-000710** — CAT III — Applicable, evidence grade C.

The Central Log Server must produce audit records containing information to establish the source of the events.

*Basis.* Splunk Enterprise determines the source attributed to a received record through the connection_host setting on each receiving input, and through explicit host assignment or extraction; for HTTP Event Collector data it can additionally take the source from a forwarded-for header. The determination is that the product exposes these mechanisms.

*Citation.* inputs.conf.spec:530, :615, :783, :849, :893, :1250 and :1326 'connection_host = [ip|dns|none]' on the TCP, splunktcp and UDP receiving stanzas, with :531-534 '"ip" sets the host to the IP address of the system sending the data' and '"dns" sets the host to the reverse DNS entry'; :2207 'connection_host = [ip|dns|proxied_ip|none]' on the HTTP Event Collector stanza, with :2213 '"proxied_ip" checks whether an X-Forwarded-For header was sent (presumably by a proxy server) and if so, sets the host to that value'. Also inputs.conf.spec:60 'host', :248 'host_regex', :260 'host_segment'. Confirmed readable on the live instance via btool inputs list --debug.

*Mechanism.* inputs.conf per-input connection_host (ip, dns, none; and proxied_ip on the HTTP Event Collector stanza), host, host_regex, host_segment; transforms.conf with props.conf TRANSFORMS-<class> for host extraction from relayed syslog

*Assessment method.* splunk btool inputs list --debug and read connection_host and host assignment for every receiving input; then run '| tstats count by host' and confirm each value resolves to the originating device or host rather than to a relay, syslog concentrator or load balancer.

**SRG-APP-000099-AU-000720** — CAT III — Applicable, evidence grade C.

The Central Log Server must produce audit records that contain information to establish the outcome of the events.

*Basis.* The product's audit records carry the action taken and its result, and the audit format and the set of audited actions are both selectable in audit.conf; for records received from hosts and devices, a success or failure attribute is derived through props.conf extraction or eventtypes.conf classification.

*Citation.* audit.conf.spec:36-45 'logging_format = v1|v2|both', where v2 is 'a new JSONL format with enriched metadata'; :47-62 '[auditconfig:/path]' with 'enabled = <comma-separated list>' / 'Lists the audit actions that the system explicitly logs for the Representational State Transfer (REST) resource' and 'disabled = <comma-separated list>', noting 'Protected actions such as delete always remain logged even if the setting omits them'. Props.conf.spec:1190 'EXTRACT-<class>', :1401 'EVAL-<fieldname>'; eventtypes.conf.spec:51 'search = <string>'. Confirmed readable on the live instance via btool audit list --debug.

*Mechanism.* audit.conf [auditTrail] logging_format and [auditconfig:/path] enabled / disabled; props.conf EXTRACT-<class> and EVAL-<fieldname>; eventtypes.conf [<eventtype>] search

*Assessment method.* splunk btool audit list --debug for logging_format and every [auditconfig:<path>] suppression; then run 'index=_audit | stats count by action, info' and confirm an outcome attribute is populated for the audited actions. For received records, sample each sourcetype in scope and confirm a success or failure attribute is extracted.

**SRG-APP-000100-AU-000730** — CAT III — Applicable, evidence grade C.

The Central Log Server must generate audit records containing information that establishes the identity of any individual or process associated with the event.

*Basis.* The product's audit records carry the authenticated user, and the configuration binds each record to a named individual rather than a shared account through role mapping; for scheduled work the identity a search runs as is itself a configuration choice. For records received from hosts and devices, the user attribute is normalized through props.conf.

*Citation.* audit.conf.spec:28-29 '[auditTrail]' / 'queueing' and :36 'logging_format = v1|v2|both' (the v2 format carrying 'enriched metadata'). Authorize.conf.spec:69 '[role_<roleName>]' and authentication.conf.spec:353 '[roleMap_<authSettings-key>]' / :1347 '[roleMap_<saml-authSettings-key>]' bind an external identity to a role. Savedsearches.conf.spec:55 'dispatchAs = [user|owner]' and limits.conf.spec:891 'force_saved_search_dispatch_as_user' determine the identity a scheduled search is attributed to. Props.conf.spec:1190 'EXTRACT-<class>' and :1353 'FIELDALIAS-<class>' normalize the user attribute on received records. Note: the capability edit_dispatch_as, present in the supplied specification set at authorize.conf.spec:500, is absent from the 10.4.2 specification set and from the live instance's default authorize.conf, so it must not be cited as the mechanism.

*Mechanism.* audit.conf [auditTrail] queueing and logging_format; authorize.conf [role_<roleName>] with authentication.conf [roleMap_<authSettings-key>] and [roleMap_<saml-authSettings-key>]; savedsearches.conf dispatchAs with limits.conf force_saved_search_dispatch_as_user; props.conf EXTRACT-<class> and FIELDALIAS-<class>

*Assessment method.* Run 'index=_audit | stats count by user' and confirm the user attribute is populated and resolves to named individuals rather than a shared or service account; splunk btool savedsearches list --debug and btool limits list --debug for dispatchAs and force_saved_search_dispatch_as_user; splunk btool authentication list --debug for the role mappings that bind external identities to roles.

**SRG-APP-000111-AU-000150** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to perform analysis of log records across multiple devices and hosts in the enclave that can be reviewed by authorized individuals.

*Basis.* Splunk Enterprise performs analysis across records from many devices and hosts in a single result set by federating search across its indexing peers, and bounds what each role may review through per-role index scoping. The determination is that the product implements both the cross-host analysis and the review restriction through its own configuration.

*Citation.* distsearch.conf.spec:29 '[distributedSearch]' with :81 'servers = <comma-separated list>', and :779 '[distributedSearch:<splunk-server-group-name>]' with :783 'servers = <comma-separated list>'. Authorize.conf.spec:357 'srchIndexesDefault = <semicolon-separated list>' / 'A list of indexes to search when no index is specified', :367 'srchIndexesAllowed = <semicolon-separated list>' / 'A list of indexes that this role is allowed to search', :372 'srchIndexesDisallowed'. Savedsearches.conf.spec:44 'search = <string>' and datamodels.conf.spec for the analysis itself; federated.conf.spec is present in the 10.4.2 set for cross-deployment search. Confirmed readable on the live instance via btool distsearch list --debug and btool authorize list --debug, which returns 20 srchIndexesAllowed entries.

*Mechanism.* distsearch.conf [distributedSearch] servers and [distributedSearch:<splunk-server-group-name>] servers; authorize.conf per-role srchIndexesAllowed, srchIndexesDefault, srchIndexesDisallowed; savedsearches.conf search and datamodels.conf; federated.conf for cross-deployment search

*Assessment method.* splunk btool distsearch list --debug and the REST endpoint /services/search/distributed/peers to confirm the search tier reaches every indexer in scope; run '| tstats count by host, splunk_server' and confirm records from multiple devices and hosts return in one result set; splunk btool authorize list --debug and read srchIndexesAllowed, srchIndexesDefault and srchIndexesDisallowed per role to confirm the authorized reviewers can reach the indexes they are responsible for.

**SRG-APP-000115-AU-000160** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to perform on-demand filtering of the log records for events of interest based on organization-defined criteria.

*Basis.* Splunk Enterprise filters indexed records on demand through its search language, and the organization's criteria are expressible as named, reusable configuration objects; per-role index scoping bounds what a given reviewer can filter across. The set of criteria is organizationally defined, but the filtering capability and the named objects that carry the criteria are product configuration.

*Citation.* savedsearches.conf.spec:44 'search = <string>' with :92 'cron_schedule' and :284 'counttype'; eventtypes.conf.spec:51 'search = <string>' (named classification criteria); macros.conf.spec:52 'definition = <string>' (reusable filter fragments); tags.conf.spec and fields.conf.spec for attribute-based selection; transforms.conf.spec for lookups that enrich the filter criteria; field_filters.conf.spec:32 '[<fieldFilterName>]' with :86 'index'. Authorize.conf.spec:367 'srchIndexesAllowed' bounds the scope. Confirmed readable on the live instance via btool savedsearches list --debug (41,247 lines) and btool authorize list --debug.

*Mechanism.* savedsearches.conf [<stanza name>] search and counttype; eventtypes.conf [<eventtype>] search; macros.conf [<stanza name>] definition; tags.conf and fields.conf for attribute-based selection; transforms.conf lookups; authorize.conf srchIndexesAllowed for scope

*Assessment method.* splunk btool savedsearches list --debug, btool eventtypes list --debug and btool macros list --debug to enumerate the named criteria in place, and the REST endpoint /services/saved/searches to list them as the product sees them; then execute an ad hoc search filtering on each organizationally defined criterion (identity, event type, location, time, address, resource) and confirm it returns a correctly narrowed result set for a role holding only the intended srchIndexesAllowed scope.

**SRG-APP-000116-AU-000270** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to use internal system clocks to generate time stamps for log records.

*Basis.* Splunk assigns a time stamp to every indexed record and exposes, per source type, whether that time stamp is parsed from the event text or taken from the host clock reading at index time. The clock itself is a host operating system service, but the selection of that clock as the time source is a product setting, so the assessment objective applies to the application.

*Citation.* props.conf.spec:502 DATETIME_CONFIG = [<filename> | CURRENT | NONE], where the CURRENT value assigns the current system time to each event; props.conf.spec:554 TIME_FORMAT; props.conf.spec:580 TZ. Confirmed readable on a Splunk 10.4.2 instance (build 33c3bf42cd73) with btool props list default --debug.

*Mechanism.* props.conf [<source type>] DATETIME_CONFIG (value CURRENT), with TIME_FORMAT and TZ governing normalization of a parsed time

*Assessment method.* Run `splunk btool props list --debug` as the Splunk service account and record DATETIME_CONFIG, TIME_FORMAT and TZ for every source type carrying audit data; then index a test event and compare its _time against the host clock reading taken at the same moment.

**SRG-APP-000125-AU-000300** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to back up the log records repository at least every seven days onto a different system or system component other than the system or component being audited.

*Basis.* Splunk exposes native capability to place copies of indexed log records on storage and on system components other than the indexer holding the primary copy, which is the condition the requirement's discussion sets for applicability to an application. Periodicity is a property of how the chosen mechanism is scheduled rather than a separate setting.

*Citation.* indexes.conf.spec:543 remotePath (root path for a remote volume), :792 coldToFrozenDir, :713 coldToFrozenScript, :643 maxGlobalDataSizeMB, :625 maxGlobalRawDataSizeMB; server.conf.spec:2430 [clustering] with replication_factor at :2929. The referenced product STIG rule is interview-based and names no configuration setting, directing operating system or third-party backup tools instead.

*Mechanism.* indexes.conf remotePath, coldToFrozenDir, coldToFrozenScript and maxGlobalDataSizeMB; server.conf [clustering] replication_factor

*Assessment method.* Run `splunk btool indexes list --debug` and record remotePath, coldToFrozenDir and coldToFrozenScript for every index holding log records, and `splunk btool server list clustering --debug` for replication_factor; pair with the recorded backup or archive schedule and confirm the destination is a different system or component.

*Product reference.* SPLK-CL-000250 — no reference

**SRG-APP-000166-AU-002490** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to enforce password complexity by requiring that at least one uppercase character be used.

*Basis.* Splunk native authentication exposes a minimum count of uppercase characters that rejects non-conforming password modification attempts, so the requirement is reachable through application configuration. The setting governs Splunk native accounts only.

*Citation.* authentication.conf.spec:450 (minPasswordUppercase = <positive integer>, "Password modification attempts which do not meet this requirement are explicitly rejected", default 0); key confirmed resolvable on a live 10.4.2 instance via btool authentication list splunk_auth

*Mechanism.* authentication.conf [splunk_auth] minPasswordUppercase

*Assessment method.* splunk btool authentication list splunk_auth --debug (run as the Splunk service account) and read minPasswordUppercase; then attempt to set an all-lowercase password on a native test account and confirm rejection.

*Product reference.* SPLK-CL-000340, SPLK-CL-000350, SPLK-CL-000360, SPLK-CL-000370, SPLK-CL-000380, SPLK-CL-000400 — confirmed in 10 4 2

**SRG-APP-000167-AU-002500** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to enforce password complexity by requiring that at least one lowercase character be used.

*Basis.* Splunk native authentication exposes a minimum count of lowercase characters that rejects non-conforming password modification attempts, so the requirement is reachable through application configuration. The setting governs Splunk native accounts only.

*Citation.* authentication.conf.spec:459 (minPasswordLowercase = <positive integer>, "Password modification attempts which do not meet this requirement are explicitly rejected", default 0); key confirmed resolvable on a live 10.4.2 instance via btool authentication list splunk_auth

*Mechanism.* authentication.conf [splunk_auth] minPasswordLowercase

*Assessment method.* splunk btool authentication list splunk_auth --debug (run as the Splunk service account) and read minPasswordLowercase; then attempt to set an all-uppercase password on a native test account and confirm rejection.

*Product reference.* SPLK-CL-000340, SPLK-CL-000350, SPLK-CL-000360, SPLK-CL-000370, SPLK-CL-000380, SPLK-CL-000400 — confirmed in 10 4 2

**SRG-APP-000168-AU-002510** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to enforce password complexity by requiring that at least one numeric character be used.

*Basis.* Splunk native authentication exposes a minimum count of digit characters that rejects non-conforming password modification attempts, so the requirement is reachable through application configuration. The setting governs Splunk native accounts only.

*Citation.* authentication.conf.spec:468 (minPasswordDigit = <positive integer>, "Password modification attempts which do not meet this requirement are explicitly rejected", default 0); key confirmed resolvable on a live 10.4.2 instance via btool authentication list splunk_auth

*Mechanism.* authentication.conf [splunk_auth] minPasswordDigit

*Assessment method.* splunk btool authentication list splunk_auth --debug (run as the Splunk service account) and read minPasswordDigit; then attempt to set a password containing no digit on a native test account and confirm rejection.

*Product reference.* SPLK-CL-000340, SPLK-CL-000350, SPLK-CL-000360, SPLK-CL-000370, SPLK-CL-000380, SPLK-CL-000400 — confirmed in 10 4 2

**SRG-APP-000169-AU-002520** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to enforce password complexity by requiring that at least one special character be used.

*Basis.* Splunk native authentication exposes a minimum count of special characters that rejects non-conforming password modification attempts, so the requirement is reachable through application configuration. The specification set records that the semicolon is not accepted as a special character, which narrows the character set an assessment should test with.

*Citation.* authentication.conf.spec:477 (minPasswordSpecial = <positive integer>, "The semicolon character is not allowed", "Password modification attempts which do not meet this requirement are explicitly rejected", default 0); key confirmed resolvable on a live 10.4.2 instance via btool authentication list splunk_auth

*Mechanism.* authentication.conf [splunk_auth] minPasswordSpecial

*Assessment method.* splunk btool authentication list splunk_auth --debug (run as the Splunk service account) and read minPasswordSpecial; then attempt to set an alphanumeric-only password on a native test account and confirm rejection.

*Product reference.* SPLK-CL-000340, SPLK-CL-000350, SPLK-CL-000360, SPLK-CL-000370, SPLK-CL-000380, SPLK-CL-000400 — confirmed in 10 4 2

**SRG-APP-000170-AU-002530** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to require the change of at least eight of the total number of characters when passwords are changed.

*Basis.* The inheritance fails on two independent grounds. First, DISA's own product-specific implementation for this requirement's CCI places it inside the application. The six rules this requirement carries as references (SPLK-CL-000340, 000350, 000360, 000370, 000380 and 000400) all direct password policy into authentication.conf under [splunk_auth], and they appear in the same sunsetted STIG whose SPLK-CL-000320 directs LDAP or SAML. In that STIG, directory delegation and native password-policy hardening are concurrent obligations, not alternatives, so CCI-004066 was never treated as inherited from the directory service. Second, the prior determination concedes in its own basis a residual that its named provider does not reach: the account of last resort, which SPLK-CL-000320 expressly preserves in native authentication. A control whose supporting rationale states that the provider does not cover part of the scope is a partially implemented control, not an inherited one, and the product always retains the native realm that holds it. Splunk exposes a password composition and history surface in [splunk_auth], and the selection of an external provider is itself made through an application setting (authType), so the requirement applies to the application. The absence of a key that counts changed character positions is real and my own search confirms it, but that makes the character-difference element an expected Other Than Satisfied result against an applicable requirement. Inability to meet a requirement is a finding to be carried as a risk decision, not a boundary question, and OUTSIDE_BOUNDARY on this row would tell an AO that no native password policy review is owed.

*Citation.* authentication.conf.spec:441, 450, 459, 468, 477 (minPasswordLength, minPasswordUppercase, minPasswordLowercase, minPasswordDigit, minPasswordSpecial under [splunk_auth]); :554 and :561 (enablePasswordHistory, passwordHistoryCount); :30 ([authentication] authType = [Splunk|LDAP|Scripted|SAML|ProxySSO]); :368-371 (Scripted authentication section and its [<authSettings-key>] stanza). Independent search over every file in the specification set (find . -type f -print0 | xargs -0 grep -niE "difok|charactersChanged|minPasswordDiff|passwordDiff|percentChanged", 128 files, 71 of them .spec) returns 0 matches, so no character-difference key exists; that part of the prior evidence is sound. On a live 10.4.2 instance btool authentication list splunk_auth enumerates the five composition keys together with enablePasswordHistory and passwordHistoryCount and no difference key, establishing that the composition mechanism exists. The IA-1 inventory record for this SRG id carries stig_reference SPLK-CL-000340/000350/000360/000370/000380/000400, whose fix text names authentication.conf [splunk_auth].

*Mechanism.* authentication.conf, [splunk_auth]: minPasswordLength, minPasswordUppercase, minPasswordLowercase, minPasswordDigit, minPasswordSpecial, enablePasswordHistory, passwordHistoryCount. Authentication.conf, [authentication]: authType, which selects whether composition is additionally enforced by a directory or federation provider. The stanza carries no key that sets a character-difference threshold.

*Providing baseline.* The organization's LDAP directory service or SAML identity provider, as selected by authentication.conf [authentication] authType (authentication.conf.spec:30)

*Assessment method.* Run `splunk btool authentication list splunk_auth --debug` as the splunk service account and examine the composition and history keys resolved for the native realm; record that the stanza exposes no character-difference threshold. Run `splunk btool authentication list authentication --debug` for authType, and enumerate the accounts remaining in native authentication through the /services/authentication/users endpoint filtered on type Splunk, to establish the scope over which the shortfall is carried.

*Product reference.* SPLK-CL-000340, SPLK-CL-000350, SPLK-CL-000360, SPLK-CL-000370, SPLK-CL-000380, SPLK-CL-000400 — confirmed in 10 4 2

**SRG-APP-000173-AU-002560** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to enforce 24 hours/1 day as the minimum password lifetime.

*Basis.* The capability finding is correct and my own search reproduces it: the specification set contains no minimum password age or minimum lifetime key, and expirePasswordDays is a ceiling only. The boundary conclusion drawn from it does not survive. This requirement carries the same CCI and the same six product STIG references as the character-difference requirement, including SPLK-CL-000400, which sets password lifetime through authentication.conf [splunk_auth]; DISA therefore placed password lifetime for this CCI inside the application rather than inheriting it from the directory service. The prior determination also concedes the same uncovered residual, the account of last resort that SPLK-CL-000320 preserves in native authentication, which the named LDAP or SAML provider does not reach and cannot be made to reach. An inheritance that the assessor's own basis says is incomplete is a finding, not an inheritance. The requirement addresses the application's native password lifetime surface, that surface is configured in authentication.conf, and the path by which an organization-selected handler could enforce a 24-hour floor is itself an application setting (authType, including the Scripted authentication extension point). Applicability therefore rests with the application. Because no key sets a floor, an instance retaining native accounts will be assessed Other Than Satisfied on this element and the shortfall carried as a documented risk decision against the system owner, which is where the obligation belongs. Writing it as outside the boundary retires an obligation the product cannot discharge.

*Citation.* Independent search over every file in the specification set (find . -type f -print0 | xargs -0 grep -niE "minPasswordAge|passwordMinAge|minPasswordLifetime|minimumPasswordAge") returns 0 matches, so no minimum-lifetime key exists. Authentication.conf.spec:487 documents expirePasswordDays as the number of days before the password expires after a reset, a maximum only; :554 and :561 (enablePasswordHistory, passwordHistoryCount) are the application's control over the reuse that a minimum lifetime exists to protect, per this requirement's own discussion; :30 ([authentication] authType); :368-371 (Scripted authentication section and its [<authSettings-key>] stanza). On a live 10.4.2 instance btool authentication list splunk_auth enumerates expirePasswordDays, expireAlertDays, expireUserAccounts, forceWeakPasswordChange, enablePasswordHistory, passwordHistoryCount, the lockout keys and constantLoginTime, and no minimum-age counterpart, establishing both that the lifetime surface exists and that it carries no floor. The IA-1 inventory record for this SRG id carries stig_reference SPLK-CL-000400, whose fix text names authentication.conf [splunk_auth] expirePasswordDays.

*Mechanism.* authentication.conf, [splunk_auth]: expirePasswordDays governs native password lifetime, with enablePasswordHistory and passwordHistoryCount controlling the reuse the floor protects. The stanza carries no minimum-lifetime key. Authentication.conf, [authentication]: authType, including the Scripted authentication extension point at the Scripted authentication section, is where an organization-selected handler enforcing a 24-hour floor is configured.

*Providing baseline.* The organization's LDAP directory service or SAML identity provider, as selected by authentication.conf [authentication] authType (authentication.conf.spec:30)

*Assessment method.* Run `splunk btool authentication list splunk_auth --debug` as the splunk service account and examine the password lifetime keys; record that no minimum-lifetime key is available. Run `splunk btool authentication list authentication --debug` for authType, enumerate the accounts remaining in native authentication through /services/authentication/users filtered on type Splunk, and examine the documented procedure governing those accounts for the interval between password changes.

*Product reference.* SPLK-CL-000340, SPLK-CL-000350, SPLK-CL-000360, SPLK-CL-000370, SPLK-CL-000380, SPLK-CL-000400 — confirmed in 10 4 2

**SRG-APP-000174-AU-002570** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to enforce a 180-day maximum password lifetime restriction.

*Basis.* Splunk native authentication exposes a maximum password lifetime in days, bounded at 3650, so a 180-day ceiling is reachable through application configuration. The lifetime value has no effect unless password expiration is also turned on through expireUserAccounts, which the specification set records as disabled by default; an assessment that reads expirePasswordDays alone would reach a wrong result.

*Citation.* authentication.conf.spec:487 (expirePasswordDays = <positive integer>, maximum value 3650, default 90); authentication.conf.spec:504 (expireUserAccounts = <boolean>, "Specifies whether password expiration is enabled", "Default: false (user passwords do not expire)")

*Mechanism.* authentication.conf [splunk_auth] expirePasswordDays, expireUserAccounts

*Assessment method.* splunk btool authentication list splunk_auth --debug (run as the Splunk service account) and read both expirePasswordDays and expireUserAccounts; a lifetime value is Other Than Satisfied where expireUserAccounts does not enable expiration.

*Product reference.* SPLK-CL-000340, SPLK-CL-000350, SPLK-CL-000360, SPLK-CL-000370, SPLK-CL-000380, SPLK-CL-000400 — confirmed in 10 4 2

**SRG-APP-000177-AU-002650** — CAT III — Applicable, evidence grade C.

The Central Log Server must map the authenticated identity to the individual user or group account for PKI-based authentication.

*Basis.* Splunk exposes the identity mapping this requirement names as explicit configuration: certBasedUserAuthMethod selects whether the subject is taken from the certificate Common Name in full, from the EDIPI extracted from it, or from a PIV identifier read out of the Subject Alternative Name, with certBasedUserAuthPivOidList naming the object identifiers searched. The resulting subject is then bound to a Splunk role through the roleMap and userToRoleMap stanzas, which completes the mapping to an individual or group account.

*Citation.* web.conf.spec:133 (certBasedUserAuthMethod = CommonName|EDIPI|PIV, "The method that the Splunk platform uses to extract LDAP credentials from client certificates"); web.conf.spec:144 (certBasedUserAuthPivOidList); authentication.conf.spec:351 ([roleMap_<authSettings-key>]); authentication.conf.spec:1251 ([userToRoleMap_<saml-authSettings-key>])

*Mechanism.* web.conf [settings] certBasedUserAuthMethod, certBasedUserAuthPivOidList; authentication.conf [roleMap_<authSettings-key>], [userToRoleMap_<saml-authSettings-key>]

*Assessment method.* splunk btool web list settings --debug and splunk btool authentication list --debug (run as the Splunk service account) to read certBasedUserAuthMethod, certBasedUserAuthPivOidList and the role-map stanzas; then authenticate with a PKI credential and confirm the audit record names the individual account the certificate mapped to.

**SRG-APP-000291-AU-000200** — CAT III — Applicable, evidence grade C.

The Central Log Server must notify system administrators and ISSO when accounts are created.

*Basis.* Splunk Enterprise implements notification through scheduled searches with an email action, and the recipient list, schedule, trigger condition and mail transport are all part of the product's configuration surface, so a notification on account creation events is implementable by configuration. DISA's product implementation reads this requirement at the Central Log Server as a report over the account events received from the devices and hosts within its scope of coverage, and the same mechanism serves notification on the log server's own account creations drawn from its audit trail.

*Citation.* savedsearches.conf.spec:73 enableSched; savedsearches.conf.spec:79 cron_schedule; savedsearches.conf.spec:249 counttype and :270 alert_condition as the trigger; savedsearches.conf.spec:300 action.email and :304 action.email.to; alert_actions.conf.spec:157 [email] with from at :163 and to at :167 and the mail transport settings that follow; savedsearches.conf.spec:403 action.script and :599-622 of alert_actions.conf.spec for webhook and custom action delivery. The audit trail that supplies the log server's own account events is audit.conf.spec:23-29 [auditTrail] queueing with indexes.conf:200 [_audit].

*Mechanism.* savedsearches.conf [<search name>] enableSched, cron_schedule, counttype or alert_condition, action.email, action.email.to; alert_actions.conf [email] from, to, mailserver

*Assessment method.* Run as the Splunk service account: splunk btool savedsearches list --debug and identify a scheduled search whose trigger is account creation events and whose action.email.to resolves to the system administrator and ISSO addresses, then splunk btool alert_actions list email --debug to confirm the mail transport is defined. Test delivery rather than accepting the configuration alone, and corroborate by interviewing the ISSO on receipt, as SPLK-CL-000020 directs. The identity of the designated SA and ISSO recipients is an organizational artifact the assessment must obtain separately.

*Product reference.* SPLK-CL-000020 — no reference

**SRG-APP-000292-AU-000420** — CAT III — Applicable, evidence grade C.

For devices and hosts within its scope of coverage, the Central Log Server must be configured to notify the system administrator (SA) and information system security officer (ISSO) when account modification events are received.

*Basis.* The Not Applicable clause this requirement carries reads "Note: This is not applicable (NA) if notifications are performed by another device", which is a condition about a particular deployment's division of labor and not a property of Splunk Enterprise, so it cannot be established as holding for the product and grade B is not available. Splunk implements the notification itself through a scheduled search with an email, script or webhook action over the account modification events it receives, so the requirement applies and the mechanism is named.

*Citation.* The clause quoted verbatim from the benchmark check text: "Note: This is not applicable (NA) if notifications are performed by another device." Mechanism: savedsearches.conf.spec:73 enableSched, :79 cron_schedule, :270 alert_condition, :300 action.email, :304 action.email.to, :403 action.script; alert_actions.conf.spec:157 [email] and :599 [webhook].

*Mechanism.* savedsearches.conf [<search name>] enableSched, cron_schedule, alert_condition, action.email, action.email.to; alert_actions.conf [email] and [webhook]

*Assessment method.* Run as the Splunk service account: splunk btool savedsearches list --debug and identify a scheduled search whose trigger is account modification events received from the devices and hosts within the log server's scope of coverage and whose action.email.to resolves to the SA and ISSO. Test delivery and corroborate receipt with the ISSO. Where the site asserts the benchmark's Not Applicable clause, the assessor must identify the other device performing the notification by name and assess the notification there; an unnamed other device does not sustain the clause.

*Product reference.* SPLK-CL-000020 — no reference

**SRG-APP-000293-AU-000430** — CAT III — Applicable, evidence grade C.

For devices and hosts within its scope of coverage, the Central Log Server must notify the system administrator (SA) and information system security officer (ISSO) when events indicating account disabling actions are received.

*Basis.* Splunk Enterprise implements event-triggered notification in its own configuration: a scheduled search with an alerting condition and an email action addressed to named recipients. The requirement's Not Applicable clause turns on whether "notifications are performed by another device", which is a property of a deployment rather than of the product, so grade B is not available and the requirement applies to Splunk as the Central Log Server. Designation of the SA and the ISSO is an organizational act; delivery of the notification is configuration.

*Citation.* savedsearches.conf.spec:73 (enableSched), :79 (cron_schedule), :249 (counttype), :270 (alert_condition), :300 (action.email), :304 (action.email.to), :313 (action.email.from); alert_actions.conf.spec:157 ([email]), :163 (from), :199 (subject), :276 (mailserver), :293 (use_tls). On a live Splunk Enterprise 10.4.2 instance, btool returns the alert_actions [email] stanza and 182 action.email.* lines in the merged savedsearches surface.

*Mechanism.* savedsearches.conf [<search_name>]: enableSched, cron_schedule, alert_condition, action.email, action.email.to; alert_actions.conf [email]: from, subject, mailserver, use_tls

*Assessment method.* splunk btool savedsearches list --debug and splunk btool alert_actions list --debug (run as the Splunk service account); examine the scheduled search set for a search whose alert_condition matches received account-disabling events and whose action.email.to addresses the SA and ISSO, then interview the ISSO to confirm receipt.

*Product reference.* SPLK-CL-000020 — confirmed in 10 4 2

**SRG-APP-000294-AU-000440** — CAT III — Applicable, evidence grade C.

For devices and hosts within its scope of coverage, the Central Log Server must notify the System Administrator (SA) and Information System Security Officer (ISSO) when events indicating account removal actions are received.

*Basis.* The mechanism is the same alerting and email-action surface used for any received-event notification; account-removal events are distinguished by the alerting search, not by a different product capability. The Not Applicable clause is conditioned on another device performing notification, which cannot be established as a property of Splunk Enterprise, so grade B is unavailable and the requirement applies.

*Citation.* savedsearches.conf.spec:73 (enableSched), :79 (cron_schedule), :270 (alert_condition), :300 (action.email), :304 (action.email.to); alert_actions.conf.spec:157 ([email]), :276 (mailserver). On a live Splunk Enterprise 10.4.2 instance, btool returns the alert_actions [email] stanza in the merged configuration.

*Mechanism.* savedsearches.conf [<search_name>]: enableSched, cron_schedule, alert_condition, action.email, action.email.to; alert_actions.conf [email]: from, mailserver, use_tls

*Assessment method.* splunk btool savedsearches list --debug and splunk btool alert_actions list --debug; examine the scheduled search set for a search whose alert_condition matches received account-removal events and whose action.email.to addresses the SA and ISSO, then interview the ISSO to confirm receipt.

*Product reference.* SPLK-CL-000020 — confirmed in 10 4 2

**SRG-APP-000297-AU-000570** — CAT III — Applicable, evidence grade C.

The Central Log Server must display an explicit logout message to users indicating the reliable termination of authenticated communications sessions.

*Basis.* Splunk Web message text is externalized and overridable. Messages.conf defines message resources by component and key with message, action and target fields, and replaces literals.conf, which the specification set marks deprecated in this version. The shipped message catalog carries logout resources for the SAML flow only and carries no generic session-termination message, so for native authentication the operator's mechanism is the post-logout redirect target rather than a message resource. The requirement is implementable through the application's own configuration and therefore applies; whether a message is in fact presented is a compliance result for the assessment.

*Citation.* messages.conf.spec:68 ([<component>]), :79 ([<component>:<key>]), :81 (message), :90 (action), :116 (target = [auto|ui|log|ui,log|none]); literals.conf.spec:3 (literals.conf deprecated, messages.conf directed instead); authentication.conf.spec:780 (redirectAfterLogoutToUrl). On a live Splunk Enterprise 10.4.2 instance the shipped default message catalog holds 2,090 message stanzas, of which [SAML:LOGOUT] and [SAML:REDIRECT_AFTER_LOGOUT] concern logout; a search of that catalog for "logged out", "signed out", "session expired" and "session timed" returns 0 lines.

*Mechanism.* messages.conf [<component>:<key>]: message, action, target (overriding the shipped resources, including [SAML:LOGOUT] and [SAML:REDIRECT_AFTER_LOGOUT]); authentication.conf [<saml-authSettings-key>]: redirectAfterLogoutToUrl

*Assessment method.* Authenticate to Splunk Web, invoke logout, and examine the resulting page for an explicit statement that the session has been terminated; splunk btool messages list --debug to identify any local message override, and splunk btool authentication list --debug for redirectAfterLogoutToUrl where SAML is the configured authentication type.

**SRG-APP-000359-AU-000120** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to send an immediate alert to the System Administrator (SA) and Information System Security Officer (ISSO) (at a minimum) when allocated log record storage volume reaches 75 percent of the repository maximum log record storage capacity.

*Basis.* The requirement's clause reads "Note: This is not applicable (NA) if an external application or operating system manages this function." That states a delegation condition at a deployment rather than a product property, and Splunk monitors index filesystem free space and raises alerts to configured recipients natively, so the clause does not support a product-level Not Applicable and grade B is unavailable.

*Citation.* server.conf.spec:1856 [diskUsage] with minFreeSpace at :1858, which in 10.4.2 accepts a percentage of the partition as well as a size in megabytes; the referenced product STIG rule's instruction to express the value in megabytes predates that extension, while the setting itself is unchanged. Health.conf.spec:217 [alert_action:*] with disabled at :218 and action.<action parameter> at :222; :93 alert.actions, :96 alert.min_duration_sec, :101 alert.threshold_color; the shipped health.conf carries [alert_action:email] with action.to and action.cc, and the [feature:disk_space] indicator thresholds keyed on minFreeSpace. Confirmed readable on 10.4.2 with btool health list alert_action:email --debug and btool server list diskUsage --debug.

*Mechanism.* server.conf [diskUsage] minFreeSpace sets the threshold; health.conf [feature:disk_space] indicator:disk_space_remaining_multiple_minfreespace:yellow and :red set the warning levels as multiples of it, with alert.actions, alert.threshold_color and alert.min_duration_sec arming the alert and [alert_action:email] action.to and action.cc carrying the recipients

*Assessment method.* Run `splunk btool server list diskUsage --debug` and compare minFreeSpace against the size of each index volume, and `splunk btool health list --debug` for the feature:disk_space indicator thresholds, alert.actions and the [alert_action:email] action.to and action.cc recipients; confirm the recipients are the designated SA and ISSO addresses.

*Product reference.* SPLK-CL-000160 — confirmed in 10 4 2

**SRG-APP-000360-AU-000130** — CAT III — Applicable, evidence grade C.

For the host and devices within its scope of coverage, the Central Log Server must be configured to send a real-time alert to the System Administrator (SA) and Information System Security Officer (ISSO) (at a minimum) of all audit failure events, such as loss of communications with hosts and devices, or if log records are no longer being received.

*Basis.* Splunk exposes a real-time scheduled alert path over its own indexed records, which can test for the absence of records from a named host, and a separate health-reporting alert path over its forwarding and indexing features, each with configurable recipients and trigger latency. The referenced product STIG rule is interview-based and names no configuration setting, directing the use of the product's reporting and notification tools.

*Citation.* savedsearches.conf.spec:31 [<stanza name>], :44 search, :137 realtime_schedule, :270 alert_condition, :249 counttype, :887 alert.severity, :300 action.email, :304 action.email.to, :79 cron_schedule; health.conf.spec:93 alert.actions, :96 alert.min_duration_sec, :101 alert.threshold_color, :217 [alert_action:*] with action.<action parameter> at :222; alert_actions.conf.spec:157 [email], :517 [script], :599 [webhook]. Confirmed on 10.4.2: the savedsearches default stanza returns action.email, alert_condition and realtime_schedule keys via btool.

*Mechanism.* savedsearches.conf [<stanza name>] search with realtime_schedule, alert_condition, counttype, alert.severity and action.email.to; health.conf [feature:*] alert.actions, alert.threshold_color and alert.min_duration_sec with [alert_action:email] action.to; alert_actions.conf [email], [webhook], [script]

*Assessment method.* Run `splunk btool savedsearches list --debug` for alert definitions carrying realtime_schedule, alert_condition and action.email.to, and `splunk btool health list --debug` for alert.actions, alert.min_duration_sec and the [alert_action:email] recipients; then stop a sending host and confirm an alert reaches the designated SA and ISSO addresses within seconds.

*Product reference.* SPLK-CL-000170 — no reference

**SRG-APP-000362-AU-000170** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to perform on-demand sorting of log records for events of interest based on the content of organization-defined audit fields within log records.

*Basis.* Splunk exposes field extraction that defines the organization's audit fields and stored, on-demand search definitions that order results on those fields over a selectable range. Sorting log records on organization-defined fields is therefore a product capability and the requirement applies to the application.

*Citation.* savedsearches.conf.spec:44 search, :564 dispatch.earliest_time, :571 dispatch.latest_time; props.conf.spec:1102 EXTRACT-<class>, :1085 REPORT-<class>; transforms.conf.spec:80 REGEX, :399 FIELDS; fields.conf.spec:89 INDEXED; times.conf.spec:40 [<timerange_name>] with earliest_time at :54 and latest_time at :61. The sort and table commands are defined in the shipped searchbnf.conf at :4375 and :4049.

*Mechanism.* savedsearches.conf [<stanza name>] search carrying the sort expression with dispatch.earliest_time and dispatch.latest_time; props.conf EXTRACT-<class> and REPORT-<class> with transforms.conf REGEX and FIELDS defining the audit fields; fields.conf INDEXED; times.conf [<timerange_name>] earliest_time and latest_time

*Assessment method.* Run `splunk btool props list --debug` and `splunk btool transforms list --debug` to confirm the organization-defined audit fields are extracted, then run an on-demand search that sorts audit records on those fields and confirm the ordering.

**SRG-APP-000363-AU-000180** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to perform on-demand searches of log records for events of interest based on the content of organization-defined audit fields within log records.

*Basis.* Splunk grants and scopes an on-demand search interface over its audit records by role, and exposes field extraction and reusable search definitions that address the organization's audit fields. Searching log records on organization-defined fields is therefore a product capability and the requirement applies to the application.

*Citation.* authorize.conf.spec:953 [capability::search], :282 srchIndexesDefault, :292 srchIndexesAllowed; savedsearches.conf.spec:44 search, :564 dispatch.earliest_time; props.conf.spec:1102 EXTRACT-<class>; transforms.conf.spec:80 REGEX, :399 FIELDS; macros.conf.spec:24 and :52 definition; fields.conf.spec:89 INDEXED.

*Mechanism.* authorize.conf [capability::search] with [role_<roleName>] srchIndexesDefault and srchIndexesAllowed scoping the search interface; savedsearches.conf search for stored queries; props.conf EXTRACT-<class> with transforms.conf REGEX and FIELDS defining the audit fields; macros.conf definition

*Assessment method.* Run `splunk btool authorize list --debug` to confirm the roles holding the search capability and their index scope, `splunk btool props list --debug` for the audit field extractions, then run an on-demand search restricted by those fields and confirm the records returned.

**SRG-APP-000365-AU-000210** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to perform audit reduction that supports after-the-fact investigations of security incidents.

*Basis.* Splunk exposes reduction over historical ranges, and that capability is bounded on two sides by product settings: the retention period caps how far back records remain reachable, and the summarized or accelerated range caps what reduction covers. The specification states that records are deleted at freeze unless an archive setting is given, so both bounds form part of the determination.

*Citation.* indexes.conf.spec:684 frozenTimePeriodInSecs, which states that data is deleted when rolled to frozen if no coldToFrozenScript is specified, :792 coldToFrozenDir, :713 coldToFrozenScript; savedsearches.conf.spec:564 dispatch.earliest_time, :571 dispatch.latest_time, :439 action.summary_index, :772 auto_summarize.command; datamodels.conf.spec:42 acceleration.earliest_time, :52 acceleration.backfill_time; times.conf.spec:54 earliest_time, :61 latest_time.

*Mechanism.* indexes.conf frozenTimePeriodInSecs with coldToFrozenDir or coldToFrozenScript determining how far back records remain reachable; savedsearches.conf dispatch.earliest_time and dispatch.latest_time with times.conf [<timerange_name>]; datamodels.conf acceleration.earliest_time and acceleration.backfill_time; savedsearches.conf auto_summarize and action.summary_index retaining the reduced sets

*Assessment method.* Run `splunk btool indexes list --debug` for frozenTimePeriodInSecs, coldToFrozenDir and coldToFrozenScript on every index holding audit records, and `splunk btool savedsearches list --debug` plus `splunk btool datamodels list --debug` for the summarized and accelerated ranges; then run a reduction over a range at the far edge of the retention period and confirm it returns records.

**SRG-APP-000366-AU-000220** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to generate on-demand audit review and analysis reports.

*Basis.* Splunk Enterprise implements report generation as a saved search object, so an on-demand audit review and analysis report is a configurable application artifact rather than a function of another baseline. Savedsearches.conf carries the report body and its dispatch time range, and authorize.conf controls which roles may run and save one.

*Citation.* savedsearches.conf.spec:31 [<stanza name>], :44 search, :599 dispatch.earliest_time, :606 dispatch.latest_time; authorize.conf.spec:1088 [capability::search], :1081 [capability::schedule_search]. Line numbers are taken from the 10.4.2 specification set as installed on the instance (134 files under etc/system/README, each stamped Version 10.4.2); the staged reference set of 128 files is stamped Version 10.0.0 and its line numbers differ, so every citation in this group was re-confirmed against the 10.4.2 set. Both conf files are readable through btool on a 10.4.2 instance.

*Mechanism.* savedsearches.conf [<stanza name>] search, dispatch.earliest_time, dispatch.latest_time; authorize.conf [capability::search], [capability::schedule_search]

*Assessment method.* podman exec -u splunk <instance> /opt/splunk/bin/splunk btool savedsearches list --debug and splunk btool authorize list --debug; examine for report stanzas covering the audit indexes in scope and for the roles holding search and schedule_search.

**SRG-APP-000367-AU-000230** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to generate reports that support on-demand reporting requirements.

*Basis.* Splunk exposes report scheduling and report delivery through configuration, which is what distinguishes support for on-demand reporting requirements from ad hoc search alone. The requirement therefore applies to the application.

*Citation.* savedsearches.conf.spec:44 search, :86 enableSched, :92 cron_schedule, :228 schedule_window, :418 action.email.sendpdf, :335 action.email, :339 action.email.to; alert_actions.conf.spec:176 [email] [10.4.2 spec set].

*Mechanism.* savedsearches.conf [<stanza name>] search, enableSched, cron_schedule, schedule_window, action.email, action.email.sendpdf; alert_actions.conf [email]

*Assessment method.* splunk btool savedsearches list --debug and splunk btool alert_actions list --debug; examine report stanzas for enableSched, cron_schedule and a delivery action, and confirm a report can be dispatched on request.

**SRG-APP-000368-AU-000240** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to generate reports that support after-the-fact investigations of security incidents.

*Basis.* A report supporting after-the-fact investigation requires a retrospective dispatch range over data still held in the index, both of which Splunk sets through configuration. The requirement applies to the application; the investigative reach is bounded by index retention, which is also an application setting.

*Citation.* savedsearches.conf.spec:44 search, :599 dispatch.earliest_time, :606 dispatch.latest_time; indexes.conf.spec:441-442 (PER INDEX OPTIONS, set under an [<index>] entry), :761 frozenTimePeriodInSecs, :892 coldToFrozenDir [10.4.2 spec set].

*Mechanism.* savedsearches.conf [<stanza name>] search, dispatch.earliest_time, dispatch.latest_time; indexes.conf [<index>] frozenTimePeriodInSecs, coldToFrozenDir

*Assessment method.* splunk btool savedsearches list --debug for dispatch.earliest_time on investigative reports; splunk btool indexes list --debug for frozenTimePeriodInSecs and coldToFrozenDir on each audit index in scope.

**SRG-APP-000369-AU-000250** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to perform audit reduction that does not alter original content or time ordering of log records.

*Basis.* Splunk performs audit reduction at search time over the stored rawdata journal, and the specification set separates index-time from search-time field extraction: only index-time settings write to the stored event. The product also exposes settings that do alter content, so the requirement applies and the determination rests on those keys rather than on an assumption of immutability.

*Citation.* props.conf.spec:1042-1046 (Field extraction configuration: index time versus search time; TRANSFORMS is index-time, REPORT and EXTRACT are search-time), :1173 REPORT-<class>, :1190 EXTRACT-<class>, :1331 SEDCMD-<class>; transforms.conf.spec:241 DEST_KEY, :286 (default _raw); field_filters.conf.spec:32 [<fieldFilterName>], :37 action; indexes.conf.spec:671 enableDataIntegrityControl [10.4.2 spec set].

*Mechanism.* props.conf REPORT-<class>, EXTRACT-<class> (search-time, non-altering); props.conf SEDCMD-<class>, transforms.conf DEST_KEY = _raw and field_filters.conf [<fieldFilterName>] action (altering); indexes.conf [<index>] enableDataIntegrityControl

*Assessment method.* splunk btool props list --debug and splunk btool transforms list --debug; examine for SEDCMD- entries and for TRANSFORMS- entries whose transforms.conf stanza sets DEST_KEY = _raw on the audit source types. Splunk btool field_filters list --debug and splunk btool indexes list --debug for enableDataIntegrityControl.

**SRG-APP-000370-AU-000260** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to generate reports that do not alter original content or time ordering of log records.

*Basis.* Report generation in Splunk is a search over indexed events; the search string and the search-time settings applied to it govern whether the report presents the original content and ordering. The requirement applies to the application, and the settings that can alter presented content are named in the specification set.

*Citation.* savedsearches.conf.spec:44 search; props.conf.spec:1173 REPORT-<class>, :1331 SEDCMD-<class>, :1401 EVAL-<fieldname>; field_filters.conf.spec:37 action (null(), sha256(), sha512(), string literal, sed()); props.conf.spec:1042-1046 (index time versus search time) [10.4.2 spec set].

*Mechanism.* savedsearches.conf [<stanza name>] search; field_filters.conf [<fieldFilterName>] action; props.conf SEDCMD-<class>, EVAL-<fieldname>

*Assessment method.* splunk btool savedsearches list --debug, reading each audit report's search string for commands that rewrite _raw or _time; splunk btool field_filters list --debug for filters whose index clause covers an audit index.

**SRG-APP-000374-AU-000290** — CAT III — Applicable, evidence grade C.

Upon receipt of the log record from hosts and devices, the Central Log Server must be configured to record time stamps of the time of receipt that can be mapped to Coordinated Universal Time (UTC).

*Basis.* Splunk stamps _indextime on every event at the point the receiver accepts it and exposes that value to search, and props.conf governs how the event timestamp is recognized and mapped to UTC, including an option that assigns the processing time to the event. The requirement applies to the application.

*Citation.* props.conf.spec:506 DATETIME_CONFIG (CURRENT assigns the current system time to each event, set at the aggregator processor), :558 TIME_FORMAT, :584 TZ, :596 TZ_ALIAS (the value is the timezone specifier to use when mapping the timestamp to UTC/GMT); limits.conf.spec:998 track_indextime_range; savedsearches.conf.spec:736 durable.track_time_type = _indextime [10.4.2 spec set]. Records emitted by a 10.4.2 instance carry an explicit numeric UTC offset in the timestamp field.

*Mechanism.* props.conf [<source type>] DATETIME_CONFIG, TIME_FORMAT, TZ, TZ_ALIAS; _indextime exposed through limits.conf track_indextime_range and savedsearches.conf durable.track_time_type

*Assessment method.* splunk btool props list --debug and examine TZ, TZ_ALIAS, TIME_FORMAT and DATETIME_CONFIG for each source type in scope; then compare _time and _indextime on a record received from a forwarding host and confirm both resolve to UTC.

**SRG-APP-000375-AU-000280** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to record time stamps for when log records are received by the log server that meet a granularity of one second for a minimum degree of precision.

*Basis.* Splunk records event time as an epoch value with a subsecond extension, which exceeds the one-second floor, and the precision carried through to search is governed by props.conf. The requirement applies to the application.

*Citation.* props.conf.spec:558 TIME_FORMAT (strptime format, which admits a fractional-second directive), :688 ADD_EXTRA_TIME_FIELDS with :696-700 (data about the sub-second timestamp granularity is left intact when set to subseconds); transforms.conf.spec:315 (when INGEST_EVAL accesses _time, subsecond information is addressed) [10.4.2 spec set]. Audit and internal records emitted by a 10.4.2 instance carry a millisecond fraction in the timestamp field.

*Mechanism.* props.conf [<source type>] TIME_FORMAT, ADD_EXTRA_TIME_FIELDS

*Assessment method.* splunk btool props list --debug for TIME_FORMAT and ADD_EXTRA_TIME_FIELDS on each source type in scope; then examine _time on a received record to subsecond precision.

**SRG-APP-000389-AU-000180** — CAT III — Applicable, evidence grade C.

The Central Log Server must require users to reauthenticate when organization-defined circumstances or situations require reauthentication.

*Basis.* Splunk exposes the circumstances that force a user to authenticate again as application configuration: session expiry after inactivity, whether a session survives a browser restart, and the browser-side inactivity bound are all settable, and credential expiry and forced replacement of a weak password compel re-establishment of the authenticator. The organization-defined circumstances themselves come from a policy document, so the determination pairs a configuration mechanism with an organizational definition the assessment must obtain.

*Citation.* web.conf.spec:924 (tools.sessions.timeout, "The number of minutes of inactivity before a user session is expired", default 60); web.conf.spec:403 (ui_inactivity_timeout); web.conf.spec:934 (tools.sessions.restart_persist, default true, sessions persist across browser restarts); authentication.conf.spec:487 (expirePasswordDays); authentication.conf.spec:509 (forceWeakPasswordChange)

*Mechanism.* web.conf [settings] tools.sessions.timeout, ui_inactivity_timeout, tools.sessions.restart_persist; authentication.conf [splunk_auth] expirePasswordDays, expireUserAccounts, forceWeakPasswordChange

*Artifact.* The system security plan or access control policy that defines the circumstances requiring reauthentication

*Assessment method.* splunk btool web list settings --debug (run as the Splunk service account) and read tools.sessions.timeout, ui_inactivity_timeout and tools.sessions.restart_persist; note that the setting name is tools.sessions.timeout and that the singular form named by the sunsetted product STIG does not resolve; then compare the configured circumstances against the organization's documented definition.

*Product reference.* SPLK-CL-000010 — renamed

**SRG-APP-000515-AU-000110** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured to off-load interconnected systems in real time and off-load standalone systems weekly, at a minimum.

*Basis.* The benchmark's Not Applicable note turns on a site condition and states nothing about Splunk as a product: Splunk itself implements off-load, forwarding received data to another receiver in real time through outputs.conf and archiving rolled buckets through indexes.conf. Because the product provides the mechanism, the clause does not hold at product level, grade B is not available, and a site that off-loads by other means records an inherited implementation rather than a Not Applicable.

*Citation.* Benchmark clause, quoted verbatim: "Note: This is not applicable (NA) if an external application or operating system manages this function." Product mechanism: outputs.conf.spec:61 [tcpout], :121 [tcpout:<target_group>], :123 server, :1071 [syslog]; indexes.conf.spec:761 frozenTimePeriodInSecs, :790 coldToFrozenScript, :892 coldToFrozenDir; inputs.conf.spec:630 [splunktcp] on the receiving side [10.4.2 spec set].

*Mechanism.* outputs.conf [tcpout], [tcpout:<target_group>] server; indexes.conf [<index>] coldToFrozenDir, coldToFrozenScript, frozenTimePeriodInSecs

*Assessment method.* splunk btool outputs list --debug for [tcpout] target groups and server entries; splunk btool indexes list --debug for coldToFrozenDir or coldToFrozenScript on each index in scope; splunk btool inputs list --debug on the receiver for the matching [splunktcp] or [splunktcp-ssl:<port>] stanza.

*Product reference.* SPLK-CL-000150 — confirmed in 10 4 2

**SRG-APP-000516-AU-000060** — CAT III — Applicable, evidence grade C.

The Central Log Server must be configured so changes made to the level and type of log records stored in the centralized repository must take effect immediately without the need to reboot or restart the application.

*Basis.* Splunk binds a configuration file to a REST reload handler through the app.conf [triggers] stanza, which is the product's mechanism for applying a change in place of a restart, and the audit specification states that per-path audit settings take effect on a reload of the audit subsystem or of audit.conf through the REST API. The requirement applies to the application; not every setting bearing on the level and type of stored log records is reloadable, so the assessment is taken per setting in scope.

*Citation.* app.conf.spec:199 [triggers], :205 reload.<conf_file_name> = [ simple | never | rest_endpoints | access_endpoints <handler_url> | http_get <handler_url> | http_post <handler_url> ], :231 reload.<conf_file_name>.<conf_stanza_prefix>; audit.conf.spec:79-80 (all settings in [auditconfig:/path] stanzas take effect when you reload the audit subsystem or the audit.conf file using the REST API); authorize.conf.spec:578 [capability::change_audit] (lets a user reload audit settings). Authentication.conf.spec:2079 is an example of a setting whose change requires a restart, which is why the finding is per setting [10.4.2 spec set].

*Mechanism.* app.conf [triggers] reload.<conf_file_name>, reload.<conf_file_name>.<conf_stanza_prefix>; audit.conf [auditconfig:/path]; authorize.conf [capability::change_audit]

*Assessment method.* splunk btool app list --debug and examine the reload.<conf> entries for the conf files that govern the level and type of stored log records (audit, inputs, indexes, props, transforms, field_filters); then change one such setting and confirm the change is in effect without a restart.

*Product reference.* SPLK-CL-000120, SPLK-CL-000260, SPLK-CL-000270, SPLK-CL-000280, SPLK-CL-000290 — confirmed in 10 4 2

\newpage

### Applicable, satisfied by documented procedure

**SRG-APP-000456-AU-000270** — CAT I — Applicable, evidence grade C.

The Central Log Server must install security-relevant software updates within 30 days unless the time period is directed by an authoritative source (e.g., IAVM, CTOs, DTMs, STIGs).

*Basis.* Splunk Enterprise does not install its own software updates. An upgrade is performed by replacing the installation from a vendor-supplied package, which is an administrative act outside the product's configuration surface; the specification set exposes no key that acquires, schedules or applies an update to the Splunk Enterprise instance. The update-related facilities the product does expose are notification or client-side only: web.conf updateCheckerBaseURL causes Splunk Web to contact the vendor for notice of new versions and can be turned off, app.conf show_upgrade_notification concerns notification for an app rather than the platform, and serverclass.conf updaterRunningFilter filters deployment clients by whether a separately installed self-updater is running, which upgrades deployment clients rather than the Central Log Server. DISA's own product-level implementation for this requirement directs an upgrade to a vendor-supported version rather than a setting, which is consistent with that reading. The requirement is real and applies to the Central Log Server, but the assessment objective is met by a documented flaw remediation procedure and the version record, not by configuration, and it is not inherited from another baseline because the software being patched is the Splunk application itself.

*Citation.* Searched all 67 .conf.spec files of the specification set for update, patch, hotfix, service pack, auto-update, self-update and package-manager vocabulary. The only hits bearing on installation are web.conf.spec:192 updateCheckerBaseURL, documented as a configurable vendor URL that Splunk Web pings for new versions and that can be set to 0 to stop the ping; app.conf.spec:116 show_upgrade_notification, app scope; and serverclass.conf.spec:316 updaterRunningFilter, whose own text states that the self-updater must be installed separately and upgrades the deployment client. No key applies an update to the instance. The installed version and build are readable with splunk version, confirmed on a Splunk 10.4.2 instance (build 33c3bf42cd73). The referenced rule SPLK-CL-000510 names no configuration setting: its fix text reads "Upgrade to a version supported by the vendor." and its check text states that the STIG is sunset, so there is no 10.4.2 setting to re-confirm, which is why stig_reference_status is recorded as no_reference rather than confirmed, renamed or withdrawn.

*Artifact.* The organization's flaw remediation procedure for Splunk Enterprise, naming the authoritative source monitored for security-relevant updates and the time period within which they are installed, together with the configuration management record of upgrades performed and evidence that the installed version remains on the vendor's supported release list.

*Assessment method.* Run splunk version as the Splunk service account to record the installed version and build, and compare it against the vendor's currently supported release list and against open IAVM, CTO, DTM and STIG direction for the product. Examine the organization's flaw remediation procedure and the configuration management record of upgrades to determine whether security-relevant updates were installed within 30 days, or within the period an authoritative source directs. There is no setting to examine; the determination rests on the procedure and the version record.

*Product reference.* SPLK-CL-000510 — no reference

**SRG-APP-001035-AU-000430** — CAT I — Applicable, evidence grade C.

The Central Log Server must be a version supported by the vendor.

*Basis.* SA-22 a requires replacement of system components once vendor support for them ends. The requirement applies to Splunk Enterprise in the Central Log Server role, but no setting in the product's configuration surface can make an installed release a supported one. Support status is a property of the release itself and of the maintenance entitlement held for it, established by documentation rather than by configuration. The assessment objective is met by examining the installed release against the vendor's published support policy, together with the maintenance entitlement and the upgrade procedure that keeps the release current. The check text contains no Not Applicable condition, and the absence of a configuration mechanism does not make the requirement inapplicable to the product.

*Citation.* Exhaustive sweep of all 128 specification files for any key governing support status or version currency (GNU grep 3.12 over every 'key =' definition in *.conf.spec, keys filtered on support|eol|lifecycle|upgrade|patch|version) returns no key that attests, enforces or determines vendor support status; a separate search for end-of-life|end-of-support|EOL|vendor support|supported release|supported lifecycle returns zero hits across the set. The only version-adjacent surfaces are web.conf.spec:192-196 updateCheckerBaseURL, which only controls whether Splunk Web polls the vendor for newer releases and may be set to 0; app.conf.spec:116-119 show_upgrade_notification, a per-app Splunk Web notice; and limits.conf.spec:3556-3603 version_upgrade_*, documented as internal KV store upgrade timing settings. None of these determines support status. The product reports its own release through its CLI: 'splunk version' returns the release and build identifier, confirmed read-only on a live 10.4.2 instance with exit status 0.

*Artifact.* Current Splunk Enterprise software maintenance and support entitlement, together with the organization's software lifecycle and patch management procedure identifying the supported-release baseline and the trigger for upgrade before vendor end of support.

*Assessment method.* Run 'splunk version' as the splunk service account on the instance and compare the reported release against the vendor's published Splunk Enterprise support policy and the end-of-support date for that release train. Examine the software maintenance entitlement in force and the patch management procedure governing upgrades. Other Than Satisfied where the installed release is at or past vendor end of support, or where no maintenance entitlement covers it.

**SRG-APP-001035-WSR-000340** — CAT I — Applicable, evidence grade C.

The web server must be a version supported by the vendor.

*Basis.* The HTTP service this requirement addresses is, in Splunk Enterprise, the bundled Splunk Web application server and the splunkd HTTP listeners rather than a separately procured web server product. The specification set exposes no version or support attribute for that embedded server, so its support status is the support status of the Splunk Enterprise release that carries it, and the determination resolves the same way as SRG-APP-001035-AU-000430 under the shared CCI: no configuration makes a release supported, and the assessment objective is met by examining the installed release against the vendor's published support policy together with the maintenance entitlement. Where an organization introduces a separately procured HTTP front end, that product is a distinct component under its own baseline and its version support is assessed against that baseline, not against the Splunk application.

*Citation.* web.conf.spec:16 [settings] with startwebserver (web.conf.spec:23), httpport (web.conf.spec:28), appServerPorts (web.conf.spec:44) and enableSplunkWebSSL (web.conf.spec:70) establish that the web server is a component of Splunk Enterprise configured through the product's own conf file; web.conf.spec:832, web.conf.spec:986 and web.conf.spec:1495 identify that server as the bundled CherryPy application server. The same exhaustive sweep of all 128 specification files returns no key reporting or constraining an embedded HTTP server version or support level, and no hit for end-of-life|end-of-support|EOL|vendor support|supported release. The only version-adjacent web.conf setting is updateCheckerBaseURL (web.conf.spec:192-196), a release-notification URL that may be disabled. 'splunk version' on a live 10.4.2 instance returns a single release identifier for the product, with no separately reported web-tier version (exit status 0, read-only).

*Artifact.* Current Splunk Enterprise software maintenance and support entitlement covering the installed release, together with the organization's software lifecycle and patch management procedure; where an external HTTP front end is procured, that product's own support entitlement under its own baseline.

*Assessment method.* Run 'splunk version' as the splunk service account and compare the reported release against the vendor's published Splunk Enterprise support policy and end-of-support date. Run 'splunk btool web list settings' as the splunk service account to confirm that Splunk Web is the serving HTTP component within the application boundary and that no separately versioned web server product is in scope. Examine the maintenance entitlement and the upgrade procedure. Other Than Satisfied where the installed release is at or past vendor end of support, or where an HTTP front end in the boundary runs an unsupported version.

**SRG-APP-000131-WSR-000073** — CAT II — Applicable, evidence grade D.

Expansion modules must be fully reviewed, tested, and signed before they can exist on a production web server.

*Basis.* An exhaustive search of the shipped specification set returns no code-signing or package-signature enforcement setting, so Splunk cannot enforce the signing of expansion modules internally. The requirement's own fix text permits enforcement 'internally or through an external utility', so the control is real and is met by the organization's documented review, test and approval of each app or add-on admitted to a production instance. The application contributes a gate rather than the control itself: the app installation capabilities are withheld from roles and the instance's access to the remote applications repository is denied.

*Citation.* Search of all 128 files of the shipped specification set for the pattern '\\bsign(ed|ing|ature)?\\b', case-insensitive, returns 56 matching lines; every one concerns TLS certificate signing, remote-storage request signing, SmartStore checksum signature algorithms, or the fschange signed-audit event stream. None concerns verification of a package or module signature at install time. Gating settings cited for the assessment: authorize.conf.spec:760 ([capability::install_apps]), authorize.conf.spec:589 ([capability::edit_local_apps]), server.conf.spec:1727-1735 ([applicationsManagement] allowInternetAccess).

*Providing baseline.* The organization's software review, test and change control process, supported by the host operating system package management baseline for signature verification of vendor packages

*Artifact.* Documented app and add-on review, test and approval record for each Splunk app or add-on admitted to a production instance, maintained under the system's configuration management plan with change control authorization, plus the designation of the reviewing authority.

*Assessment method.* Examine the app and add-on review, test and approval records against the inventory of installed apps. Run, as the Splunk service account: splunk btool authorize list --debug to enumerate roles holding install_apps, edit_local_apps and rest_apps_management; splunk btool server list applicationsManagement --debug to examine allowInternetAccess; splunk btool app list --debug to inventory installed apps.

**SRG-APP-000456-WSR-000187** — CAT II — Applicable, evidence grade C.

The web server must install security-relevant software updates within 30 days unless the time period is directed by an authoritative source (e.g., IAVM, CTOs, DTMs, STIGs).

*Basis.* Splunk Web is a component of the Splunk Enterprise installation and is not separately patchable; it is updated when the installation is replaced from a vendor-supplied package. The requirement's discussion anticipates a web server configured both to check for and to install security-relevant updates from an authoritative source. Splunk exposes the checking half only: web.conf updateCheckerBaseURL causes Splunk Web to contact the vendor for notice of new versions, and setting it to 0 stops that contact, which is the option taken where outbound vendor contact is not permitted. The product exposes no key that acquires, schedules or applies an update. Because the assessment objective is the installation of the update within a time period, and the product provides no mechanism for installation, the requirement is satisfied by a documented procedure and the upgrade record rather than by configuration. It is not inherited from the host operating system or the container platform, because the software being patched is the Splunk application itself.

*Citation.* web.conf.spec:192 updateCheckerBaseURL, documented as a configurable vendor URL that Splunk Web pings for new versions of Splunk software and that can be set to 0 to stop the ping - a notification control, not an installer; confirmed present and readable on a Splunk 10.4.2 instance (build 33c3bf42cd73) with splunk btool web list --debug. Searched all 67 .conf.spec files for install-an-update vocabulary: no key acquires or applies a Splunk Enterprise update. The remaining hits are app.conf.spec:116 show_upgrade_notification, app scope, and serverclass.conf.spec:316 updaterRunningFilter, which concerns deployment clients running a separately installed self-updater. The referenced rule SPLK-CL-000510 names no configuration setting - its fix text directs an upgrade to a vendor-supported version - so there is no 10.4.2 setting to re-confirm and stig_reference_status is recorded as no_reference.

*Artifact.* The organization's flaw remediation procedure covering the Splunk Web component of Splunk Enterprise, naming the authoritative source monitored and the installation time period, together with the configuration management record of upgrades performed and evidence that the installed version remains on the vendor's supported release list.

*Assessment method.* Run splunk version as the Splunk service account to record the installed version and build and compare it against the vendor's supported release list. Run splunk btool web list --debug and examine updateCheckerBaseURL to record whether vendor notification is in use or deliberately turned off, which determines which authoritative source the procedure must monitor. Examine the flaw remediation procedure and the configuration management record of upgrades for the installation time period actually met.

*Product reference.* SPLK-CL-000510 — no reference

**SRG-APP-000830-AU-000290** — CAT II — Applicable, evidence grade D.

The Central Log Server must for password-based authentication, maintain a list of commonly used, expected, or compromised passwords on an organization-defined frequency.

*Basis.* Maintaining a list of commonly used, expected or compromised passwords is a records-keeping obligation, and the Splunk configuration surface provides nowhere to hold or reference such a list. The determination is met by the organization's list and its maintenance record rather than by a setting, so the artifact is the evidence.

*Citation.* Enumeration of every declared key containing 'password' across the 71 specification files - grep -h -o -E '^[A-Za-z_][A-Za-z0-9_.<>-]* *=' *.spec | grep -i password | sort -u - returns 22 keys. Ten are the authentication.conf password policy and hashing settings at authentication.conf.spec:441-561; the remainder are credential-holding fields such as bindDNpassword and sslPassword. None is a deny list, dictionary or screening reference.

*Artifact.* The organization's list of commonly used, expected and compromised passwords, with its maintenance record, held under the system's identification and authentication policy.

*Assessment method.* Examine the organization's password deny list and its maintenance record, and confirm the maintenance frequency is defined in the identification and authentication policy. No instance command gathers this, as the product exposes no corresponding setting.

**SRG-APP-000830-WSR-000190** — CAT II — Applicable, evidence grade D.

The web server must, for password-based authentication, maintain a list of commonly used, expected, or compromised passwords on an organization-defined frequency.

*Basis.* Splunk Web holds no credential store and no password policy settings of its own, so it can hold no deny list either; the obligation to maintain the list rests on the organization and is evidenced by the list and its maintenance record.

*Citation.* grep -c -E '^(minPassword|expirePassword|passwordHistory|passwordHash|enablePasswordHistory|forceWeakPassword)' web.conf.spec returns 0. The enumeration of all 22 declared keys containing 'password' across the 71 specification files returns no deny list, dictionary or screening reference in web.conf.spec or any other file.

*Artifact.* The organization's list of commonly used, expected and compromised passwords, with its maintenance record, held under the system's identification and authentication policy.

*Assessment method.* Examine the organization's password deny list and its maintenance record; confirm that web-tier authentication is delegated to the splunkd authentication system rather than to a separate credential store, by splunk btool authentication list --debug for authType.

**SRG-APP-000835-AU-000300** — CAT II — Applicable, evidence grade D.

The Central Log Server must for password-based authentication, update the list of passwords on an organization-defined frequency.

*Basis.* Updating the password deny list at a defined frequency is a maintenance action on an organizational record, and the product exposes no setting that holds a list or schedules its revision. The artifact and its revision history are the evidence.

*Citation.* The enumeration of all 22 declared keys containing 'password' across the 71 specification files returns no deny list or screening key, and no scheduling key associated with one. The only time-based password settings are authentication.conf.spec:487 expirePasswordDays and :495 expireAlertDays, both of which govern expiry of a user's own password rather than revision of a list.

*Artifact.* The password deny list's revision history and review record, showing updates at the organization-defined frequency.

*Assessment method.* Examine the deny list's revision history against the frequency defined in the identification and authentication policy. No instance command gathers this.

**SRG-APP-000835-WSR-000200** — CAT II — Applicable, evidence grade D.

The web server must, for password-based authentication, update the list of passwords on an organization-defined frequency.

*Basis.* The web tier holds no password policy settings and therefore no list to update; the revision obligation rests on the organization and is evidenced by the list's review record.

*Citation.* grep -c -E '^(minPassword|expirePassword|passwordHistory|passwordHash|enablePasswordHistory|forceWeakPassword)' web.conf.spec returns 0; the enumeration of all 22 password-named keys across the 71 specification files returns no deny list or scheduling key in any file.

*Artifact.* The password deny list's revision history and review record, showing updates at the organization-defined frequency.

*Assessment method.* Examine the deny list's revision history against that policy-defined frequency; confirm by splunk btool authentication list --debug for authType that the web tier authenticates through the splunkd authentication system.

**SRG-APP-000840-AU-000310** — CAT II — Applicable, evidence grade D.

The Central Log Server must for password-based authentication, update the list of passwords when organizational passwords are suspected to have been compromised directly or indirectly.

*Basis.* Updating the password deny list on suspicion of compromise is an incident-driven action on an organizational record, and the product exposes no setting that holds a list or responds to a compromise event. The procedure and the resulting revisions are the evidence.

*Citation.* The enumeration of all 22 declared keys containing 'password' across the 71 specification files returns no deny list or screening key. A sweep for compromise-driven password handling across the specification set returns no matching setting; the sole 'compromis' match in the set, at server.conf.spec:3173, concerns search performance during cluster manager restarts.

*Artifact.* The procedure tying password deny list revision to the incident response plan, with the revision records produced on suspected compromise.

*Assessment method.* Examine the incident response plan for the trigger that requires deny list revision, and sample revision records against recorded credential-compromise events. No instance command gathers this.

**SRG-APP-000840-WSR-000210** — CAT II — Applicable, evidence grade D.

The web server must, for password-based authentication, update the list of passwords when organizational passwords are suspected to have been compromised directly or indirectly.

*Basis.* The web tier holds no password policy settings and no list to revise; the compromise-driven revision obligation rests on the organization and is evidenced by the procedure and its records.

*Citation.* grep -c -E '^(minPassword|expirePassword|passwordHistory|passwordHash|enablePasswordHistory|forceWeakPassword)' web.conf.spec returns 0; the enumeration of all 22 password-named keys across the 71 specification files returns no deny list or compromise-response key in any file.

*Artifact.* The procedure tying password deny list revision to the incident response plan, with the revision records produced on suspected compromise.

*Assessment method.* Examine the incident response plan and sample deny list revision records against recorded credential-compromise events; confirm web-tier delegation by splunk btool authentication list --debug for authType.

**SRG-APP-000855-AU-000340** — CAT II — Applicable, evidence grade D.

The Central Log Server must for password-based authentication, require immediate selection of a new password upon account recovery.

*Basis.* The specification set declares no key that compels a password change at next logon following an account recovery action: forceWeakPasswordChange is triggered by password weakness rather than by recovery, and expirePasswordDays counts whole days from a reset, so neither produces immediate re-selection. The objective is met by the documented recovery procedure in which a single-use credential is issued and replaced by the account holder at first use.

*Citation.* authentication.conf.spec:509 forceWeakPasswordChange specifies whether users must change a weak password; :487 expirePasswordDays specifies the number of days before the password expires after a reset. A sweep for a recovery-triggered forced change - grep -n -i -E '(force|must|require).{0,25}(change|reset|select).{0,25}password' across the specification set - returns only those two settings. User-seed.conf.spec sets only the initial credential and is ignored once a credential store exists.

*Artifact.* The account management and password reset procedure, specifying issuance of a single-use credential and its immediate replacement by the account holder at first use, with the recovery records it produces.

*Assessment method.* Examine the account recovery procedure and a sample of recovery records for evidence that replacement was required at first use; splunk btool authentication list --debug for [splunk_auth] forceWeakPasswordChange and expirePasswordDays as supporting configuration.

**SRG-APP-000855-WSR-000240** — CAT II — Applicable, evidence grade D.

The web server must, for password-based authentication, require immediate selection of a new password upon account recovery.

*Basis.* The web tier has no credential lifecycle of its own and the specification set declares no recovery-triggered forced change key anywhere, so the objective is met by the documented recovery procedure rather than by configuration.

*Citation.* grep -c -E '^(minPassword|expirePassword|passwordHistory|passwordHash|enablePasswordHistory|forceWeakPassword)' web.conf.spec returns 0. The sweep for a recovery-triggered forced change across the specification set returns only authentication.conf.spec:509 forceWeakPasswordChange, keyed to password weakness, and :487 expirePasswordDays, which counts whole days from a reset.

*Artifact.* The account management and password reset procedure, specifying issuance of a single-use credential and its immediate replacement by the account holder at first use, with the recovery records it produces.

*Assessment method.* Examine the account recovery procedure and a sample of recovery records; confirm web-tier delegation by splunk btool authentication list --debug for authType, and examine [splunk_auth] forceWeakPasswordChange as supporting configuration.

**SRG-APP-000865-AU-000360** — CAT II — Applicable, evidence grade D.

The Central Log Server must for password-based authentication, employ automated tools to assist the user in selecting strong password authenticators.

*Basis.* The specification set exposes no password generator, strength indicator or selection aid; the minPassword* family rejects non-conforming candidates, which is enforcement rather than assistance in selection. The objective is met by an organization-approved password generation tool supplied to account holders, so the artifact is the evidence.

*Citation.* A sweep for selection assistance - grep -n -i -E 'password.{0,30}(generat|suggest|strength|meter|assist)' across the specification set - returns two incidental matches, neither a selection aid. The two near candidates are ruled out by inspection: web.conf.spec:1430 loginPasswordHint is static first-logon text whose default reads 'The password you created when you installed this instance', and web-features.conf.spec:246 enable_password_management_page_vnext selects a JavaScript library for rendering the password management page.

*Artifact.* The organization-approved password or passphrase generation tool and the procedure directing account holders to use it.

*Assessment method.* Examine the designated password generation tool and the procedure directing its use. No instance command gathers this, as the product exposes no corresponding setting.

**SRG-APP-000865-WSR-000260** — CAT II — Applicable, evidence grade D.

The web server must, for password-based authentication, employ automated tools to assist the user in selecting strong password authenticators.

*Basis.* The web tier offers no password generator or strength indicator, and the password management page it renders carries no selection aid declared anywhere in the specification set. The objective is met by an organization-approved password generation tool, so the artifact is the evidence.

*Citation.* The sweep for selection assistance across the specification set returns no password generator, strength indicator or suggestion key. Web.conf.spec:1430 loginPasswordHint is static first-logon text, and web-features.conf.spec:246 enable_password_management_page_vnext selects only the JavaScript library used to render the password management page.

*Artifact.* The organization-approved password or passphrase generation tool and the procedure directing account holders to use it.

*Assessment method.* Examine the designated password generation tool and the procedure directing its use. No instance command gathers this, as the product exposes no corresponding setting.

**SRG-APP-000125-AU-000310** — CAT III — Applicable, evidence grade D.

The Central Log Server system backups must be retained for a minimum of 5 years for SAMI (Sources and Methods Information) and a minimum of 7 days for non-SAMI on media capable of guaranteeing file integrity for the minimum applicable information retention period.

*Basis.* Splunk takes no backups of itself and exposes no setting that selects backup media or sets a backup retention period; the executing baseline is the organization's enterprise backup and storage service, and the retention period and the SAMI determination are documentary. The in-product bound the documented period must be consistent with is the index retention setting.

*Citation.* indexes.conf.spec:684 frozenTimePeriodInSecs bounds in-product retention. A search of every .conf.spec file for backup and media settings returns only configuration-backup and log-rotation items: server.conf.spec:4447 [app_backup] backup_path (configuration backups), server.conf.spec:1680 [stderr_log_rotation] BackupIndex at :1694 (rolled log copies), limits.conf.spec:3596 version_upgrade_backup_disabled. No setting in the specification set governs backup media or a backup retention period for log records, and no setting matching a media parameter exists at all.

*Artifact.* The System Security Plan entry recording the log-record retention period and the SAMI determination, together with the backup media designation in the organization's backup procedure. The providing baseline is the organization's enterprise backup and storage service.

*Assessment method.* Examine the SSP retention entry, the SAMI determination and the backup media documentation; run `splunk btool indexes list --debug` and record frozenTimePeriodInSecs for every index holding log records to confirm the in-product period is consistent with the documented retention period.

*Product reference.* SPLK-CL-000250 — no reference

\newpage

### Undetermined

**SRG-APP-000251-WSR-000195** — CAT II — Undetermined, evidence grade E.

The web server must terminate the connection if server-level exceptions are triggered when handling requests to prevent HTTP request smuggling attacks.

*Basis.* This requirement concerns the behavior of the HTTP server when an exception is raised during request handling - whether the connection is torn down - not the disclosure of that exception, which is a separate requirement. Splunk Enterprise exposes no configuration governing connection termination on an exception. Enumerating every setting in the Splunk instance.conf [httpServer] stanza returns 26 keys, none of which addresses exception handling or conditions a close on an error. The nearest keys in web.conf [settings] govern disclosure (request.show_tracebacks), application server process lifetime (appServerProcessShutdownTimeout) and timeouts (response.timeout, server.socket_timeout); none of them conditions connection termination on a server-level exception. Absence of a setting is not absence of the behavior: whether the splunkd HTTP server and the Python application server close the socket rather than return it to the keep-alive pool on a 5xx is internal, non-configurable behavior, and the specification set documents configuration only. Applicability therefore cannot be established by examination and requires a test, so this is recorded as undetermined rather than guessed in either direction.

*Citation.* Enumerated the full server.conf [httpServer] stanza, server.conf.spec:1298 through 1591, 26 keys: no exception-handling or connection-termination setting. Searched all 67 .conf.spec files for an exception- or error-conditioned close, terminate or disconnect, and separately for 5xx, HTTP 500 and status code: zero hits. The only related keys are disclosure and timeout controls - web.conf.spec:910 request.show_tracebacks, web.conf.spec:1278 appServerProcessShutdownTimeout, web.conf.spec:971 response.timeout - none of which implements the requirement.

*Assessment method.* Test rather than examine. Against each Splunk HTTP listener in scope (management and REST port, Splunk Web, HTTP Event Collector), send requests that force a server-side exception and capture the full exchange, for example curl -sv --http1.1 against the listener together with a packet capture, and determine whether the response carries Connection: close and whether the TCP connection is torn down rather than reused. That test settles applicability: if the teardown behavior is fixed in the product and not configurable, record the determination against the product rather than against a setting.

\newpage

