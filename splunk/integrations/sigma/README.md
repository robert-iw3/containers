# Sigma rule analyzer for Splunk

A lightweight Sigma rule analyzer that runs inside Splunk. It takes the
Windows and Linux logs the official Splunk add-ons already collect, matches
them against Sigma detection rules, and writes what matched as a detection
event you can search, report on, and pivot from back to the log that
triggered it.

Nothing else has to be installed on the endpoints. If the Splunk Add-on for
Microsoft Windows or the Splunk Add-on for Unix and Linux is already
collecting, the data needed is already arriving.

## At a glance

![Components and data flow](docs/sigma-analyzer-dataflow.svg)

| | |
|---|---|
| **What it reads** | the Windows and Linux logs the official Splunk add-ons already collect, in the indexes they already sit in |
| **What it does** | runs each Sigma rule as a scheduled search against those logs |
| **What it writes** | one detection event per match, into its own `sigma_alerts` index, carrying the rule, its severity, its ATT&CK mapping, and where the matching log came from |
| **What you open** | the `sigma_detection_lab` app: tiles first, then detail, then the original event |
| **What it installs on endpoints** | nothing |

Set it up in six steps: [docs/setup-guide.md](docs/setup-guide.md).
Build an installable package with [`bin/package-app.sh`](bin/package-app.sh).

## How it works

```
Windows / Linux hosts
        |  official Splunk add-ons collect, parse and CIM-normalize
        v
    raw index
        |  converted Sigma rules run on a schedule
        v
  sigma_alerts index          one detection event per match, carrying the
        |                     rule's identity, severity and ATT&CK mapping
        v                     next to the fields of the log that matched
  sigma_detection_lab app     tiles, then detail, then the source events
```

Four pieces:

| Piece | What it does |
|---|---|
| `fetch-rules.py` | Pulls Sigma rules from SigmaHQ's published releases, with provenance and an offline bundle path |
| `sigma2splunkalert.py` | Converts rules to SPL with pySigma and emits `savedsearches.conf` |
| `pipelines/` | Maps Sigma log sources onto the source types the add-ons actually produce |
| `app/sigma_detection_lab/` | The Splunk app: the detection index, and dashboards to read it |

The detection event is what makes this usable rather than just noisy. Each
rule's search ends by recording which rule fired, how severe it is, which
ATT&CK techniques it covers, and where the matching event came from, then
writing that into `sigma_alerts`. Retention there can outlast the raw data,
a dashboard reads a small index instead of scanning everything, and the
trail back to the original Windows or Linux event survives.

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

