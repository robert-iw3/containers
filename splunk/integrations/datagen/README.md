# datagen — Splunk test data generator

Produces realistic sample log data so you can build and test against a
Splunk environment you do not have.

The problem it solves is simple. Anything built on top of Splunk — an app, a
dashboard, a report, a detection rule — is built against data. Without the
data you cannot tell whether it works, and real production data is usually
the thing you are least able to copy onto a test system. This generates
data that looks and behaves like the real thing, in whatever volume you ask
for.

Two kinds of people need that:

- **Developers building something on Splunk** who need it to work in a
  customer environment they have never seen. Generate data of the right
  shape, then check that searches, dashboards, and detections actually hold
  up against it.
- **Engineers running Splunk** who need to test how much data a system can
  take, and that data arrives where it is supposed to.

It runs from a plain Python 3 install, or from Windows PowerShell, with
nothing to download first. Nothing about it is specific to one environment:
you describe what you want in a template, and it emits that.

This is a standalone tool. The Sigma detection work in
`../sigma/` happens to use it, but the generator knows nothing
about Sigma or any other consumer.

## Where the templates come from

Writing sample data by hand tests your guess at what the data looks like.
That guess is usually close enough to be misleading: a search can pass
against invented data and fail against the real thing.

Splunk add-ons already contain the answer. A technology add-on's
`props.conf` is the authoritative statement of what fields a source type
carries and how they are produced, so the templates are derived from it
rather than invented.

`ta-schema.py` reads an add-on and reports, per source type, which fields
must be present in the raw event, and which ones the add-on's knowledge
objects supply on top of them — field extractions, field transforms, field
aliases, calculated fields, and automatic lookups. Emit the raw fields and
the rest follow, through to CIM normalization.

## End to end

Five steps. Nothing here needs network access except step 1.

### 1. Get the add-on you are generating for

Download from Splunkbase and verify it. Example, the Unix and Linux add-on
(app 833):

```bash
sha256sum splunk-add-on-for-unix-and-linux_1034.spl
```

### 2. Extract it

```bash
mkdir -p ./ta && tar -xzf splunk-add-on-for-unix-and-linux_1034.spl -C ./ta
```

### 3. Learn what the add-on expects

```bash
python3 ta-schema.py --ta ./ta/Splunk_TA_nix --min-fields 3
```

For one source type in full, including renames and index-time extractions:

```bash
python3 ta-schema.py --ta ./ta/Splunk_TA_windows --sourcetype 'XmlWinEventLog:Security'
```

That prints the field inventory, the CIM tags the add-on applies, and two
settings worth knowing before you write a search:

| Output | Meaning |
|---|---|
| `RENAMED TO` | the add-on renames the source type at search time; a search on the original name returns no events |
| `INDEXED_EXTRACT` | index-time field extraction, so there are no search-time field extractions to read |
| `Raw event must carry` | fields your generated event needs |
| knowledge objects applied | fields the add-on supplies once the raw fields exist |

### 4. Generate

```bash
python3 datagen.py --tier small --out ./out --index my_test_index
```

Templates are validated first, and nothing is emitted while an error
stands. A typo in a template does not fail loudly on its own: an unknown
transform, or a placeholder naming a variable that was renamed, produces
output that looks plausible and is wrong, and the cost of finding out later
is a reindex. Validation reports the file, the location, and a likely
correction:

```
ERROR   win_security.json [variables.ts]
        unknown generator 'timestmap'
        hint: did you mean 'timestamp'?
```

Run it on its own while authoring a template:

```bash
python3 validate-templates.py --templates ./templates
```

On Windows, with no Python, from the same templates:

```powershell
.\datagen.ps1 -Tier small -Out .\out -Index my_test_index
```

Check the volume before committing to it:

```bash
python3 datagen.py --tier large --estimate-only
```

### 5. Collect it

The run writes an `inputs.conf` next to the data, with an explicit
`sourcetype` on every stanza. Copy it into an app on a forwarder:

```bash
cp ./out/inputs.conf /opt/splunkforwarder/etc/apps/my_test_inputs/local/inputs.conf
```

Then restart the forwarder as **its own service account**, which is not
always `splunk`:

```bash
stat -c '%U' /opt/splunkforwarder/var
```

The Splunk CLI chowns all of `SPLUNK_HOME` to whoever invokes it, so running
it as the wrong account leaves splunkd unable to write its pid file. This
cost us a forwarder outage; `../lib/discover.sh`
reports the account for a given endpoint.

## Knowing where the data will go

Data has to cross every hop between the generator and the index, and it can
stop at any of them. `../lib/discover.sh` reports the chain and what would
stop it:

```bash
../lib/discover.sh --target podman:splunk-uf --trace \
  --map 'hf01=podman:splunk-hf,idx01=podman:splunk-idx'
```

```
# Forwarding path, 3 hop(s). Data can stop at any of them.
#   1. podman:splunk-uf [forwarder] -> hf01:9997 indexAndForward=false
#   2. podman:splunk-hf [full] -> idx01:9997 indexAndForward=false
#   3. podman:splunk-idx [full] terminal, indexes locally
```

A hostname in `outputs.conf` is not a transport target and nothing on the
instance says how to reach it, so `--map` is where the operator supplies
that. Without it the trace stops at the first unmapped hop and says so.

`--inputs` reports what an instance can receive, and names anything that
would misfile or drop data: a receiver with no source type set, a `udp`
stanza still on the 1024-byte `maxEventSize` default, HEC enabled with no
token, a forwarder with no output server, and an input writing to an index
that does not exist on the indexer at the end of the path. That last one
cannot be seen from the forwarder alone, which is why the check runs against
the terminal hop.

Each finding is printed with what to do about it. None of it requires a
login, because it is read from configuration rather than searched.

## Volume and licensing

A download-trial or Free license indexes **500 MB/day**, and repeatedly
exceeding it disables search. Every run measures bytes before writing
anything, and `--budget-mb` (default 150) refuses to go past a ceiling.

Tiers are **record** counts, not event counts: one auditd execution is five
records (`SYSCALL`, `EXECVE`, `CWD`, `PATH`, `PROCTITLE`).

| Tier | Records | Measured size | Share of a 500 MB/day license |
|---|---|---|---|
| tiny | 200 | 0.05 MB | negligible |
| small | 2,000 | 0.45 MB | 0.1% |
| medium | 150,000 | 32.8 MB | 6.6% |
| large | 600,000 | 131.1 MB | 26% |

Sizes are from the committed templates; your own templates will differ.
`--records N` overrides the tier.

## Templates

One JSON file per source type in `templates/`. JSON because it is the only
format Python 3 and Windows PowerShell 5.1 both parse with no dependencies,
so both generators read the same files.

```json
{
  "name": "linux_secure",
  "sourcetype": "linux_secure",
  "origin": "Splunk Add-on for Unix and Linux (/var/log/secure)",
  "weight": 20,
  "variables": {
    "ts":   {"gen": "timestamp", "format": "iso8601"},
    "user": {"gen": "choice", "values": ["jdoe", "svc_deploy"]},
    "pid":  {"gen": "int", "min": 1000, "max": 60000}
  },
  "records": [
    {"weight": 8, "lines": ["{ts} {host} sshd[{pid}]: Failed password for {user}"]}
  ]
}
```

Variables resolve **once per record group**, so every line in a group
agrees — an auditd `audit()` id, a Sysmon `ProcessGuid`. `records` is
weighted, so one template can emit a realistic mix of event kinds.

### Generators

`const`, `choice` (with `weights`), `int`, `float`, `hex`, `ipv4`, `uuid`,
`guid_braced`, `sequence` (with `step`, `jitter`), `timestamp`,
`sha256_of`, `compose`.

`timestamp` formats: `epoch`, `epoch_ms3`, `iso8601`, `iso8601_z`,
`syslog_rfc3164`, `win_xml`, `strftime`.

### Transforms

Applied in a placeholder as `{var|transform|transform}`:

`hexify`, `audit_args`, `argc`, `join`, `join_comma`, `first`, `basename`,
`dirname`, `upper`, `lower`, `xml`, `abspath`.

`hexify` reproduces auditd's behavior of hex-encoding any value containing
whitespace, which is why a string search for a command line with spaces
fails against real auditd data. Reproducing it is deliberate: a generator
that emits a cleaner format than reality lets a broken search pass.

## Reproducibility

`--seed` alone is not enough, because the wall clock still moves the
timestamps. Pair it with `--now-epoch` for byte-identical output:

```bash
python3 datagen.py --tier small --seed 42 --now-epoch 1794400000 --out ./a
python3 datagen.py --tier small --seed 42 --now-epoch 1794400000 --out ./b
```

Verified identical across all six committed templates. The two runtimes
have different RNGs, so `datagen.ps1` is **not** byte-identical to
`datagen.py`; record shapes, source types and volumes match.
