# Trellix Malware Analysis

Publisher: Splunk Community \
Connector Version: 1.0.3 \
Product Vendor: Trellix \
Product Name: Malware Analysis \
Minimum Product Version: 5.4.0

This app provides connectivity to the Trellix Advanced Malware Analysis tool

### Configuration variables

This table lists the configuration variables required to operate Trellix Malware Analysis. These variables are specified when configuring a Malware Analysis asset in Splunk SOAR.

VARIABLE | REQUIRED | TYPE | DESCRIPTION
-------- | -------- | ---- | -----------
**base_url** | required | string | Base URL for the console, i.e., https://<console IP or FQDN> |
**username** | required | string | Username to log into the console |
**password** | required | password | Password for the username |

### Supported Actions

[test connectivity](#action-test-connectivity) - Validate the asset configuration for connectivity using supplied configuration \
[get profiles](#action-get-profiles) - Return available operating system profiles from Trellix console \
[detonate file](#action-detonate-file) - Run a file in the sandbox and retrieve the analysis results \
[detonate url](#action-detonate-url) - Run a URL in the sandbox \
[get report](#action-get-report) - Get results of an already completed detonation \
[save artifacts](#action-save-artifacts) - Save a ZIP file of the detonation report to the Vault \
[get status](#action-get-status) - Gets the status of a detonation report

## action: 'test connectivity'

Validate the asset configuration for connectivity using supplied configuration

Type: **test** \
Read only: **True**

#### Action Parameters

No parameters are required for this action

#### Action Output

No Output

## action: 'get profiles'

Return available operating system profiles from Trellix console

Type: **generic** \
Read only: **False**

#### Action Parameters

No parameters are required for this action

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.data.\*.entity.sensors.\*.profiles.\*.name | string | | |
action_result.status | string | | |
action_result.message | string | | |
action_result.summary | string | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'detonate file'

Run a file in the sandbox and retrieve the analysis results

Type: **generic** \
Read only: **False**

Detonate a file in the AX console.

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**vault_id** | required | Vault ID of the file to detonate | string | `pe file` `pdf` `flash` `apk` `jar` `doc` `xls` `ppt` `vault id` |
**priority** | required | Sets the analysis priority, default is Normal | string | |
**analysis_type** | required | Specifies the analysis mode | string | |
**force** | optional | Perform an analysis on the file even if the file exactly matches an analysis that has already been performed on this file | boolean | |
**prefetch** | optional | Determine the file target based on an internal determination rather than browsing to the target location | boolean | |
**enable_vnc** | optional | Enable VNC while submitting on a Malware Analysis appliance, default is False | boolean | |
**profile** | required | Input the Malware Analysis profile to use for analysis | string | |
**custom_profile** | optional | Manually input the Malware Analysis profile to use for analysis. Please use get profiles action for available options | string | |
**application** | required | Specifies the ID of the application to be used for the analysis | string | |
**timeout** | required | Specifies the timeout period for the analysis in seconds | numeric | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.vault_id | string | `pe file` `pdf` `flash` `apk` `jar` `doc` `xls` `ppt` `vault id` | |
action_result.parameter.priority | string | | |
action_result.parameter.analysis_type | string | | |
action_result.parameter.force | boolean | | True False |
action_result.parameter.prefetch | boolean | | True False |
action_result.parameter.enable_vnc | boolean | | True False |
action_result.parameter.profile | string | | win7-sp1 |
action_result.parameter.custom_profile | string | | |
action_result.parameter.application | string | | Adobe Reader 10.0 |
action_result.parameter.timeout | numeric | | 1 |
action_result.data.\*.submission_details.\*.id | numeric | `fireeyeax submission id` | |
action_result.data.\*.submission_details.\*.uuid | string | `fireeyeax submission uuid` | |
action_result.data.\*.submission_details.\*.vnc_port | numeric | | 8080 |
action_result.data.\*.id | numeric | | |
action_result.status | string | | success failed |
action_result.message | string | | |
action_result.summary | string | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'detonate url'

Run a URL in the sandbox

Type: **generic** \
Read only: **False**

Detonate a URL in the AX console.

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**urls** | required | URL(s) to detonate. Comma-separated list allowed | string | `url` |
**priority** | required | Sets the analysis priority, default is Normal | string | |
**analysis_type** | required | Specifies the analysis mode | string | |
**force** | optional | Perform an analysis on the file even if the file exactly matches an analysis that has already been performed on this file | boolean | |
**prefetch** | optional | Determine the file target based on an internal determination rather than browsing to the target location | boolean | |
**enable_vnc** | optional | Enable VNC while submitting on a Malware Analysis appliance, default is False | boolean | |
**profile** | required | Input the Malware Analysis profile to use for analysis. Please use get profiles action for available options | string | |
**custom_profile** | optional | Manually input the Malware Analysis profile to use for analysis. Please use get profiles action for available options | string | |
**application** | required | Specifies the ID of the application to be used for the analysis | string | |
**timeout** | required | Specifies the timeout period for the analysis in seconds | numeric | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.urls | string | `url` | |
action_result.parameter.priority | string | | |
action_result.parameter.analysis_type | string | | |
action_result.parameter.force | boolean | | True False |
action_result.parameter.prefetch | boolean | | True False |
action_result.parameter.enable_vnc | boolean | | True False |
action_result.parameter.profile | string | | win7-sp1 |
action_result.parameter.custom_profile | string | | |
action_result.parameter.application | string | | Adobe Reader 10.0 |
action_result.parameter.timeout | numeric | | 1 |
action_result.data.\*.submission_details.\*.id | string | `fireeyeax submission id` | |
action_result.data.\*.submission_details.\*.job_ids | string | | |
action_result.data.\*.submission_details.\*.uuid | string | `fireeyeax submission uuid` | |
action_result.data.\*.submission_details.\*.vnc_port | numeric | | 8080 |
action_result.data.\*.id | numeric | | |
action_result.status | string | | success failed |
action_result.message | string | | |
action_result.summary | string | | |
summary.total_objects | numeric | | |
summary.total_objects_successful | numeric | | |

## action: 'get report'

Get results of an already completed detonation

Type: **investigate** \
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**id** | required | Detonation ID to get the report of | string | `fireeyeax submission id` |
**extended** | optional | Get additional information from the console about this report | boolean | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.id | string | `fireeyeax submission id` | |
action_result.parameter.extended | boolean | | True False |
action_result.data.\*.alert.\*.malicious | string | | |
action_result.data.\*.alert.\*.severity | string | | |
action_result.data.\*.alert.\*.uuid | string | `fireeyeax submission uuid` | |
action_result.status | string | | success failed |
action_result.message | string | | |
action_result.summary | string | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |
action_result.status | string | | success failed |
action_result.data.\*.alert.\*.malicious | string | | |
action_result.data.\*.alert.\*.explanation.malwareDetected.malware.\*.sha256 | string | | |
action_result.data.\*.alert.\*.explanation.malwareDetected.malware.1.original | string | | |

## action: 'save artifacts'

Save a ZIP file of the detonation report to the Vault

Type: **investigate** \
Read only: **True**

This action downloads all the malware artifacts from a detonation as a ZIP file and adds that file to the vault.

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**uuid** | required | UUID of detonation to get the results of | string | `fireeyeax submission uuid` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.uuid | string | `fireeyeax submission uuid` | |
action_result.data | string | | |
action_result.status | string | | success failed |
action_result.message | string | | |
action_result.summary | string | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'get status'

Gets the status of a detonation report

Type: **investigate** \
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**id** | required | Submission ID of the detonation report to get the status of | string | `fireeyeax submission id` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.id | string | `fireeyeax submission id` | 12345 |
action_result.data.\*.analysisStatus | string | | In Progress Done Submission not found |
action_result.data.\*.submissionStatus | string | | running done |
action_result.data.\*.verdict | string | | malicious non-malicious |
action_result.data.\*.submission_details.\*.vnc_port | numeric | | 8080 |
action_result.data.\*.submission_details.\*.job_ids | string | | |
action_result.data.\*.submission_details.\*.uuid | string | `fireeyeax submission uuid` | |
action_result.data.\*.submission_details.\*.id | string | `fireeyeax submission id` | 12345 |
action_result.status | string | | success failed |
action_result.message | string | | |
action_result.summary | string | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

______________________________________________________________________

Auto-generated Splunk SOAR Connector documentation.

Copyright 2025 Splunk Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.
