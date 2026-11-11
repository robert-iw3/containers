# Splunk index maintenance

Scripts for the data management tasks that come up on a running Splunk
instance: moving data between indexes, renaming one, changing retention and
size limits, emptying an index, and bringing archived data back.

Every script takes the same connection flags, reads the configuration
actually in force rather than guessing at it, shows what it intends to do,
and asks before anything that cannot be undone.

```bash
./bin/index-inventory.sh --container splunk          # start here
./bin/index-inventory.sh --splunk-home /opt/splunk   # or a local install
```

## Which script

| I need to | use |
|---|---|
| see what exists, how big it is, what will be frozen next | [`index-inventory.sh`](bin/index-inventory.sh) |
| create an index, or change its retention or size cap | [`index-create.sh`](bin/index-create.sh) |
| move **some** events to another index, by host, source type or time | [`index-move-events.sh`](bin/index-move-events.sh) |
| move **all** of an index's data to another index | [`index-move-buckets.sh`](bin/index-move-buckets.sh) |
| rename an index | [`index-rename.sh`](bin/index-rename.sh) |
| empty an index but keep it defined | [`index-empty.sh`](bin/index-empty.sh) |
| search data that was frozen out | [`index-thaw.sh`](bin/index-thaw.sh) |

## The two ways to move data, and why the choice matters

This is the decision the rest follows from.

**By search** — [`index-move-events.sh`](bin/index-move-events.sh). Events
matching a search are re-indexed into the destination. It is the only way to
move *part* of an index, because on disk the unit is a bucket and a bucket
holds whatever it holds.

- `_time` is preserved; `_indextime` becomes now.
- It is charged against the licence a second time. Moving 100 GB spends
  100 GB of the daily volume, so a large move is split across days.
- The originals stay. Removing them is a separate decision, below.

**By bucket** — [`index-move-buckets.sh`](bin/index-move-buckets.sh). The
bucket directories are moved on disk. Nothing is re-read.

- No licence cost, no change to `_indextime`, and it takes as long as moving
  files takes.
- All or nothing: the whole index goes.
- splunkd must be stopped, and hot buckets rolled first.
- Not on an indexer cluster: buckets there are tracked by the manager, and
  moving them behind its back makes the cluster disagree with the disk.

So: moving one host's logs out of a shared index is a search move. Merging
`app_2025` into `app_archive` is a bucket move.

## What "delete" means here

Three different things get called deleting data, and they are not
interchangeable:

| | what it does | disk reclaimed |
|---|---|---|
| `\| delete` in a search | marks events unsearchable | **no** — not until the bucket freezes on its own retention |
| `splunk clean eventdata` ([`index-empty.sh`](bin/index-empty.sh)) | removes the buckets | yes |
| freezing | removes or archives buckets past retention | yes |

A search-time delete is the one most often reached for and the one that does
least: the data is still on disk, still counted in the index size, and still
there until retention catches up. It also needs a role holding
`can_delete`, which `admin` does not have by default.

## Renaming

Splunk has no rename. The name is in the index stanza, in the bucket paths,
in every input routing to it, and in every search, dashboard and alert naming
it. [`index-rename.sh`](bin/index-rename.sh) creates the new index with the
old one's settings and moves the data across, and reports everything on the
instance still referring to the old name — but repointing those is yours to
do, and so is removing the old definition once you are satisfied.

The step that breaks deployments is the third one. The data moves silently
and the searches keep looking at a name that no longer holds anything. Note
also that the scan sees this instance only: a forwarder's `inputs.conf` is
where new data is routed, and until that is changed and the forwarder
restarted, new data still arrives in the old index.

## Retention and size are both ceilings

`frozenTimePeriodInSecs` and `maxTotalDataSizeMB` are limits, and whichever
is reached first wins. An index set to keep 90 days inside a 50 GB cap keeps
90 days only if 90 days fits in 50 GB; otherwise it keeps however much does.
Leaving the cap unset does not mean unlimited — it takes the default, which
on most installations is 500 GB.

`index-inventory.sh` prints both, the percentage of the cap used, and flags
an index already holding data older than its own retention.

## Credentials

Some operations reach splunkd and need credentials. They are read from a
file or from the environment, never from the command line, where they would
be visible in the process table and in shell history:

```bash
printf 'admin:your-password\n' > ~/.splunk-auth && chmod 600 ~/.splunk-auth
./bin/index-move-events.sh --auth-file ~/.splunk-auth ...
```

```bash
SPLUNK_AUTH='admin:your-password' ./bin/index-move-events.sh ...
```

The Splunk CLI is always run as the account that owns the installation,
resolved from `$SPLUNK_HOME/etc` rather than assumed. Running it as root
leaves root-owned files that splunkd cannot then rewrite, which shows up
later as errors with no obvious cause.

## Common flags

| flag | |
|---|---|
| `--container NAME` | run against a container with `podman exec` |
| `--splunk-home PATH` | run against a local installation (default `/opt/splunk`) |
| `--user NAME` | override the resolved service account |
| `--auth-file PATH` | first line is `user:password` |
| `--dry-run`, `-n` | report what would happen and stop |
| `--yes`, `-y` | skip the confirmation prompt |

## Before a move, after a move

```bash
./bin/index-inventory.sh --container splunk --index src --index dst
# ... the move ...
./bin/index-inventory.sh --container splunk --index src --index dst
```

Each script verifies its own work — a bucket move asserts the destination
directory exists rather than trusting that `mv` said nothing, and a search
move waits for the destination count to rise rather than treating a finished
search as finished indexing. Neither replaces looking at the index
afterwards.
