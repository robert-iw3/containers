#!/usr/bin/env python3
"""Apply vendor verification to the rule files.

Round-two verification read the vendor's configuration-file reference for each
setting behind a finding and, where the setting could be exercised, tested it on
a live instance. That work produced three things a rule file should carry:

  a corrected criterion   where the original tested the wrong key, the wrong
                          operator, or the wrong thing entirely
  a citation              the vendor page the criterion now rests on
  a confidence            derived -> documented once a vendor page supports every
                          criterion in the rule, -> tested once each was exercised

Only a correction that is a single valid criterion is applied. The evaluator takes
one condition per check line, with an operator drawn from a fixed vocabulary; a
correction written as prose, or joining two conditions with "AND", is not a
criterion this format can express. Those are written to a deferral report for
reading rather than guessed at, because a criterion the evaluator cannot parse
fails silently and would be worse than the error it replaced.

A criterion the vendor contradicted outright is retired rather than deleted: the
line is kept as `retired_check:` with the reason. Retirement is withheld where it
would leave a rule with no criterion at all, since a rule with none evaluates to
not_reviewed - trading a wrong answer for no answer.

Confidence is the weakest link. A rule is recorded `documented` only when EVERY
criterion it uses was verified; one unverified criterion holds the whole rule at
`derived`, because the rule can be wrong in exactly that place.

Prose stays in assess/inventory/vendor-verification.json. The rule file carries a
pointer to it, so the vendor's words are stored once and the checklist joins to
them at emit time.

Usage:
  assess/bin/apply-verification.py                 # report what would change
  assess/bin/apply-verification.py --apply         # write it
  assess/bin/apply-verification.py --report FILE   # where deferrals are listed
"""
import argparse, json, os, re, sys, collections

# The evaluator's operator vocabulary. A correction using anything else is not a
# criterion it can decide, so it is deferred rather than written.
OPS = ('absent', 'empty', 'equals', 'in', 'matches', 'max', 'min', 'non_empty',
       'not_equals', 'not_in', 'not_matches', 'present')

CHECK = re.compile(r'^(check:\s+)(\S+)\s+\[([^\]]*)\]\s+(\S+)\s+(\S+)(?:\s+(.*))?$')
CRIT = re.compile(r'^(?P<conf>[A-Za-z0-9_.-]+\.conf)\s+\[(?P<stanza>[^\]]*)\]\s+'
                  r'(?P<key>\S+)\s+(?P<op>%s)(?:\s+(?P<val>.*))?$' % '|'.join(OPS))

RANK = {'derived': 0, 'documented': 1, 'tested': 2}
UNRANK = {v: k for k, v in RANK.items()}
FALSE = 'finding_is_false'

# The generated block is fenced so a later run can remove it exactly. Retired
# criteria are restored to active check: lines when the fence is stripped, so the
# applier always sees the same input and is a pure function of (rules, store).
OPEN_FENCE = '# --- vendor verification: generated, do not edit by hand'
CLOSE_FENCE = '# --- end vendor verification'


def strip_block(lines):
    """Remove a previous run's block, restoring the criteria it changed.

    Retired criteria come back as active checks; corrected criteria are replaced
    by the original they were corrected from. The result is the rule file as
    build-rules.py generated it, so applying is repeatable.
    """
    applied = set()
    for line in lines:
        if line.startswith('corrected:'):
            applied.add(line.split(':', 1)[1].split(' -> ')[-1].strip())
    out, inside = [], False
    for line in lines:
        m = CHECK.match(line)
        if m and not inside and line.split(':', 1)[1].strip() in applied:
            continue                      # the corrected form; original is restored below
        if line == OPEN_FENCE:
            inside = True
            continue
        if line == CLOSE_FENCE:
            inside = False
            continue
        if inside:
            if line.startswith('retired_check:'):
                out.append('check:           ' + line.split(':', 1)[1].strip())
            elif line.startswith('corrected:'):
                orig = line.split(':', 1)[1].split(' -> ')[0].strip()
                out.append('check:           ' + orig)
            continue
        out.append(line)
    return out


def parse_correction(text):
    """A correction is usable only as a single parseable criterion.

    Returns the normalized criterion, or None with the reason it was deferred.
    """
    t = ' '.join(str(text or '').split())
    if not t:
        return None, 'empty'
    m = CRIT.match(t)
    if not m:
        return None, 'not a single criterion in the evaluator\'s syntax'
    val = m.group('val') or ''
    # The evaluator decides one condition per line. "AND" is not an operator.
    if re.search(r'\bAND\b', val):
        return None, 'joins two conditions with AND, which the evaluator cannot parse'
    # Instructional prose swallowed into the value would be written as a literal.
    if re.search(r',\s*and\b|\breplace\b|\bdelete\b|\bkeep\b|\bmove\b|\brecord\b'
                 r'|\binstead\b|external_dependencies', val, re.I):
        return None, 'carries instructional prose in the value'
    if m.group('op') in ('present', 'absent', 'non_empty') and val:
        return None, 'operator takes no value but one was given'
    if m.group('op') not in ('present', 'absent', 'non_empty') and not val:
        return None, 'operator needs a value but none was given'
    return '%s [%s] %s %s%s' % (m.group('conf'), m.group('stanza'), m.group('key'),
                                m.group('op'), (' ' + val) if val else ''), None


def wrap(first, cont, text, width=92):
    words = ' '.join(str(text).split()).split()
    lines, cur = [], first
    for w in words:
        if len(cur) + 1 + len(w) > width and cur not in (first, cont):
            lines.append(cur)
            cur = cont + w
        else:
            cur = cur + (' ' if cur not in (first, cont) else '') + w
    lines.append(cur)
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--rules', default=os.path.join('assess', 'rules'))
    ap.add_argument('--store', default=os.path.join('assess', 'inventory',
                                                    'vendor-verification.json'))
    ap.add_argument('--report', default=os.path.join('internal_dev',
                                                     'verification-deferrals.md'))
    a = ap.parse_args()

    with open(a.store, encoding='utf-8') as fh:
        store = json.load(fh).get('settings', {})
    if not store:
        sys.stderr.write('no verification in %s\n' % a.store)
        return 2

    stat = collections.Counter()
    deferred = []      # (rule, conf, stanza, key, verdict, reason, correction)
    withheld = []
    changed = 0

    for fn in sorted(os.listdir(a.rules)):
        if not fn.endswith('.rule'):
            continue
        rid = fn[:-5]
        path = os.path.join(a.rules, fn)
        with open(path, encoding='utf-8') as fh:
            lines = fh.read().split('\n')

        lines = strip_block(lines)

        def lookup(line):
            m = CHECK.match(line)
            if not m:
                return None, None
            _, conf, stanza, key, _, _ = m.groups()
            return m, store.get('%s\t%s\t%s' % (conf, stanza, key))

        # Does any criterion survive retirement? If not, withhold it.
        survives = 0
        for line in lines:
            m, rec = lookup(line)
            if not m:
                continue
            if rec and rec.get('verdict') == FALSE:
                crit, _ = parse_correction(rec.get('correction'))
                if not crit:
                    continue
            survives += 1
        protect = (survives == 0)

        out, seen, vendor, retired, confs, corrections = [], set(), [], [], [], []
        total = verified = 0
        dirty = False

        for line in lines:
            m, rec = lookup(line)
            if not m:
                out.append(line)
                continue
            pre, conf, stanza, key, op, val = m.groups()
            total += 1
            if not rec:
                out.append(line)
                continue

            verified += 1
            confs.append(RANK[rec.get('confidence', 'derived')])
            if rec.get('vendor_doc_url'):
                vendor.append('%s [%s] %s %s' % (conf, stanza, key, rec['vendor_doc_url']))

            crit, why = parse_correction(rec.get('correction'))
            verdict = rec.get('verdict')

            if verdict == FALSE and not crit:
                if protect:
                    out.append(line)
                    stat['retirement withheld (would empty the rule)'] += 1
                    withheld.append(rid)
                    continue
                retired.append(('%s [%s] %s %s%s'
                                % (conf, stanza, key, op, (' ' + val) if val else ''),
                                rec.get('vendor_says') or rec.get('notes')
                                or 'vendor documentation contradicts this criterion'))
                stat['criterion retired'] += 1
                dirty = True
                continue

            if crit:
                new = pre + crit
                if new.strip() in seen:                 # several originals, one correction
                    stat['duplicate criterion collapsed'] += 1
                    dirty = True
                    continue
                seen.add(new.strip())
                if new.strip() != line.strip():
                    stat['criterion corrected'] += 1
                    dirty = True
                    corrections.append((line.split(':', 1)[1].strip(), crit))
                    out.append(new)
                else:
                    stat['criterion already correct'] += 1
                    out.append(line)
                continue

            if (rec.get('correction') or '').strip():
                deferred.append((rid, conf, stanza, key, verdict, why,
                                 ' '.join(rec['correction'].split())))
                stat['correction deferred for reading'] += 1
            if line.strip() in seen:
                stat['duplicate criterion collapsed'] += 1
                dirty = True
                continue
            seen.add(line.strip())
            out.append(line)

        if total and verified == total and confs:
            newconf = UNRANK[min(confs)]
            stat['rule confidence -> ' + newconf] += 1
        elif verified:
            newconf = 'derived'
            stat['rule held at derived (partially verified)'] += 1
        else:
            newconf = None
            stat['rule untouched (no verified criterion)'] += 1

        if newconf:
            for i, l in enumerate(out):
                if l.startswith('confidence:'):
                    repl = 'confidence:      ' + newconf
                    if out[i] != repl:
                        out[i] = repl
                        dirty = True
                    break

        if vendor or retired or corrections:
            last = max((i for i, l in enumerate(out) if l.startswith('check:')), default=None)
            block = [OPEN_FENCE]
            block += ['corrected:       %s -> %s' % (o, n) for o, n in corrections]
            block += ['vendor:          ' + v for v in sorted(set(vendor))]
            for orig, reason in retired:
                block.append('retired_check:   ' + orig)
                block.extend(wrap('                 reason: ', ' ' * 25, reason))
            block.append(CLOSE_FENCE)
            if last is None:
                out.extend([''] + block)
            else:
                out[last + 1:last + 1] = block
            dirty = True

        if dirty:
            changed += 1
            if a.apply:
                tmp = path + '.tmp'
                with open(tmp, 'w', encoding='utf-8') as fh:
                    fh.write('\n'.join(out))
                os.replace(tmp, path)

    print('%s %d rule file(s)' % ('wrote' if a.apply else 'would change', changed))
    for k, n in sorted(stat.items()):
        print('  %-48s %d' % (k, n))

    if withheld:
        print()
        print('  NEEDS READING - every criterion contradicted, retirement withheld:')
        for r in sorted(set(withheld)):
            print('    %s' % r)

    if deferred and a.apply:
        os.makedirs(os.path.dirname(a.report) or '.', exist_ok=True)
        with open(a.report, 'w', encoding='utf-8') as fh:
            fh.write('# Verification corrections deferred for reading\n\n')
            fh.write('Each correction below came from vendor verification but is not a '
                     'single criterion in the\nevaluator\'s syntax, so it was not applied '
                     'mechanically. The evaluator takes one condition\nper check line with '
                     'an operator from a fixed vocabulary (%s).\n\n' % ', '.join(OPS))
            fh.write('%d deferral(s) across %d requirement(s).\n'
                     % (len(deferred), len({d[0] for d in deferred})))
            by = collections.defaultdict(list)
            for d in deferred:
                by[d[0]].append(d)
            for rid in sorted(by):
                fh.write('\n## %s\n\n' % rid)
                for _, conf, stanza, key, verdict, why, corr in by[rid]:
                    fh.write('- **%s [%s] %s** - %s\n' % (conf, stanza, key, verdict))
                    fh.write('  - deferred because: %s\n' % why)
                    fh.write('  - correction as written: %s\n' % corr)
        print()
        print('  %d deferral(s) across %d requirement(s) written to %s'
              % (len(deferred), len({d[0] for d in deferred}), a.report))

    if not a.apply:
        print()
        print('  dry run. re-run with --apply to write.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
