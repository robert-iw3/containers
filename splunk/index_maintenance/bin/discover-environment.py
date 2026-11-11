#!/usr/bin/env python3

"""Write a report describing how data is configured on a Splunk instance.

For someone who has just been handed an instance and needs to understand it:
what arrives, from where, where it lands, how it is parsed, how long it is
kept, and which file decides each of those. Everything is read from the
instance -- nothing here is assumed about how it was set up.

The report is Markdown, so it can be committed, attached to a ticket or read
in a terminal. Every section says which file a setting comes from, because
the question that follows "why is it like this" is always "where do I change
it".

Credentials are optional. Without them the report is built from the merged
configuration and from the metadata in each bucket, which is enough for all
of the above. With them (--auth-file, or --ask-auth) it adds the things only
a search can answer: who the users are, what the roles can see, and which
scheduled searches have been failing.

    ./bin/discover-environment.py --container splunk --out environment.md
    ./bin/discover-environment.py --container splunk --ask-auth --out env.md
"""
from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import splunkmeta as M  # noqa: E402

OUT = []


def w(line: str = "") -> None:
    OUT.append(line)


def table(headers, rows) -> None:
    if not rows:
        w("_Nothing found._")
        w()
        return
    w("| " + " | ".join(headers) + " |")
    w("|" + "|".join("---" for _ in headers) + "|")
    for r in rows:
        w("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    w()


def when(epoch) -> str:
    if not epoch:
        return "never"
    return time.strftime("%F %T", time.gmtime(epoch))


def btool_files(t: M.Target, conf: str, stanza_filter=None):
    """Which app defines each stanza of a conf file.

    btool --debug prefixes every line with the file it came from, which is
    the only reliable way to answer "where is this set".
    """
    out = t.splunk(f"btool {conf} list --debug")
    current, owner = None, {}
    for line in out.splitlines():
        m = re.match(r"^(\S+)\s+\[(.+)\]\s*$", line)
        if m:
            current = m.group(2)
            path = m.group(1)
            if current not in owner:
                owner[current] = path
    if stanza_filter:
        owner = {k: v for k, v in owner.items() if stanza_filter(k)}
    return owner


def short_path(t: M.Target, p: str) -> str:
    return p.replace(f"{t.home}/etc/", "").replace(f"{t.home}/", "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--container")
    ap.add_argument("--splunk-home", default="/opt/splunk")
    ap.add_argument("--user")
    ap.add_argument("--out", help="Write the report here instead of to stdout")
    ap.add_argument("--auth-file")
    ap.add_argument("--ask-auth", action="store_true")
    ap.add_argument("--include-internal", action="store_true",
                    help="Describe Splunk's own _* indexes too")
    args = ap.parse_args(argv)

    t = M.Target(args.container, args.splunk_home, args.user)
    auth = None
    if args.auth_file:
        auth = Path(args.auth_file).read_text().splitlines()[0].strip()
    elif os.environ.get("SPLUNK_AUTH"):
        auth = os.environ["SPLUNK_AUTH"]
    elif args.ask_auth:
        if sys.stdin.isatty():
            u = input("  Splunk username: ").strip()
            p = getpass.getpass(f"  Password for {u}: ")
            auth = f"{u}:{p}" if u and p else None
        else:
            print("  --ask-auth needs a terminal; continuing without "
                  "credentials", file=sys.stderr)

    def search(spl: str) -> str:
        if not auth:
            return ""
        return t.sh(f"IM_A='{auth}' sh -c '{t.home}/bin/splunk search "
                    f'"{spl}" -output csv -preview false -auth "$IM_A"\' '
                    f"2>/dev/null")

    now = time.time()
    sys.stderr.write("  reading the instance ...\n")

    # ---------------------------------------------------------------- 1
    w("# Splunk environment")
    w()
    w(f"Generated {when(now)} UTC from `{t.home}`"
      + (f" in the container `{args.container}`." if args.container else "."))
    w()
    w("Everything below was read from the instance. Each section names the "
      "file a setting comes from, so anything that looks wrong can be "
      "changed where it is actually set.")
    w()

    ver = t.splunk("version").strip().splitlines()
    roles = []
    srv = t.splunk("btool server list general")
    for line in srv.splitlines():
        if line.strip().startswith("serverName") and "=" in line:
            roles.append(("serverName", line.split("=", 1)[1].strip()))
    mgmt = ""
    for line in t.splunk("btool web list settings").splitlines():
        if line.strip().startswith("mgmtHostPort") and "=" in line:
            mgmt = line.split("=", 1)[1].strip()

    w("## In one paragraph")
    w()
    names = M.indexes(t)
    user_idx = [n for n in names if not n.startswith("_")]
    total_kb = 0
    holding = 0
    for idx in user_idx:
        s = M.index_settings(t, idx)
        home, _ = M.index_dirs(t, idx, s)
        base = home[:-3] if home.endswith("/db") else home
        kb = M.du_kb(t, base)
        total_kb += kb
        if M.metadata(t, idx, s, "sourcetype"):
            holding += 1
    w(f"- **Version**: {ver[0] if ver else 'unknown'}")
    for k, v in roles:
        w(f"- **{k}**: {v}")
    w(f"- **Indexes**: {len(user_idx)} defined for data, {holding} holding "
      f"any, plus {len(names) - len(user_idx)} of Splunk's own")
    on_disk = (f"{total_kb / 1048576:.1f} GB" if total_kb >= 1048576
               else f"{total_kb / 1024:.0f} MB")
    w(f"- **On disk**: {on_disk} across the data indexes")
    used, avail, pct = M.disk_free(t, f"{t.home}/var/lib/splunk")
    w(f"- **Disk**: {avail / 1048576:.0f} GB free on the index filesystem "
      f"({100 - pct}% of it)")
    if mgmt:
        w(f"- **Management port**: {mgmt}")
    w()

    # ---------------------------------------------------------------- 2
    w("## How data gets in")
    w()
    w("Three things have to line up for data to arrive: something sends it, "
      "this instance accepts it, and an input decides which index it lands "
      "in.")
    w()

    w("### Receiving")
    rows = []
    for line in t.splunk("btool inputs list --debug").splitlines():
        m = re.match(r"^(\S+)\s+\[(splunktcp|tcp|udp|http)(?::\/\/)?(.*)\]\s*$", line)
        if m:
            rows.append((f"`{m.group(2)}://{m.group(3)}`",
                         short_path(t, m.group(1))))
    table(["listening on", "defined in"], sorted(set(rows)))

    w("### Forwarders currently connected")
    fwd = t.sh(f"grep -h 'group=tcpin_connections' "
               f"{t.home}/var/log/splunk/metrics.log 2>/dev/null | tail -300")
    seen = {}
    for line in fwd.splitlines():
        h = re.search(r"hostname=([^\s,]+)", line)
        v = re.search(r"version=([^\s,]+)", line)
        ft = re.search(r"fwdType=([^\s,]+)", line)
        if h:
            seen[h.group(1)] = (v.group(1) if v else "?",
                                ft.group(1) if ft else "?")
    table(["forwarder", "version", "type"],
          [(h, v, f) for h, (v, f) in sorted(seen.items())])
    if not seen:
        w("No forwarder has connected recently. Data may be arriving through "
          "a file input, HEC, or a scripted input instead -- see the inputs "
          "below.")
        w()

    w("### Inputs defined here")
    w()
    w("An input on *this* instance reads data this instance can see. Data "
      "arriving from a forwarder is configured on that forwarder, not here, "
      "so an empty table does not mean nothing is arriving.")
    w()
    rows = []
    for line in t.splunk("btool inputs list --debug").splitlines():
        m = re.match(r"^(\S+)\s+\[(monitor|batch|script|WinEventLog|"
                     r"powershell|perfmon)(?::\/\/)?(.*)\]\s*$", line)
        if m:
            rows.append((f"{m.group(2)}", f"`{m.group(3)[:52]}`",
                         short_path(t, m.group(1))))
    table(["kind", "path or source", "defined in"], sorted(set(rows))[:40])

    # ---------------------------------------------------------------- 3
    w("## What is actually in each index")
    w()
    w("Read from the metadata Splunk keeps in every bucket, so these are "
      "counts of what is on disk rather than a sample.")
    w()
    for idx in (names if args.include_internal else user_idx):
        s = M.index_settings(t, idx)
        md = M.metadata(t, idx, s, "sourcetype")
        hosts = M.metadata(t, idx, s, "host")
        if not md:
            w(f"### `{idx}`")
            w()
            w("Holds no data.")
            w()
            continue
        total = sum(r.count for r in md.values())
        newest = max((r.latest or 0) for r in md.values())
        oldest = min((r.earliest or 0) for r in md.values() if r.earliest) \
            if any(r.earliest for r in md.values()) else 0
        w(f"### `{idx}`")
        w()
        w(f"{total:,} events, {when(oldest)} to {when(newest)} UTC. "
          f"Last event {int((now - newest) / 3600)}h ago.")
        w()
        table(["source type", "events", "first", "last"],
              [(f"`{r.value}`", f"{r.count:,}", when(r.earliest), when(r.latest))
               for r in sorted(md.values(), key=lambda r: -r.count)])
        if hosts:
            w(f"Hosts reporting into it: "
              + ", ".join(f"`{h}`" for h in sorted(hosts)[:20])
              + (f" and {len(hosts) - 20} more" if len(hosts) > 20 else ""))
            w()

    # ---------------------------------------------------------------- 4
    w("## Index configuration")
    w()
    w("Retention and size are both ceilings and whichever is reached first "
      "wins: an index set to keep 90 days inside a 50 GB cap keeps 90 days "
      "only if 90 days fits in 50 GB.")
    w()
    owners = btool_files(t, "indexes", lambda k: k != "default" and ":" not in k)
    rows = []
    for idx in (names if args.include_internal else user_idx):
        s = M.index_settings(t, idx)
        ret = s.get("frozenTimePeriodInSecs", "")
        cap = s.get("maxTotalDataSizeMB", "")
        frozen_to = s.get("coldToFrozenDir", "") or s.get("coldToFrozenScript", "")
        rows.append((
            f"`{idx}`",
            f"{int(ret) // 86400}d" if ret.isdigit() else "unset",
            f"{int(cap) / 1024:.0f}G" if cap.isdigit() and int(cap) >= 1024
            else (f"{cap}M" if cap.isdigit() else "unset"),
            "archived" if frozen_to else "deleted",
            short_path(t, owners.get(idx, "?")),
        ))
    table(["index", "retention", "size cap", "past retention", "defined in"], rows)
    w("“past retention: deleted” means exactly that -- when data passes the "
      "retention or the cap it is removed, with no copy kept, unless "
      "`coldToFrozenDir` is set.")
    w()

    # ---------------------------------------------------------------- 5
    w("## How data is parsed")
    w()
    w("A source type decides how an event is broken up, timestamped and "
      "extracted. Where a source type is defined tells you which app owns "
      "that behaviour.")
    w()
    props = btool_files(t, "props")
    seen_st = set()
    for idx in user_idx:
        s = M.index_settings(t, idx)
        seen_st |= set(M.metadata(t, idx, s, "sourcetype").keys())
    rows = []
    for st in sorted(seen_st):
        path = props.get(st)
        rows.append((f"`{st}`",
                     short_path(t, path) if path else
                     "**no props.conf stanza** -- Splunk is guessing"))
    table(["source type in the data", "parsed by"], rows)
    unparsed = [r for r in rows if "no props.conf" in str(r[1])]
    if unparsed:
        w(f"{len(unparsed)} source type(s) present in the data have no "
          f"explicit parsing configuration. Splunk will have guessed line "
          f"breaking and timestamps for those, which usually works and "
          f"sometimes quietly does not.")
        w()

    w("### Index routing")
    w()
    w("A transform can send an event to a different index than its input "
      "named. If data is not where you expect, this is where to look.")
    w()
    rows = []
    tr = t.splunk("btool transforms list --debug")
    stanza, path = None, None
    for line in tr.splitlines():
        m = re.match(r"^(\S+)\s+\[(.+)\]\s*$", line)
        if m:
            path, stanza = m.group(1), m.group(2)
            continue
        if stanza and "_MetaData:Index" in line:
            rows.append((f"`{stanza}`", short_path(t, path or "?")))
    table(["transform", "defined in"], sorted(set(rows)))

    # ---------------------------------------------------------------- 6
    w("## Apps")
    w()
    appdirs = t.sh(f"ls -1 {t.home}/etc/apps 2>/dev/null").split()
    rows = []
    for a in sorted(appdirs):
        st = t.sh(f"cat {t.home}/etc/apps/{a}/local/app.conf "
                  f"{t.home}/etc/apps/{a}/default/app.conf 2>/dev/null")
        disabled = bool(re.search(r"(?m)^\s*state\s*=\s*disabled", st))
        ver = re.search(r"(?m)^\s*version\s*=\s*(\S+)", st)
        has = []
        for conf, label in (("indexes.conf", "indexes"),
                            ("inputs.conf", "inputs"),
                            ("props.conf", "parsing"),
                            ("savedsearches.conf", "searches")):
            n = t.sh(f"ls {t.home}/etc/apps/{a}/*/{conf} 2>/dev/null | wc -l").strip()
            if n.isdigit() and int(n) > 0:
                has.append(label)
        rows.append((f"`{a}`", ver.group(1) if ver else "",
                     "disabled" if disabled else "enabled",
                     ", ".join(has) or "-"))
    table(["app", "version", "state", "configures"], rows)

    # ---------------------------------------------------------------- 7
    w("## Scheduled searches")
    w()
    rows = []
    ss = t.splunk("btool savedsearches list --debug")
    stanza, path, cron, enabled, to_index = None, None, "", "", ""
    def flush():
        if stanza and cron:
            rows.append((f"`{stanza[:46]}`", cron,
                         "no" if enabled in ("0", "false") else "yes",
                         to_index or "-", short_path(t, path or "?")))
    for line in ss.splitlines():
        m = re.match(r"^(\S+)\s+\[(.+)\]\s*$", line)
        if m:
            flush()
            path, stanza = m.group(1), m.group(2)
            cron, enabled, to_index = "", "", ""
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k == "cron_schedule":
            cron = v
        elif k == "enableSched":
            enabled = v
        elif k in ("action.summary_index._name", "action.summary_index"):
            if k.endswith("_name"):
                to_index = v
    flush()
    table(["saved search", "cron", "scheduled", "writes to", "defined in"],
          rows[:40])
    if len(rows) > 40:
        w(f"_and {len(rows) - 40} more._")
        w()

    # ---------------------------------------------------------------- 8
    if auth:
        w("## Who can see what")
        w()
        w("An account that may not search an index gets no results from it, "
          "which looks the same as an empty index.")
        w()
        out = search("| rest /services/authorization/roles splunk_server=local "
                     "| fields title, srchIndexesAllowed, srchIndexesDefault "
                     "| table title, srchIndexesAllowed, srchIndexesDefault")
        rows = []
        for line in out.splitlines()[1:]:
            parts = [c.strip('"') for c in line.split(",")]
            if len(parts) >= 3 and parts[0]:
                rows.append((f"`{parts[0]}`", parts[1][:40] or "-",
                             parts[2][:40] or "-"))
        table(["role", "may search", "searches by default"], rows)

        w("### Scheduled searches that have been failing")
        w()
        out = search("index=_internal sourcetype=scheduler "
                     "(status=skipped OR status=continued) earliest=-24h "
                     "| stats count by savedsearch_name, status "
                     "| sort - count | head 20")
        rows = []
        for line in out.splitlines()[1:]:
            parts = [c.strip('"') for c in line.split(",")]
            if len(parts) >= 3:
                rows.append((f"`{parts[0][:46]}`", parts[1], parts[2]))
        table(["saved search", "status", "times in 24h"], rows)
        if rows:
            w("`skipped` means the scheduler could not start it, almost "
              "always because more searches are scheduled than the instance "
              "can run at once. `continued` means it was deferred.")
            w()
    else:
        w("## Who can see what")
        w()
        w("_Not read: this needs credentials. Re-run with `--ask-auth` to "
          "include roles, index permissions and the scheduler's recent "
          "failures._")
        w()

    # ---------------------------------------------------------------- 9
    w("## What to check next")
    w()
    w("- `./bin/health-check.py` -- disk, queues, licence, currency, with "
      "verdicts")
    w("- `./bin/data-availability.py` -- every source type and host, and how "
      "long since each last sent anything")
    w("- `./bin/check-credentials.sh` -- what your own account can reach")
    w("- `./bin/index-inventory.sh` -- sizes and retention, and what is "
      "about to be frozen")
    w()

    text = "\n".join(OUT) + "\n"
    if args.out:
        Path(args.out).write_text(text)
        sys.stderr.write(f"  wrote {args.out} ({len(OUT)} lines)\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
