#!/usr/bin/env python3
"""Offline savedsearches.conf validator.

Models Splunk's conf parser (stanzas, key = value, trailing-backslash
continuation, # comments) and checks every key against a copy of
savedsearches.conf.spec, honoring the spec's <wildcard> key forms.

Exists so generated output can be checked without writing anything into a
Splunk instance. Get the spec from the target version:

  podman exec -u splunk <container> \
    cat /opt/splunk/etc/system/README/savedsearches.conf.spec > spec.txt
  bin/validate-savedsearches.py savedsearches.conf spec.txt

Reports parse errors and unknown keys separately, and exits non-zero when
it finds either, so it can gate a build the way preflight.py does.
"""
import os, re, sys, collections

def spec_keys(path):
    exact, wild = set(), []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r'^([A-Za-z_][^\s=]*)\s*=', line)
        if not m: continue
        k = m.group(1)
        if "<" in k:
            wild.append(re.compile("^" + re.escape(k).replace(r"<", "<").replace(
                r"\<", "<") .replace("<", "\x00").split("\x00")[0] + ".*$"))
            # build a proper pattern: replace each <...> with [^.]+ (or .+ at tail)
            parts = re.split(r'<[^>]+>', k)
            pat = "[^.]+".join(re.escape(p) for p in parts)
            wild.append(re.compile("^" + pat + "$"))
        else:
            exact.add(k)
    return exact, wild

def parse(path):
    """Return (stanzas, errors). Mirrors Splunk's line-continuation handling."""
    stanzas, errors = collections.OrderedDict(), []
    cur = None
    pending = None          # (lineno, text) accumulating a continuation
    for n, raw in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
        line = raw.rstrip("\n")
        if pending is not None:
            ln, text = pending
            if line.endswith("\\"):
                pending = (ln, text + line[:-1]); continue
            pending = None
            continue                      # continuation consumed
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1]
            if cur in stanzas:
                errors.append((n, "DUPLICATE STANZA", cur))
            stanzas.setdefault(cur, [])
            continue
        if "=" not in s:
            errors.append((n, "NOT A KEY=VALUE LINE", s[:90]))
            continue
        if cur is None:
            errors.append((n, "KEY OUTSIDE ANY STANZA", s[:90]))
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_.\-]*$', k):
            errors.append((n, "MALFORMED KEY NAME", k[:60]))
            continue
        stanzas[cur].append((n, k, v.strip()))
        if line.endswith("\\"):
            pending = (n, v)
    return stanzas, errors

def main():
    if len(sys.argv) < 3:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    conf, specpath = sys.argv[1], sys.argv[2]
    for pth in (conf, specpath):
        if not os.path.exists(pth):
            print(f"FAIL: no such file: {pth}", file=sys.stderr)
            sys.exit(2)
    exact, wild = spec_keys(specpath)
    stanzas, errors = parse(conf)
    unknown = []
    for st, kvs in stanzas.items():
        for n, k, v in kvs:
            if k in exact: continue
            if any(w.match(k) for w in wild): continue
            if k.startswith("display."): continue  # open namespace: custom visualisations
            unknown.append((n, st, k))
    print(f"file:      {conf}")
    print(f"stanzas:   {len(stanzas)}")
    print(f"key lines: {sum(len(v) for v in stanzas.values())}")
    print(f"PARSE ERRORS:   {len(errors)}")
    for n, kind, det in errors[:25]:
        print(f"   line {n:>5}  {kind}: {det}")
    if len(errors) > 25: print(f"   ... {len(errors)-25} more")
    print(f"UNKNOWN KEYS:   {len(unknown)}")
    seen = collections.Counter(k for _, _, k in unknown)
    for k, c in seen.most_common(15):
        print(f"   {c:>5}x  {k}")
    # Non-zero when something is wrong, so this can gate a build the way
    # preflight.py does. A validator that always exits 0 reports, but it
    # cannot stop anything, and a report nobody reads is not a check.
    sys.exit(1 if (errors or unknown) else 0)

if __name__ == "__main__":
    main()
