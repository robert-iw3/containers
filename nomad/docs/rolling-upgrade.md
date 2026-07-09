# Rolling upgrade runbook

Order matters: **servers first (followers, then leader), then clients**. Nomad
servers tolerate mixed versions inside one minor release train during the roll;
clients must never run a newer version than the servers.

Before anything: read the upstream upgrade guide for the target version
(https://developer.hashicorp.com/nomad/docs/upgrade/upgrade-specific) — some
releases have one-off steps this generic runbook can't know about.

## 0. Preconditions

```bash
export NOMAD_ADDR=https://<any-server>:4646
export NOMAD_CACERT=/etc/nomad.d/ca.pem
export NOMAD_TOKEN=<management token>

nomad server members            # all alive, one leader
nomad node status               # all clients ready
nomad operator snapshot save pre-upgrade-$(date +%Y%m%d).snap
```

Do not proceed with a degraded quorum. With 3 servers you can lose exactly one;
an upgrade intentionally takes one down, so all three must be healthy first.

## 1. Upgrade server followers, one at a time

For each **non-leader** server (find the leader with
`nomad operator raft list-peers`):

```bash
# on the server being upgraded
sudo systemctl stop nomad
# install the new binary (ansible avenue: rerun the playbook limited to this
# host with the new nomad_version; baremetal: NOMAD_VERSION=x.y.z ./install-nomad.sh)
sudo systemctl start nomad
```

Wait until it rejoins before touching the next one:

```bash
nomad server members     # upgraded server alive, correct new version shown
nomad operator raft list-peers
```

## 2. Upgrade the leader last

Transfer leadership away first so the restart doesn't force an election under
load:

```bash
nomad operator raft transfer-leadership
```

Then repeat the stop → install → start → verify cycle on the old leader.

## 3. Upgrade clients

Drain each client so workloads reschedule gracefully, then upgrade:

```bash
nomad node drain -enable -deadline 10m <node-id>
# stop nomad, install new binary, start nomad (as above)
nomad node drain -disable <node-id>
nomad node status <node-id>     # eligible, ready
```

Batch clients only as far as your spare capacity allows — every drained client's
allocations must fit on the remaining ones.

AWS avenue note: instances are ASG-managed, so the equivalent is an instance
refresh — bump `nomad_version` in tfvars, `tofu apply` (updates the launch
template), then refresh clients before... **servers first**: detach/replace
server instances one at a time (or `aws autoscaling start-instance-refresh`
with `MinHealthyPercentage` ≥ 66 on the server ASG), then the client ASGs.

## 4. Post-checks

```bash
nomad server members             # all on the new version
nomad node status                # all ready
nomad job status                 # workloads running
```

## Rollback

Nomad does not support downgrading servers once the new version has written
Raft state. Rollback = restore: stand up servers on the old version and
`nomad operator snapshot restore pre-upgrade-<date>.snap`. This is why step 0's
snapshot is not optional.
