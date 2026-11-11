# Sigma to Splunk alert integration

Converts Sigma detection rules into a Splunk `savedsearches.conf`.

Read this section first: **the conversion works and is tested. Whether any
converted rule would ever fire is unproven, and on the current lab instance
the answer is no.** Those are different claims and the rest of this file
keeps them apart.

## Status

| Item | State | Basis |
|---|---|---|
| Rule conversion to SPL | Works | Tested on 385 real SigmaHQ rules |
| Generated conf is valid | Works | 385 stanzas, 0 parse errors, 0 unknown keys, offline validator |
| Linux log source mapping | Written, unproven | `pipelines/splunk-linux.yml`, never run against data |
| Searches return results | Unproven | Requires a data source no lab container produces |
| CIM data model queries | Partly blocked | 121 of 211 Linux rules convert; the data models are absent from the lab |
| Offline rule delivery | Not built | Design only, see "Air-gapped delivery" |

## What this changed on the instance

Nothing. The relaxation that would have allowed installing `Splunk_TA_nix`
was withdrawn before any instance work began.

| Measure | Before | After |
|---|---|---|
| `btool check` output | 0 lines, exit 0 | 0 lines, identical |
| Apps in `etc/apps` | 37 | 37, list identical |
| Indexes | 20 | 20, list identical |
| `savedsearches` stanzas | 182 | 182, `btool list` output identical |
| splunkd restarts | — | none |
| App directories created | — | none |
| Indexes created | — | none |

Interaction with `epo-uat-indexer` was read-only throughout: `btool check`,
`btool list`, and `cat` of `savedsearches.conf.spec` and nine stock
`savedsearches.conf` files. Nothing was written into any container. The
`stig-viewer` container that appeared during this work is not ours.

## How to run it

Install the dependencies. Conversion runs on pySigma; the `sigmac` binary
the original script called is retired and is not on any package index.

```bash
python3 -m pip install --target ./pylib -r requirements.txt
```

Convert a directory of Sigma rules:

```bash
PYTHONPATH=./pylib ./sigma2splunkalert.py /path/to/rules --pipeline pipelines/splunk-linux.yml -o savedsearches.conf
```

Validate the output without touching a Splunk instance:

```bash
podman exec -u splunk epo-uat-indexer cat /opt/splunk/etc/system/README/savedsearches.conf.spec > spec.txt
```

```bash
python3 bin/validate-savedsearches.py savedsearches.conf spec.txt
```

`--pipeline` takes a built-in name (`none`, `cim`, `windows`,
`sysmon_acceleration`) or a YAML pipeline file. `--output-format` takes
`default`, `data_model` or `savedsearches`. Network sources are refused
unless `--allow-network` is passed.

## Proven by test

Measured on 385 real SigmaHQ rules fetched for this evaluation: 211 Linux,
120 Windows, 54 network.

The script as written could not run. Three independent failures, each
reached by satisfying the previous one:

| Failure | Location | Detail |
|---|---|---|
| `ModuleNotFoundError: No module named 'git'` | line 16 | GitPython imported at module scope, absent from the host |
| `FileNotFoundError: 'sigmac'` | `convertSigmaRule` | the retired converter binary, not installed and not installable |
| `TemplateNotFound: 'savedsearches.conf.j2' ... search path: 'templates'` | `generate_savedsearches_conf` | `FileSystemLoader('templates')`, but the template sits beside the script |

Default argument paths were also wrong: `config/config.yml` and
`sigma_config/splunk-all.yml` against actual files `config.yaml` and
`splunk-all.yml`.

Rendering the original template against a real Sigma rule produced **six
malformed lines per stanza**, confirmed by the offline validator:

```
line 10  NOT A KEY=VALUE LINE: MITRE Techniques: attack.t1083, attack.t1548 \
line 11  NOT A KEY=VALUE LINE: MITRE Tactics: attack.discovery, attack.privilege-escalation
line 12  NOT A KEY=VALUE LINE: title: Linux Capabilities Discovery
line 13  NOT A KEY=VALUE LINE: description: Detects attempts to discover the files ...
line 14  NOT A KEY=VALUE LINE: tags: attack.discovery, attack.privilege-escalation, ...
line 15  NOT A KEY=VALUE LINE: level: low
```

Two distinct causes. The `action.email.message.alert` value used backslash
continuation across a Jinja `{% for %}` loop over `rule.fields`; most Sigma
rules have no `fields:` key, so the loop emitted a blank line, which ended
the continuation early and spilled the MITRE lines out as their own
malformed lines. Separately, `title:`, `description:`, `tags:` and `level:`
were written with colons rather than `key = value`.

`mapToCIMDatamodel` returned `None` for every real rule. It intersected the
`datamodels` tags in `splunk-all.yml` (`authentication`, `endpoint`) with
Sigma rule tags, which are ATT&CK identifiers (`attack.discovery`,
`attack.t1083`). The two sets never intersect, so `action.datamodel` never
emitted and the whole CIM feature was dead code.

`action.datamodel` would not have worked anyway. It is syntactically
accepted — the spec's generic `action.<action_name>.<parameter>` wildcard
covers it — but there is no alert action named `datamodel`, so it is a
silent no-op, not a `btool` error.

The pySigma Splunk backend ships **no Linux pipeline**: only
`splunk_windows`, `splunk_sysmon_acceleration` and `splunk_cim`. Measured
over the 211 Linux rules:

| Pipeline | Output format | Converted | Note |
|---|---|---|---|
| none | default | 211 / 211 | no index or sourcetype scoping at all |
| none | data_model | 0 / 211 | `No data model specified by processing pipeline` |
| cim | default / data_model / savedsearches | 121 / 211 | 88 `Rule type not yet supported by the Splunk data model CIM pipeline`, 2 field-whitelist rejections |
| windows | default | 211 / 211 | identical to `none`; the Windows pipeline is a no-op for Linux log sources |
| `pipelines/splunk-linux.yml` | default | 211 / 211 | written here, maps log source to sourcetype |

pySigma emits **multi-line SPL** for 7 of 211 Linux rules — those needing
`| rex` or `| regex` stages. Written straight into `search =` that produced
18 malformed lines. Newlines are now folded to spaces before rendering.

After the fixes, on all 385 rules: 385 converted, 385 stanzas, 0 parse
errors, 0 unknown keys.

Raw auditd records on this host carry exactly the field names the 53 auditd
rules expect:

```
type=EXECVE msg=audit(1771796905.044:86129031): argc=3 a0="systemctl" a1="stop" a2="auditd.service"
```

But only 2 `EXECVE` records appeared in 20,000 lines against 614 `SYSCALL`,
because default audit policy does not log `execve`. `auditd` is installed
on this host and inactive.

Zero title collisions across all 385 rules, and no `[` or `]` in any title.
The original stanza naming (`[{{ rule.title }}]`) was therefore not an
immediate problem, but it ignored the Sigma `id`, which is the stable key.
Stanzas are now `Sigma - <title> (<id prefix>)`.

The validator was control-tested against nine real on-disk
`savedsearches.conf` files from the instance: 184 stanzas, 0 parse errors,
0 unknown keys. An earlier control against `btool list` output produced 878
false positives — `btool list` is a display format that prints multi-line
searches without continuations, so it is not a valid conf file and must not
be used as a control.

## Concluded by reading, not proven

The lab instance cannot run any of these searches usefully, and this is
read off the read-only inventory rather than by dispatching a search.

The 20 indexes are: `_audit _configtracker default _dm_summary _dsappevent
_dsclient _dsphonehome epo_all history _internal _introspection main
_metrics _metrics_rollup provider-family:hadoop splunklogger summary
_telemetry _thefishbucket volume:_splunk_summaries`.

`index=windows`, `index=unix` and `index=threat-hunting` do not exist.
Every log source in `splunk-all.yml` maps to `windows` or `unix`, and
`config.yaml` collected to `threat-hunting`. Searching a nonexistent index
returns zero results without erroring, which is the worst failure mode: it
looks like "no detections".

`Splunk_SA_CIM` is absent, so the `Authentication`, `Endpoint`,
`Network_Traffic`, `DNS` and `Change` data models do not exist on this
instance. All 121 CIM-convertible rules would error at dispatch.
`Threat_Detection`, named in `config.yaml` under
`datamodel_acceleration`, is not a CIM data model at all.

`splunk-all.yml` is legacy sigmac configuration. pySigma cannot read it —
it takes processing pipelines, a different format. Its `logsources` entries
also carry a `sourcetype:` key, which sigmac never recognized in a log
source, so the sourcetype would not have reached the SPL even under
sigmac. The file is retained as a written record; only its `datamodels`
section is read, and only to annotate stanzas.

`fetchRemoteSigmaRules` returned `os.path.join(temp_dir, 'sigma')` after
cloning. SigmaHQ/sigma puts rules in `rules/`, not `sigma/`, so that path
would not exist and `loadSigmaRules` would return an empty list — silently,
with no error. It now returns the clone root.

## Source-to-rule mapping, Linux

What the 211 Linux rules require, and whether the Splunk Add-on for Unix
and Linux can supply it. Source types and their CIM mappings are from
Splunk's own add-on documentation.

| Sigma log source | Rules | Detection fields | Source type needed | From `Splunk_TA_nix`? | CIM |
|---|---|---|---|---|---|
| `linux` / `process_creation` | 123 | `Image`, `CommandLine`, `ParentImage`, `ParentCommandLine`, `CurrentDirectory` | `sysmon:linux` | **No** | Endpoint |
| `linux` / `auditd` | 53 | `type`, `a0`–`a3`, `name`, `exe`, `SYSCALL` | `linux_audit` | Yes, with an audit policy | Authentication, Change |
| `linux`, no category | 15 | keyword-only | any Linux text source | Yes | — |
| `linux` / `file_event` | 8 | `TargetFilename`, `Image` | `sysmon:linux` | **No** (`fs_notification` is not field-compatible) | Endpoint |
| `linux` / `network_connection` | 5 | `DestinationHostname`, `DestinationIp`, `DestinationPort`, `Initiated` | `sysmon:linux` | **No** | Network_Traffic |
| `linux` / `syslog` | 2 | — | `syslog` | Yes | — |
| `linux` / `sshd` | 1 | — | `linux_secure` | Yes | Authentication, Network Sessions, Change |
| `linux` / `cron` | 1 | — | `cron` | Yes | — |
| `linux` / `clamav`, `guacamole`, `vsftpd` | 3 | — | application logs | No | — |

Two findings drive everything else.

**The largest group cannot be served by the Unix add-on.** No source type
in `Splunk_TA_nix` carries Sysmon-style process-creation events. `ps` is a
point-in-time snapshot mapped to Performance, not an event stream mapped to
Endpoint. The 123 `process_creation` rules — the only group pySigma's CIM
pipeline can convert — need Sysmon for Linux on the endpoint plus the
Splunk Add-on for Sysmon for Linux (`sysmon:linux`). Splunk lists that
add-on as not supported, and the older `sysmon_linux` alternative is
archived. For an air-gapped accredited environment that is a procurement
and sustainment problem, not a configuration one.

**The auditd group needs host policy beyond the add-on.** `linux_audit`
gives the right field shape, proven above, but only if `auditd` is running
with rules that log the syscalls the Sigma rules look for. Default policy
does not. These 53 rules need an `audit.rules` policy, for example
`-a always,exit -F arch=b64 -S execve -k exec`. That is a host
configuration change, outside the add-on and outside Splunk.

Note also that `linux_audit` maps to Authentication and Change, **not** to
Endpoint.Processes. So even with auditd data flowing, auditd `EXECVE`
records will not populate the data model the `process_creation` rules
target. The two Linux groups do not converge on one data model.

The logic translates to Windows and Cisco with one caveat each. Windows is
the case pySigma's pipelines were built for, and `splunk_windows` supplies
real log source conditions, so Windows Security and Sysmon rules should
convert and scope correctly. Cisco network rules in `rules/network/` are
largely vendor-agnostic and keyword-shaped; they need a syslog source type
per platform, and pySigma ships no network pipeline for Splunk, so they
would need the same hand-written pipeline treatment as Linux.

## Test plan for when the instance is released

Executable as written. Record every measurement; the assessment effort
re-runs against the result.

1. **Capture before-state.** Four commands, output kept.

```bash
podman exec -u splunk epo-uat-indexer /opt/splunk/bin/splunk btool check > before-btool.txt 2>&1
```

   Also `ls -1 /opt/splunk/etc/apps`, `btool indexes list`, and
   `btool savedsearches list`. `btool check` has no per-conf form — `btool
   savedsearches check` is an invalid command on 10.4.2 — and it exits 0
   even when it reports errors, so compare the text, never the status.

2. **Create the index.** `index=linux_lab` in a new app
   `etc/apps/sigma_lab_indexes/local/indexes.conf` on `epo-uat-indexer`.
   Never `etc/system/local`.

3. **Install `Splunk_TA_nix` on `epo-uat-uf`** for collection. Enable only
   the file-monitor inputs: `/var/log/auth.log` as `linux_secure` and
   `/var/log/audit/audit.log` as `linux_audit`. Leave the scripted inputs
   off — they are polling load and none of them feeds a Sigma rule.
   Splunkbase requires authentication to download, so the package has to be
   supplied rather than fetched; that is the one step this plan cannot
   self-serve.

4. **Install the TA's parsing half on `epo-uat-indexer`**: `props.conf` and
   `transforms.conf` only, as an app under `etc/apps/`.

5. **Enable auditd execve logging** on whatever host generates the data:
   `-a always,exit -F arch=b64 -S execve -k exec`. Without this the 53
   auditd rules have nothing to match. This is a host change and belongs in
   a deploy script, not in a test.

6. **Confirm data is flowing** before testing anything:
   `splunk search 'index=linux_lab sourcetype=linux_audit type=EXECVE | head 5'`.
   Note that `splunk search 'search ...'` double-prefixes and returns zero
   results, and `-output rawdata` fails on searches producing stats.

7. **Measure, for the 53 auditd rules**: how many dispatch without error,
   how many return results, and for those returning nothing, whether the
   source is absent or the conversion is wrong. That last split is the
   point of the exercise. Expect the 123 `process_creation` rules to return
   nothing — they need `sysmon:linux`, which this plan does not install.

8. **Capture after-state** with the same four commands and diff. Report the
   `btool check` delta with the text of any new error, every app directory
   created and on which container, every index created, and whether
   splunkd was restarted.

Validation of generated conf does **not** need the instance. Use
`bin/validate-savedsearches.py` with a copy of the target version's spec.
If a `btool` check against a real instance is wanted later, copy the conf
into a throwaway app such as `etc/apps/sigma_validate_tmp/local/`, run
`btool check`, parse the output, and remove the directory.

## Design assessment

**Shape.** Not a container stack. This is a build-time transform: Sigma
YAML in, one conf file out, no service, no port, no state. A container adds
an image to maintain and buys nothing. It is also not really a Splunk app —
the *output* belongs in an app (`sigma_hunting_app`), but the converter has
no business running inside a Splunk instance. Keep it as a script in this
repo, run in CI or by an operator, emitting an app directory that ships as
an artifact. The one thing worth containerising is the Python environment,
because pySigma pulls a dependency tree you do not want on an indexer.

A larger point: pySigma's Splunk backend already has a `savedsearches`
output format. Much of what this script does, it does less well than the
library it now calls. The script's remaining justification is the
surrounding policy — scheduling, severity mapping, alert actions, stanza
naming — not the conversion.

**Datamodel acceleration and summary indexing should not be defaults, and
both are now off.** Acceleration builds and maintains a tsidx summary per
bucket per data model; on a busy indexer that is continuous background
CPU and disk, commonly 10–30% added index-time overhead and a summary that
can approach the size of the raw data. Turning it on for an invented data
model named `Threat_Detection` costs that for nothing. Summary indexing has
a subtler problem: `| collect` runs on *every* scheduled execution, so a
rule firing every 10 minutes writes 144 times a day per rule, and the
written events are then themselves indexed and licensed. Neither belongs on
until someone has decided they want it and the target exists.

**500 rules on a 10-minute cron with an email action each.** 500 searches
every 10 minutes is 72,000 dispatches a day, against a default concurrency
limit of roughly `max_searches_per_cpu * cpus + 2`. On a modest indexer
that is a few dozen concurrent slots, so the scheduler skips and lags, and
skipped searches on a `-10m` window with no overlap silently lose
detection coverage. The emails are worse: no `alert.suppress`, so a
persistent condition emails every 10 minutes per matching rule, which is
how a detection pipeline gets muted by its recipients in week one. If 500
rules are the goal, the answers are staggered cron, severity-tiered
schedules, `alert.suppress` with a sensible `alert.suppress.period`, and a
single notification path — a summary index or ES notable — rather than
500 independent mail senders. The current defaults ship with email off for
this reason.

**Air-gapped delivery.** `fetchRemoteSigmaRules` cloning from github.com at
run time is not deployable to the target environment; stated plainly, that
code path is dead there. Network sources now require `--allow-network` so
this fails loudly rather than hanging on a DNS timeout. The delivery path
that works is to move the artifact, not the source: on a connected host,
clone SigmaHQ at a pinned tag, convert, and emit a versioned app directory;
sign it; carry it in on media; and on the inside, verify the signature and
drop the app in. Converting outside also means pySigma and its dependency
tree never need to exist on the air-gapped side. The rule corpus becomes a
reviewed, versioned artifact with a known provenance, which is what an
accredited environment wants anyway — rules appearing from a `git clone`
would not survive a change-control review.

## Parked

- **Nothing runs against live data.** No search in any generated conf has
  been dispatched. Everything under "Proven by test" is conversion and
  conf-validity; everything about whether a rule fires is unproven.
- **`Splunk_TA_nix` was not obtained.** Splunkbase requires authentication.
  The package has to be supplied.
- **`sysmon:linux` is unverified.** The source type name is from Splunk's
  documentation, not from a running instance, and the add-on that produces
  it is listed as not supported. `pipelines/splunk-linux.yml` maps
  `process_creation`, `file_event` and `network_connection` to it on that
  basis alone.
- **`pipelines/splunk-linux.yml` maps source type only, not index.** This
  is deliberate — a hardcoded nonexistent index returns zero results
  silently — but it means generated searches are index-unscoped and will
  search everything the running user can see. Scoping is left to the
  caller and is not yet wired into `config.yaml`.
- **No `rules/network/` pipeline.** The 54 network rules convert
  unscoped. Cisco source type mapping is not written.
