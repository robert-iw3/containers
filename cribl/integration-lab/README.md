# Enterprise log sources → Cribl → Splunk integration lab

Fifteen mock log sources — Windows Security, Sysmon, DNS and DHCP from the
domain controllers, Palo Alto, Cisco ASA and ISE, Suricata, NetFlow, proxy, web
tier, Kubernetes, Linux and Entra ID — emit into a Cribl worker, which applies a
different treatment per source and forwards to Splunk. `run-lab.sh` asserts what
arrived, how much licensed volume it consumed, and that every mapped control
still has evidence.

The lab measures index utilization: how much licensed volume the pipeline
removes. The Windows event IDs it emits are an example set for exercising the
pipeline, not a detection baseline. A second run will measure extending
detection coverage while holding the reduction.

```bash
./run-lab.sh                # bring it up, generate traffic, assert, tear down
KEEP_UP=1 ./run-lab.sh      # leave the stack running for inspection
```

The Splunk image is built once from this repository:

```bash
podman build -t localhost/splunk-lab:10.4.2 ../../splunk/enterprise
```

The Splunk instance runs the repository's hardened configuration, not stock
defaults: `splunk/conf/render.sh` produces it, `make-certs.sh` produces a lab CA
and per-service certificates, and the container's entrypoint stages both into
place before splunkd starts. Splunk Web is HTTPS-only, endpoints reach Cribl
over mutual TLS, nothing publishes port 80, and there is no plaintext receiver
on 9997.

## The path

```
 15 sources          cribl-worker                     splunk
 ┌──────────┐        tcpjson :10060 (mutual TLS)      index=enterprise
 │ emitter  ├──tee──►  route by sourcetype ──► one    ← what the pipeline kept
 │          │          pipeline per source     HEC
 │          └───────────────────────────────►  HEC    index=enterprise_raw
 └──────────┘        straight to Splunk               ← the unfiltered control
```

Every record takes both paths, so the "no pipeline" baseline is measured in
Splunk rather than computed from the emitter's own send count. The
leader carries no data; it holds config and distributes it.

## The data set

`generator/sources/` holds one module per feed. Each declares `SHARE` — its
percent of total **bytes**, because that is how SIEM volume is quoted and
licensed — plus its sourcetype, record shape, and the NIST SP 800-53r5 controls
and CSF 2.0 subcategories that its events provide evidence for.

Record sizes differ by a factor of twelve across these feeds, so the harness
measures each source's average size and solves for the selection weight that
lands on the declared byte share. Adding a feed means adding a module.

The shares model a ~10,000-endpoint enterprise and are the input to substitute
first: the reduction ratio follows directly from them, because **a reduction
ratio is a property of the environment at least as much as of the pipeline.**
Set them from your own license usage per sourcetype and re-run.

## What the lab asserts

Counting arrivals is not enough: a pipeline that forwards everything and a
pipeline that forwards nothing both produce an event count, so the count alone
does not show whether the right events were kept.

| Assertion | What it catches |
| --- | --- |
| `index_thruput` non-zero **and** `_internal` searchable | the two ways an indexer returns nothing: events routed away before the index writer, or indexed and invisible to this role |
| all 15 sources represented after reduction | a route filter that matches no events sends its whole feed to the unmatched file |
| the unmatched capture is empty | everything fell through to the catch-all |
| every must-not-drop control still has evidence | reduction that removes a control's only evidence is a deferred cost, not a saving |
| control arm received every record, 0 HEC errors | an A/B whose control arm is missing records measures the reduction against an incomplete baseline |
| emitter and control index agree within 1% | two independent accountings of the same quantity |
| 5156/5158 absent, 1102 present | the drop ran and did not remove the rare high-value event |
| encoded payload in the restricted index, absent from the main one, present in the control | the routing ran, and the control proves there was something to route |
| 40–70% of licensed bytes kept | two-sided: too low means a rule is removing more than it was written to |
| Splunk Web refuses http and answers https | the hardening took effect |
| no `Non-SSL` acceptor on 9997, nothing on port 80 | plaintext left in the deployment |

## The business case, measured

See [cribl-value-measured.md](../docs/cribl-value-measured.md) for the full
write-up. The current run removed **34.4% of licensed volume** while leaving
six of fifteen sources untouched and every full-rate detection witness intact.
A volume-tuned version of the same rules reached 69.8%; the difference is what
that version was taking out of the SOC's visibility, and section 3 of the
write-up quantifies it rule by rule.

## Operating constraints

These are the constraints the lab is built around. Each one produced a failure
that reported healthy, so each is enforced by a check rather than by a comment.

### Splunk and the forwarder

**Staged configuration and certificates mount outside `$SPLUNK_HOME`.** Splunk
reverts ownership at start with a recursive `chown` of `$SPLUNK_HOME`; a
read-only mount inside it makes that `chown` fail and Splunk aborts with
`Error calling execve()`, which does not identify the mount as the cause. The
mounts are at `/staged/conf` and `/staged/certs`, and the entrypoint copies both
into place owned by `splunk` before splunkd starts.

**Certificates cannot be mounted at their final path.** A bind mount carries the
host's ownership, which maps to root in the container while splunkd runs as
`splunk`, so 0600 keys are unreadable. Splunk Web then starts with SSL enabled
and no usable certificate and answers neither http nor https.

**Never run the Splunk CLI as root in a container.** `podman exec` defaults to
root, and the CLI writes files owned by the user who runs it. A single
root-owned `etc/system/metadata/local.meta` prevents splunkd from starting
again (`Cannot initialize: ... Permission denied`). Before that failure,
splunkd returns HTTP 500 on `/storage/passwords` while the container still
reports healthy. Splunk
10 also refuses to start as root, so `podman exec <c> splunk restart` stops
splunkd and does not bring it back.

**`[indexAndForward] selectiveIndexing = true` in `outputs.conf` discards
everything on an indexer.** The receiver still acknowledges every event and no
index receives anything, `_internal` included. `splunk/conf/render.sh` refuses
to emit the file without `--forwarding`, and the lab asserts `index_thruput`
directly rather than inferring from a search.

**`SPLUNK_ENABLE_LISTEN` writes a plaintext receiver.** It produces
`[splunktcp://9997]` in the search app, which is a different stanza from
`[splunktcp-ssl://9997]` and is never overridden by it. Both acceptors bind. Define the receiver only in the staged `inputs.conf`.

**The forwarder's default throughput limit is 256 KBps per pipeline.** On a
domain controller the limit is roughly a quarter of what the host generates (an
estimate, not measured in this lab), so the channel backlog never drains while
the forwarder still reports healthy. Set
`limits.conf [thruput] maxKBps` deliberately.

### Cribl

**Configuration is files, in two places.** The leader's own config is
`/opt/cribl/local/cribl`; a group's is `/opt/cribl/groups/<group>/local/cribl`.
Files under `local/cribl/groups/<group>/` are ignored without an error.

**Never mount a volume on a worker's `/opt/cribl/state`.** A worker applies a
bundle by renaming `state/distributed/bundles/<id>/local/cribl` over
`/opt/cribl/local/cribl`. A volume puts those two paths on different filesystems, so the rename fails
with `EXDEV`, apply and revert both fail, and the worker holds a stale config
lock indefinitely while reporting healthy.

**Editing group config is not enough.** The leader must commit, then deploy with
the returned commit hash. The literal `HEAD` is rejected.

**One invalid entry invalidates the whole file.** A single bad key or enum value
disables every Destination in `outputs.yml`. The startup error names one entry
but does not say what is wrong with it, and the entry it names is often a valid
one, not the faulty one. `run-lab.sh` validates
both Sources and Destinations against the schema shipped in the Cribl image
before deploying, including enum values.

**The group config helper starts lazily** and can be minutes behind the leader's
API on a loaded host. Until it is up, its error is indistinguishable from broken
configuration, so the runner treats "not available" as not ready and keeps
waiting. A check that could not run is not a result.

**The leader-to-worker channel cannot be TLS while distributed settings come
from environment variables.** `tls://` in `CRIBL_DIST_LEADER_URL` enables TLS on
port 4200 and names no certificate: the leader binds nothing, every worker reports
`sending is blocked`, no bundle is applied, and both containers report
healthy while the leader still accepts commits and deploys. Naming a certificate
requires distributed settings that are not environment variables, and the API
refuses them: *"Changing distributed settings is disabled while
CRIBL_DIST_MASTER_URL, CRIBL_DIST_MODE env vars are defined."* A group-local
`cribl.yml` does not reach it either. The lab runs `tcp://` and reports the
check as `skip`, not `ok`. The bundle is the group's
`outputs.yml` verbatim, so in production every Destination credential crosses
that port once per worker on every deploy.

### Writing checks against this stack

**`grep -q` on a pipe inverts an assertion under `set -o pipefail`.** It exits at
the first match and sends SIGPIPE to the writer; the pipeline then reports 141,
so the check fails exactly when the pattern it searches for is present. The
failure depends on output buffering, so the check passes when run by hand and
fails in the full run. Use `grep -c`.

**`splunk search -output rawdata` fails on any `stats` result** with
`result had no _raw key`. A count helper built on it returns nothing, every
count reads zero, and a working pipeline is reported as completely broken. Use
`-output csv`.

**The Splunk image ships no `curl`, `wget`, `nc`, `ss`, `netstat` or `lsof`.**
In-container checks go through a `splunk` subcommand, `openssl`, or
`/opt/splunk/bin/python3`.

## Credentials

`run-lab.sh` generates `.env` on first run (Cribl distributed token, Splunk
admin password) and creates the Splunk HEC token through the API, writing it
into the worker group's Destination at deploy time. `.env`, the live config
and the leader's auth material are gitignored. Nothing here ships a
credential.
