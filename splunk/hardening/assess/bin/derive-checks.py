#!/usr/bin/env python3
"""Regenerate the collection inventory from the rule files.

The toolkit had two sources of truth for what gets read off the instance.

  assess/bin/assess.sh  collects the settings listed in assess/inventory/checks.tsv
  assess/bin/evaluate.sh decides from the `check:` lines in assess/rules/*.rule

Nothing kept the two in step. assess/bin/apply-verification.py corrects criteria in
the rule files - vendor verification corrected 58 of them and retired 50 - and it
does not touch checks.tsv. A corrected criterion can therefore name a setting that
collection never looked up, and the evaluator then decides on an observation that
does not exist. It fails silently: a condition with no observation reads as "not
present", so the requirement gets a status rather than an error.

This tool makes the rule files the single source of truth. It reads every criterion
and writes the inventory collection needs, so collection cannot fall behind a
correction. A `retired_check:` line is skipped, because a withdrawn criterion
decides nothing and so needs nothing collected.

Nothing a criterion reads is dropped. The evaluator indexes observations by
conf/stanza/key and not by requirement, so an observation collected for one
requirement answers an identical criterion in another; since this tool emits a row
for every criterion, every setting the evaluator reads is still collected.

Running it is a dry run. It reports what would change and writes nothing until
--apply, because applying means a re-collection against the live instance and that
is the operator's decision, not this tool's.

Usage:
  assess/bin/derive-checks.py                  # report what would change
  assess/bin/derive-checks.py --apply          # write it, keeping a .prev copy
  assess/bin/derive-checks.py --examples 10    # show more of each difference
"""
import argparse, os, re, shutil, sys, tempfile, collections

# The evaluator's operator vocabulary, from assess/bin/evaluate.sh. A criterion is
# "conf [stanza] key operator [value]", and the operator is what tells a key apart
# from an operator when only one token follows the stanza.
OPS = ('absent', 'equals', 'in', 'matches', 'max', 'min', 'non_empty',
       'not_equals', 'not_in', 'not_matches', 'present')

# conf, then the bracketed stanza, then whatever the criterion tests.
CHECK = re.compile(r'^(?P<conf>\S+)\s+\[(?P<stanza>[^\]]*)\]\s*(?P<rest>.*)$')

# A specification declares a setting as "name = <value>" at the start of a line.
# Same shape parse-mechanisms.py reads, so the two agree on what is declared.
SPEC_KEY = re.compile(r'^([A-Za-z_][A-Za-z0-9_.\-]*)\s*=')

HEADER = ('srg_id', 'severity', 'conf', 'stanza', 'key', 'key_status')


def resolve_spec_dir(root):
    """The specification set key_status is measured against.

    The set must match the version under assessment: a 10.0.0 set read against a
    10.4.2 instance calls 15 settings undeclared that 10.4.2 does declare, audit.conf
    logging_format among them. Prefer the highest-numbered version-matched directory
    and let the caller name one, which is what bin/build-conf-glossary.py does.
    """
    named = os.environ.get('SPLUNK_SPEC_DIR') or ''
    if named:
        return named
    base = os.path.dirname(root)
    cands = sorted((d for d in os.listdir(base)
                    if d.startswith('splunk-spec-files-')), reverse=True)
    return os.path.join(base, cands[0]) if cands else \
        os.path.join(base, 'splunk-spec-files')


def declared_keys(spec_dir):
    """Every setting name each shipped .conf.spec declares, by conf file."""
    out = {}
    for name in sorted(os.listdir(spec_dir)):
        if not name.endswith('.conf.spec'):
            continue
        keys = set()
        with open(os.path.join(spec_dir, name), encoding='utf-8', errors='replace') as fh:
            for line in fh:
                m = SPEC_KEY.match(line)
                if m:
                    keys.add(m.group(1).lower())
        out[name[:-5]] = keys
    return out


def to_regex(pat):
    """A placeholder name as an anchored regex, the way the toolkit resolves one.

    Ported from the identical function in assess/bin/assess.sh and
    assess/bin/evaluate.sh, so this tool judges coverage by the same rule the run
    uses. A placeholder matches the empty name, and the separator before it becomes
    optional with it, because Splunk inherits: a value in [tcpout] is the default
    for every [tcpout:group].
    """
    out, inph, sep = '^', False, ''
    for c in pat:
        if c == '<':
            inph = True
            if sep:
                out = out[:len(out) - len(sep)] + '(' + sep + '.*)?'
            else:
                out += '.*'
            sep = ''
            continue
        if c == '>':
            inph = False
            continue
        if inph:
            continue
        if c in '.*+?[](){}|^$\\/-':
            out += '\\' + c
            sep = '\\' + c
        else:
            out += c
            sep = c
        if c not in ':-_/':
            sep = ''
    return out + '$'


def coverage(missing, inventory):
    """Which missing rows are real silent failures, and which are already answered.

    A missing row is not automatically a wrong decision. Observations are indexed
    by conf/stanza/key and not by requirement, so the same setting collected for a
    different requirement answers this criterion too. And a row written with a
    placeholder expands at collection into one observation per real stanza, which
    may be the stanza this criterion names.

    Returns three lists: answered elsewhere, possibly answered by expanding a
    placeholder row - the real stanza names are on the instance, not in the repo,
    so this cannot be settled here - and never collected, which is the set that
    decides on an observation that does not exist.
    """
    concrete = set()           # observation keys a literal inventory row produces
    wild = collections.defaultdict(list)   # conf -> (stanza regex, key regex)
    for conf, stanza, key in inventory:
        if not key:
            continue           # a whole-stanza row produces no keyed observation
        if '<' in stanza or '<' in key:
            wild[conf].append((re.compile(to_regex(stanza)),
                               re.compile(to_regex(key.lower()))))
        else:
            concrete.add((conf, stanza, key.lower()))

    elsewhere, maybe, never = [], [], []
    for r in missing:
        conf, stanza, key = r[2], r[3], r[4]
        if not key:
            never.append(r)    # a stanza read happens only if the row asks for it
            continue
        if '<' in stanza or '<' in key:
            sre, kre = re.compile(to_regex(stanza)), re.compile(to_regex(key.lower()))
            if any(c == conf and sre.match(s) and kre.match(k)
                   for c, s, k in concrete):
                elsewhere.append(r)
            elif wild.get(conf):
                maybe.append(r)
            else:
                never.append(r)
            continue
        if (conf, stanza, key.lower()) in concrete:
            elsewhere.append(r)
        elif any(sre.match(stanza) and kre.match(key.lower())
                 for sre, kre in wild.get(conf, ())):
            maybe.append(r)
        else:
            never.append(r)
    return elsewhere, maybe, never


def split_key(rest):
    """Take the key off the front of a criterion's tail.

    A key written as a placeholder may hold a space - authentication.conf
    [roleMap_<authSettings-key>] <Splunk RoleName> names the role names themselves -
    so an angle-bracketed key is read to its closing bracket rather than to the next
    space. The evaluator splits on whitespace and so reads that one differently;
    report() names such lines.
    """
    rest = rest.strip()
    if not rest:
        return '', ''
    if rest.startswith('<') and '>' in rest:
        cut = rest.index('>') + 1
        return rest[:cut], rest[cut:].strip()
    parts = rest.split(None, 1)
    return parts[0], (parts[1] if len(parts) > 1 else '')


def parse_check(text):
    """A criterion as (conf, stanza, key, operator), or None if it is not one."""
    m = CHECK.match(text.strip())
    if not m:
        return None
    key, tail = split_key(m.group('rest'))
    op = tail.split(None, 1)[0] if tail else ''
    # Only an operator follows the stanza: the criterion tests the stanza itself,
    # not a setting in it. build-rules.py drops an empty key when it writes the
    # line, so "inputs.conf [splunktcp] present" is a whole-stanza existence test
    # and the key is genuinely empty.
    if not op and key in OPS:
        return m.group('conf').lower(), m.group('stanza'), '', key
    return m.group('conf').lower(), m.group('stanza'), key, op


def read_rules(rules_dir):
    """Criteria per requirement, plus the lines that did not parse as criteria."""
    per_rule, unparsable, stanza_only, spaced_key = [], [], [], []
    for name in sorted(os.listdir(rules_dir)):
        if not name.endswith('.rule'):
            continue
        path = os.path.join(rules_dir, name)
        srg = severity = ''
        checks, retired = [], 0
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                if line.startswith('id:'):
                    srg = line.split(':', 1)[1].strip()
                elif line.startswith('severity:'):
                    severity = line.split(':', 1)[1].strip()
                elif line.startswith('retired_check:'):
                    retired += 1
                elif line.startswith('check:'):
                    body = line.split(':', 1)[1].strip()
                    got = parse_check(body)
                    if not got:
                        unparsable.append((name, body))
                        continue
                    conf, stanza, key, op = got
                    if not key:
                        stanza_only.append((name, body))
                    elif key.startswith('<') and ' ' in key:
                        spaced_key.append((name, body))
                    checks.append((conf, stanza, key))
        if not srg:
            unparsable.append((name, 'no id: line'))
            continue
        per_rule.append((srg, severity, checks, retired))
    return per_rule, unparsable, stanza_only, spaced_key


def read_existing(path):
    """The inventory as it stands, keyed the way the evaluator matches settings.

    Key case is folded in the lookup because the evaluator lowercases a key before
    matching an observation to a criterion; the spelling is kept for reporting.
    """
    rows = {}
    if not os.path.isfile(path):
        return rows
    with open(path, encoding='utf-8') as fh:
        head = fh.readline().rstrip('\n').split('\t')
        if tuple(head[:6]) != HEADER:
            sys.exit('%s does not carry the expected columns: %s' % (path, head))
        for line in fh:
            f = line.rstrip('\n').split('\t')
            if len(f) < 6:
                continue
            srg, sev, conf, stanza, key, status = f[:6]
            rows[(srg, conf, stanza, key.lower())] = (sev, key, status)
    return rows


def key_status(conf, key, spec, prior):
    """The key_status column, with the meaning parse-mechanisms.py gave it.

      declared   the shipped .conf.spec for this file declares this setting
      undeclared it does not, and the setting is assessed anyway and marked.
                 Measured case: audit.conf settings present on the instance and
                 absent from the specification set
      stanza     the criterion has no key - the whole stanza is read
      aggregate  the whole file is read

    The first three are measured here. `aggregate` is not: it recorded that a
    requirement's prose named conf files but no setting this toolkit could parse,
    which a rule file no longer says, so it is carried over where the row already
    exists and never invented for a new one.
    """
    if not key:
        if prior and prior[2] == 'aggregate':
            return 'aggregate'
        return 'stanza'
    known = spec.get(conf)
    if known is not None and key.lower() in known:
        return 'declared'
    return 'undeclared'


def build(per_rule, existing, spec):
    """One row per distinct (srg_id, conf, stanza, key), in inventory order."""
    rows, seen = [], set()
    collapsed = 0
    for srg, severity, checks, _retired in per_rule:
        for conf, stanza, key in checks:
            ident = (srg, conf, stanza, key.lower())
            if ident in seen:
                collapsed += 1
                continue
            seen.add(ident)
            prior = existing.get(ident)
            rows.append((srg, severity, conf, stanza, key,
                         key_status(conf, key, spec, prior)))
    rows.sort()
    return rows, collapsed


def write_atomically(path, rows, keep_prev):
    """Replace the inventory in one step, keeping the previous file beside it.

    A partial inventory is worse than a stale one: collection would read it, find
    fewer settings, and the run would look complete. The new file is written whole
    under a temporary name and moved into place, and the file it replaces is kept
    as .prev so a bad run is recoverable without a re-collection.
    """
    d = os.path.dirname(os.path.abspath(path))
    # mkstemp creates 0600 and os.replace keeps it. The inventory is read by
    # whatever account runs the collection, which on a Splunk host is the splunk
    # user and not the account that generated this file, so the mode the inventory
    # already had is carried over.
    mode = os.stat(path).st_mode & 0o7777 if os.path.isfile(path) else 0o644
    if keep_prev and os.path.isfile(path):
        shutil.copy2(path, path + '.prev')
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.checks-', suffix='.tsv')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write('\t'.join(HEADER) + '\n')
            for r in rows:
                fh.write('\t'.join(r) + '\n')
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def report(rows, existing, per_rule, unparsable, stanza_only, spaced_key,
           collapsed, spec_dir, n_examples, out):
    """What changes, and which of the changes are the silent failures."""
    new = {(r[0], r[2], r[3], r[4].lower()): r for r in rows}
    missing = [new[k] for k in new if k not in existing]
    dead = [(k[0], existing[k][0], k[1], k[2], existing[k][1], existing[k][2])
            for k in existing if k not in new]
    changed_status = [(new[k], existing[k][2]) for k in new
                      if k in existing and existing[k][2] != new[k][5]]
    changed_sev = [(new[k], existing[k][0]) for k in new
                   if k in existing and existing[k][0] != new[k][1]]
    missing.sort(); dead.sort(); changed_status.sort(); changed_sev.sort()

    with_checks = [p for p in per_rule if p[2]]
    retired = sum(p[3] for p in per_rule)
    p = lambda s='': print(s, file=out)

    p('specification set : %s' % spec_dir)
    p('rule files read   : %d  (%d carry a criterion, %d retired criteria skipped)'
      % (len(per_rule), len(with_checks), retired))
    p()
    p('rows the rules require : %d   over %d requirement(s)'
      % (len(rows), len({r[0] for r in rows})))
    p('rows in the inventory  : %d   over %d requirement(s)'
      % (len(existing), len({k[0] for k in existing})))
    p()
    inventory = [(k[1], k[2], existing[k][1]) for k in existing]
    elsewhere, maybe, never = coverage(missing, inventory)
    p('MISSING FROM THE INVENTORY - a criterion names a setting the inventory does not')
    p('  %d row(s), of which' % len(missing))
    p('    %d decide on a setting nothing collects - the silent failures' % len(never))
    for r in never[:n_examples]:
        p('      %-28s %s [%s] %s   (%s)' % (r[0], r[2], r[3], r[4] or '-', r[5]))
    if len(never) > n_examples:
        p('      ... %d more' % (len(never) - n_examples))
    p('    %d are answered by the same setting collected for another requirement'
      % len(elsewhere))
    for r in elsewhere[:3]:
        p('      %-28s %s [%s] %s' % (r[0], r[2], r[3], r[4] or '-'))
    p('    %d may be answered by expanding a placeholder row, depending on which'
      % len(maybe))
    p('      stanzas the instance has - not decidable from the repo')
    for r in maybe[:3]:
        p('      %-28s %s [%s] %s' % (r[0], r[2], r[3], r[4] or '-'))
    p()
    p('DEAD COLLECTION - the inventory lists a setting no criterion needs')
    p('  %d row(s)' % len(dead))
    for d in dead[:n_examples]:
        p('    %-28s %s [%s] %s   (%s)' % (d[0], d[2], d[3], d[4] or '-', d[5]))
    if len(dead) > n_examples:
        p('    ... %d more' % (len(dead) - n_examples))
    p()
    p('SAME SETTING, DIFFERENT COLUMN - collected either way, label only')
    p('  key_status : %d row(s)' % len(changed_status))
    for r, was in changed_status[:n_examples]:
        p('    %-28s %s [%s] %s   %s -> %s' % (r[0], r[2], r[3], r[4] or '-', was, r[5]))
    if len(changed_status) > n_examples:
        p('    ... %d more' % (len(changed_status) - n_examples))
    p('  severity   : %d row(s)' % len(changed_sev))
    for r, was in changed_sev[:n_examples]:
        p('    %-28s %s [%s] %s   %s -> %s' % (r[0], r[2], r[3], r[4] or '-', was, r[1]))
    p()
    byst = collections.Counter(r[5] for r in rows)
    p('key_status in the derived inventory')
    for k in ('declared', 'undeclared', 'stanza', 'aggregate'):
        p('  %-11s %d' % (k, byst.get(k, 0)))
    if collapsed:
        p()
        p('%d duplicate criterion row(s) collapsed (same setting named twice in one rule)'
          % collapsed)
    if unparsable:
        p()
        p('NOT A CRITERION - %d line(s) this tool could not read, and so did not collect'
          % len(unparsable))
        for name, body in unparsable[:n_examples]:
            p('    %s: %s' % (name, body))
    if stanza_only:
        p()
        p('WHOLE-STANZA CRITERIA - %d line(s) name a stanza and no setting.' % len(stanza_only))
        p('  Collected as a stanza row. The evaluator splits the line on whitespace and')
        p('  so reads the operator as the key name, which no instance has; that is a')
        p('  separate defect in the rule format, not in this inventory.')
        for name, body in stanza_only[:n_examples]:
            p('    %s: %s' % (name, body))
    if spaced_key:
        p()
        p('PLACEHOLDER KEY WITH A SPACE - %d line(s).' % len(spaced_key))
        p('  Read here to the closing angle bracket; the evaluator reads only as far as')
        p('  the first space. Also a rule-format defect, reported rather than worked around.')
        for name, body in spaced_key[:n_examples]:
            p('    %s: %s' % (name, body))


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    assess_root = os.path.dirname(here)
    ap = argparse.ArgumentParser(
        description='Regenerate assess/inventory/checks.tsv from assess/rules/*.rule.')
    ap.add_argument('--rules', default=os.path.join(assess_root, 'rules'),
                    help='directory of .rule files')
    ap.add_argument('--checks', default=os.path.join(assess_root, 'inventory', 'checks.tsv'),
                    help='the inventory to compare against, and to write with --apply')
    ap.add_argument('--spec-dir', default=None,
                    help='specification set key_status is measured against')
    ap.add_argument('--examples', type=int, default=6, metavar='N',
                    help='how many rows to show per difference (default 6)')
    ap.add_argument('--apply', action='store_true',
                    help='write the inventory; without this the tool only reports')
    args = ap.parse_args(argv)

    if not os.path.isdir(args.rules):
        sys.exit('no rule files at %s' % args.rules)
    spec_dir = args.spec_dir or resolve_spec_dir(os.path.dirname(assess_root))
    if not os.path.isdir(spec_dir):
        sys.exit('no specification directory at %s' % spec_dir)

    spec = declared_keys(spec_dir)
    per_rule, unparsable, stanza_only, spaced_key = read_rules(args.rules)
    existing = read_existing(args.checks)
    rows, collapsed = build(per_rule, existing, spec)

    if not rows:
        sys.exit('no criteria parsed from %s - refusing to write an empty inventory'
                 % args.rules)

    report(rows, existing, per_rule, unparsable, stanza_only, spaced_key,
           collapsed, spec_dir, args.examples, sys.stdout)
    print()
    if args.apply:
        write_atomically(args.checks, rows, keep_prev=True)
        print('wrote %d row(s) -> %s' % (len(rows), args.checks))
        print('previous inventory kept at %s.prev' % args.checks)
        print('collection is now behind the rules: re-run assess/bin/assess.sh')
    else:
        print('DRY RUN - nothing written. Re-run with --apply to write %s' % args.checks)
    return 0


if __name__ == '__main__':
    sys.exit(main())
