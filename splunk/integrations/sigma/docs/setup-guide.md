# Setting up the Sigma rule analyzer

Six steps. The first three are checks, and if they all pass the install is
two commands.

## Before you start

You need a Splunk Enterprise instance where you can install an app and
restart splunkd, and Windows or Linux logs already arriving through the
official Splunk add-ons. Nothing is installed on the endpoints.

## 1. Confirm the logs are already arriving

The analyzer reads what the add-ons collect. If that is not happening, the
rules have nothing to match.

```bash
index=* sourcetype IN ("XmlWinEventLog:*", "linux_audit", "linux_secure") | stats count by sourcetype index
```

Note the index names. You will need them in step 4.

Nothing back means the collection side is the problem, not this integration.
`../../lib/discover.sh --target <your target> --inputs` reports what an
instance is set up to receive and names what is missing.

## 2. Confirm the add-ons are installed

```bash
| rest /services/apps/local | search title IN ("Splunk_TA_windows","Splunk_TA_nix") | table title, version, disabled
```

The add-ons do the parsing and CIM normalization. Without them the fields
Sigma rules match on will not exist, and rules will convert cleanly and
never fire.

## 3. Know which source types you actually have

Sigma rules are written against log sources, and a rule whose source type is
absent can never fire. This is the single most common reason a deployment
looks broken when it is not.

```bash
index=* | stats count by sourcetype | sort - count
```

Windows process-creation rules, the largest group, need Sysmon event ID 1 —
either `XmlWinEventLog:Microsoft-Windows-Sysmon/Operational`, or Security
`4688` with command line auditing enabled. Linux auditd rules need
`linux_audit` from a file monitor on `audit.log`, and an audit policy that
logs `execve`. Without that policy the log contains almost nothing a rule
matches.

## 4. Get the rules and build the package

On a machine with internet access:

```bash
python3 -m pip install --target ./pylib -r requirements.txt
```

```bash
python3 fetch-rules.py --package core --out ./rules-core
```

```bash
./bin/package-app.sh --rules ./rules-core/SigmaHQ_sigma/core/rules/windows/process_creation --pipeline windows
```

That writes `dist/sigma_detection_lab-<version>.spl` with the converted
rules already inside it, and verifies every conf and view parses before
packaging.

For an air-gapped environment, fetch on a connected host and carry one file
in:

```bash
python3 fetch-rules.py --package core --make-bundle sigma-rules.tar.gz
```

Move `sigma-rules.tar.gz` and its `.sha256` sidecar, then on the inside:

```bash
python3 fetch-rules.py --from-bundle sigma-rules.tar.gz --out ./rules-core
```

The install path never touches the network and verifies each artifact's
checksum before extracting.

## 5. Install it

Splunk Web: **Apps → Manage Apps → Install app from file**, choose the
`.spl`, then restart when prompted.

Or from the command line:

```bash
splunk install app dist/sigma_detection_lab-0.1.0.spl -auth <user>:<password>
```

```bash
splunk restart
```

The app brings its own `sigma_alerts` index, so nothing has to be created
first.

## 6. Point it at your indexes, and let it run

The app searches whatever `sigma_lab_index` resolves to. Set it to the
indexes holding your Windows and Linux logs, from step 1.

**Settings → Advanced search → Search macros → `sigma_lab_index`**, or
in `$SPLUNK_HOME/etc/apps/sigma_detection_lab/local/macros.conf`:

```ini
[sigma_lab_index]
definition = index=wineventlog OR index=linux
```

Saved searches arrive enabled on a ten-minute schedule. The first detections
appear within about ten minutes of a matching event.

Then open **Sigma Detection Lab → Detection Coverage**.

## Checking it works

```bash
index=sigma_alerts sourcetype=sigma:alert | stats count by sigma_rule, sigma_level
```

Nothing back, after the schedule has run, usually means one of:

| Symptom | Cause |
|---|---|
| no detections at all | the source types the rules need are not in your data — step 3 |
| searches error on dispatch | the macro points at an index that does not exist — step 6 |
| detections but no drilldown | an older package without the `sigma_src_*` fields |
| scheduler deferring runs | more scheduled searches than the instance's concurrency allows. `bin/preflight.py` reports this before deploying; `bin/check-instance.sh` reports it on the instance. Rules are batched precisely so this does not happen, so a recurrence usually means the cadence was tightened |

## Tuning

Start with fewer rules. `--rules` takes any directory, so a first deployment
can be one category:

```bash
./bin/package-app.sh --rules ./rules-core/SigmaHQ_sigma/core/rules/windows/process_creation/proc_creation_win_powershell
```

A rule that fires constantly on legitimate work is worse than no rule,
because it trains people to ignore the whole app. Disable it in
`local/savedsearches.conf` rather than editing the packaged file, so a
reinstall does not bring it back:

```ini
[Sigma - <rule title> (<id prefix>)]
disabled = 1
```

## What it does not do

It does not install anything on endpoints, change how the add-ons parse, or
alter your existing indexes. It reads them and writes to its own.
