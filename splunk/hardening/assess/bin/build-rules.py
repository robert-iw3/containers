#!/usr/bin/env python3
"""Maintain one rule file per requirement.

A rule file is the unit a site customizes. It holds everything needed to assess
one requirement - what it asks, what the application can do about it, the
conditions that decide it, and where each of those came from - in a format that
is read by shell at run time and edited by hand without tooling.

One requirement per file on purpose. A site that disagrees with a determination
edits that file; it does not fork the toolkit, regenerate an inventory, or hold a
patch against a large generated document.

Rule files are source, not build output. This tool never removes one and never
rewrites what the site owns: the criteria, the determination, decidable,
confidence, and any vendor verification block. It does three things.

  scaffold   a requirement that has a criterion and no rule file gets one,
             written from criteria.json and sca-determinations.json
  refresh    the fields the benchmark fixes - the title, severity, CAT, CCI and
             the control mapping - are brought up to date in place, in a file
             whose site-owned content is still what a scaffold would hold
  report     a file the site has customized is left alone. Where the benchmark
             text has also moved under it, the file is listed rather than
             written, because the requirement may now be asking something
             different and only a reader can say whether the criteria still
             answer it.

The rule format carries the requirement title but not the SRG discussion, check
and fix prose, so a revision confined to that prose is not visible from the rule
files and is not reported here; it is a difference between two benchmark
documents.

Usage:
  assess/bin/build-rules.py [ROOT]                    # report what would change
  assess/bin/build-rules.py [ROOT] --apply            # write it
  assess/bin/build-rules.py [ROOT] --refresh-header   # also restate the note
"""
import argparse
import json
import os
import sys

SEV_CAT = {'high': 'CAT I', 'medium': 'CAT II', 'low': 'CAT III'}

# Every field line in a rule file puts its value in the same column, and wrapped
# prose is indented to match it.
FW = 17

# The fields the benchmark fixes. A site that disagrees with one of these is
# disagreeing with the SRG document, not with this assessment, so they are
# refreshed in place and nothing else in the file is.
BENCH_FIELDS = ('group', 'severity', 'cat', 'cci', 'control_rev5')

# The lines that decide a requirement. A file whose set of these differs from
# what a scaffold would hold has had its criteria customized, which is what makes
# a revision of the benchmark text a question for a reader rather than a refresh.
# confidence and vendor pointers record where a criterion came from, not what it
# tests, so they do not make a file a question.
CRITERIA_FIELDS = ('check', 'retired_check', 'corrected', 'decidable')

# Header field order, used to place a field the file does not carry yet.
FIELD_ORDER = ('id', 'group', 'severity', 'cat', 'determination', 'grade',
               'decidable', 'confidence', 'revised', 'cci', 'control_rev5')

# The note every rule file carries, under the title and above the fields. It
# states what regeneration does, because the file invites an edit.
HEADER_NOTE = [
    '# Generated from the benchmark and the assessment determinations, then kept',
    '# by hand. Edit this file to change how this requirement is assessed here;',
    '# it is read at run time. Regenerating refreshes the benchmark text in place',
    '# and leaves the criteria, the determination and any verification block as',
    '# they are.',
]


def wrap(text, width=74, indent=' ' * FW):
    """Fold prose so a rule file stays readable in a terminal."""
    words, lines, cur = (text or '').split(), [], ''
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur); cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur:
        lines.append(cur)
    return ('\n' + indent).join(lines) if lines else ''


def fld(name, value):
    """name: value, in the column every rule file uses."""
    return '%-*s%s' % (FW, name + ':', value)


def condition_line(c):
    """conf [stanza] key operator value - the form the evaluator reads."""
    stanza = '[%s]' % c.get('stanza', '') if c.get('stanza') else '[]'
    op = c.get('operator', '')
    val = (c.get('value') or '').strip()
    return ' '.join(x for x in (c.get('conf', ''), stanza, c.get('key', ''), op, val) if x)


def controls_of(r, ccimap):
    """The Rev 5 controls the requirement's CCIs map to."""
    return sorted({(ccimap.get(x) or {}).get('controls', {}).get('5', '').split()[0]
                   for x in r['cci'] if (ccimap.get(x) or {}).get('controls', {}).get('5')})


def comment_block(sid, r):
    """The leading comment: the requirement line, the title, then the note."""
    L = ['# %s  -  %s' % (sid, SEV_CAT.get(r['severity'], r['severity'])),
         '# %s' % wrap(r['title'], 74, '# '),
         '#']
    L.extend(HEADER_NOTE)
    return '\n'.join(L).split('\n')


def render(sid, r, c, d, ccimap, gloss):
    """A whole rule file as a scaffold holds it, line by line."""
    controls = controls_of(r, ccimap)
    confs = sorted({k.get('conf') for k in (c.get('conditions') or []) if k.get('conf')})

    L = list(comment_block(sid, r))
    L.append('')
    L.append(fld('id', sid))
    L.append(fld('group', r['group_id']))
    L.append(fld('severity', r['severity']))
    L.append(fld('cat', SEV_CAT.get(r['severity'], '')))
    L.append(fld('determination', d.get('determination', 'UNDETERMINED')))
    L.append(fld('grade', d.get('evidence_grade', '-')))
    L.append(fld('decidable', c.get('decidable', 'manual')))
    # derived    from the benchmark text and the shipped specification only
    # documented confirmed against the vendor published documentation
    # tested     confirmed by observing the product behave that way
    # What the criterion rests on. Not how many readers it had.
    L.append(fld('confidence', c.get('confidence') or 'derived'))
    if c.get('revised_on_verification'):
        L.append(fld('revised', 'yes'))
    L.append(fld('cci', ' '.join(r['cci'])))
    if controls:
        L.append(fld('control_rev5', ' '.join(controls)))
    L.append('')
    if c.get('application_contribution'):
        L.append(fld('contribution', wrap(c['application_contribution'])))
        L.append('')
    for conf in confs:
        g = gloss.get(conf)
        if g:
            L.append(fld('governs', '%s - %s' % (conf, wrap(g['description']))))
    if confs:
        L.append('')
    for k in (c.get('conditions') or []):
        L.append(fld('check', condition_line(k)))
    if c.get('conditions'):
        L.append('')
    for e in (c.get('external_dependencies') or []):
        L.append(fld('external', wrap(e)))
    if c.get('external_dependencies'):
        L.append('')
    if c.get('manual_reason'):
        L.append(fld('manual_reason', wrap(c['manual_reason'])))
        L.append('')
    if c.get('citation'):
        L.append(fld('citation', wrap(c['citation'])))
    if c.get('finding_statement'):
        L.append(fld('finding', wrap(c['finding_statement'])))
    L.append('')
    return '\n'.join(L).split('\n')


def header_bounds(lines):
    """Where the leading comment's note starts and ends, or None.

    The note is the run of comment lines after the lone '#' that follows the
    title. A file whose comment does not have that shape is left alone rather
    than guessed at.
    """
    if not lines or not lines[0].startswith('# '):
        return None
    try:
        sep = lines.index('#')
    except ValueError:
        return None
    if any(not l.startswith('# ') for l in lines[:sep]):
        return None
    end = sep + 1
    while end < len(lines) and lines[end].startswith('#'):
        end += 1
    return sep, end


def without_note(lines):
    """The file minus the generated note, so a stale note is not a customization."""
    b = header_bounds(lines)
    if not b:
        return list(lines)
    sep, end = b
    return lines[:sep + 1] + lines[end:]


def criteria_shape(lines):
    """The decision-bearing lines, in order. Continuation prose is indented and
    so is not one of them."""
    return [l for l in lines if l.split(':', 1)[0] in CRITERIA_FIELDS]


def find_field(lines, name):
    pre = name + ':'
    for i, l in enumerate(lines):
        if l.startswith(pre):
            return i
    return -1


def place_field(lines, name):
    """Where a header field belongs in a file that does not carry it."""
    i = FIELD_ORDER.index(name)
    for p in reversed(FIELD_ORDER[:i]):
        j = find_field(lines, p)
        if j >= 0:
            return j + 1
    for p in FIELD_ORDER[i + 1:]:
        j = find_field(lines, p)
        if j >= 0:
            return j
    return len(lines)


def set_field(lines, name, value):
    """Give a header field the benchmark's value. True when the file moved."""
    i = find_field(lines, name)
    if value is None:
        if i < 0:
            return False
        del lines[i]
        return True
    line = fld(name, value)
    if i < 0:
        lines.insert(place_field(lines, name), line)
        return True
    if lines[i] != line:
        lines[i] = line
        return True
    return False


def refresh(lines, sid, r, ccimap):
    """Bring the benchmark's fields up to date. Returns the fields that moved."""
    moved = []
    want = {'group': r['group_id'],
            'severity': r['severity'],
            'cat': SEV_CAT.get(r['severity'], ''),
            'cci': ' '.join(r['cci'])}
    controls = controls_of(r, ccimap)
    want['control_rev5'] = ' '.join(controls) if controls else None
    for name in BENCH_FIELDS:
        if set_field(lines, name, want[name]):
            moved.append(name)

    b = header_bounds(lines)
    if b:
        sep, _ = b
        cb = comment_block(sid, r)
        title = cb[:cb.index('#') + 1]       # the requirement line and the title
        if lines[:sep + 1] != title:
            lines[:sep + 1] = title
            moved.insert(0, 'title')
    return moved


def set_note(lines):
    """Restate the note. True when the file carried different wording."""
    b = header_bounds(lines)
    if not b:
        return False
    sep, end = b
    if lines[sep + 1:end] == HEADER_NOTE:
        return False
    lines[sep + 1:end] = HEADER_NOTE
    return True


def write_atomic(path, lines):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
    os.replace(tmp, path)


def load_glossary(path):
    gloss = {}
    if not os.path.isfile(path):
        return gloss
    with open(path, encoding='utf-8') as fh:
        head = fh.readline().rstrip('\n').split('\t')
        for line in fh:
            f = line.rstrip('\n').split('\t')
            if len(f) >= len(head):
                gloss[f[0]] = dict(zip(head, f))
    return gloss


def main(argv):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description='Scaffold and refresh the rule files.')
    ap.add_argument('root', nargs='?', default=here,
                    help='the assess directory holding inventory/ and rules/')
    ap.add_argument('--apply', action='store_true', help='write; otherwise report only')
    ap.add_argument('--refresh-header', action='store_true',
                    help='also restate the generated note where a file carries '
                         'superseded wording')
    a = ap.parse_args(argv[1:])

    root = a.root
    inv = lambda n: json.load(open(os.path.join(root, 'inventory', n), encoding='utf-8'))
    crit = {c['srg_id']: c for c in inv('criteria.json') if c.get('srg_id')}
    rules = {r['srg_id']: r for r in inv('srg-rules.json')}
    dets = {d['srg_id']: d for d in inv('sca-determinations.json')}
    ccimap = inv('cci-map.json')
    gloss = load_glossary(os.path.join(root, 'inventory', 'conf-glossary.tsv'))

    out_dir = os.path.join(root, 'rules')
    os.makedirs(out_dir, exist_ok=True)
    present = {f[:-5] for f in os.listdir(out_dir) if f.endswith('.rule')}

    scaffolded, refreshed, untouched, review = [], [], [], []
    customized, diverges, note_stale = [], [], []
    no_criterion, no_benchmark, unreadable = [], [], []
    written = 0
    # Counted from each rule file's own decidable:, which is what the evaluator
    # reads, rather than from criteria.json.
    tally = {'machine': 0, 'manual': 0, 'unver': 0}

    for sid in sorted(present | (set(crit) & set(rules))):
        path = os.path.join(out_dir, '%s.rule' % sid)
        r, c, d = rules.get(sid), crit.get(sid), dets.get(sid, {})

        if sid not in present:
            # Scaffolding needs text from the benchmark and conditions from the
            # criteria, so only a requirement carrying both is written.
            lines = render(sid, r, c, d, ccimap, gloss)
            scaffolded.append(sid)
            if a.apply:
                write_atomic(path, lines)
            written += 1
            dec = c.get('decidable', 'manual')
        else:
            with open(path, encoding='utf-8') as fh:
                lines = fh.read().split('\n')
            dec = next((l.split(':', 1)[1].strip() for l in lines
                        if l.startswith('decidable:')), 'manual')

        tally['machine' if dec == 'machine' else 'manual'] += 1
        if c is not None and not c.get('group_verified'):
            tally['unver'] += 1

        if sid in present:
            if not header_bounds(lines):
                unreadable.append(sid)
                continue
            if not r:
                no_benchmark.append(sid)
                continue

            # Refreshed on a copy, so the decision is made before anything is kept.
            probe = list(lines)
            moved = refresh(probe, sid, r, ccimap)
            if c:
                scaffold = render(sid, r, c, d, ccimap, gloss)
                criteria_edited = criteria_shape(probe) != criteria_shape(scaffold)
                if without_note(probe) != without_note(scaffold):
                    diverges.append(sid)
            else:
                no_criterion.append(sid)
                criteria_edited = True      # authored by hand; there is no scaffold form
                diverges.append(sid)
            if criteria_edited:
                customized.append(sid)

            if moved and criteria_edited:
                new = list(lines)           # a conflict is reported, not resolved
                review.append((sid, moved))
            elif moved:
                new = probe
                refreshed.append((sid, moved))
            else:
                new = list(lines)
                untouched.append(sid)

            if set_note(list(lines)):
                note_stale.append(sid)
                if a.refresh_header:
                    set_note(new)

            if new != lines:
                if a.apply:
                    write_atomic(path, new)
                written += 1

    rel = os.path.relpath(out_dir, root)
    print('%d rule file(s) found in %s, %d requirement(s) with a criterion in the benchmark'
          % (len(present), rel, len(set(crit) & set(rules))))
    print('  scaffolded               : %d' % len(scaffolded))
    print('  benchmark text refreshed : %d' % len(refreshed))
    print('  left untouched           : %d' % len(untouched))
    print('  needing review           : %d' % len(review))
    print('  file(s) %-17s: %d' % ('written' if a.apply else 'to write', written))
    print()
    line = lambda label, n, note='': print('  %-40s: %d%s' % (label, n, note))
    line('criteria customized, never rewritten', len(customized))
    line('differing from a scaffold in any respect', len(diverges))
    line('note wording superseded', len(note_stale),
         '' if a.refresh_header else '  (--refresh-header restates it)')
    line('rule file with no criterion', len(no_criterion))
    line('in the benchmark with no criterion yet', len(set(rules) - set(crit)),
         '  (not scaffolded)')
    line('rule file outside the benchmark', len(no_benchmark))
    line('comment shape not recognized', len(unreadable), '  (left alone)')
    print()
    line('machine-decidable', tally['machine'])
    line('manual', tally['manual'])
    line('criterion unverified', tally['unver'], '  (not used to decide a status)')

    if scaffolded:
        print()
        print('  SCAFFOLDED - no rule file existed:')
        for sid in scaffolded:
            print('    %s' % sid)
    if refreshed:
        print()
        print('  REFRESHED - benchmark fields updated, site content untouched:')
        for sid, moved in refreshed:
            print('    %-34s %s' % (sid, ', '.join(moved)))
    if review:
        print()
        print('  NEEDS READING - the benchmark text moved under customized criteria.')
        print('  Nothing was written to these; the requirement may now be asking')
        print('  something different:')
        for sid, moved in review:
            print('    %-34s %s' % (sid, ', '.join(moved)))
    if unreadable:
        print()
        print('  NEEDS READING - comment shape not recognized, so the title and note')
        print('  were not refreshed:')
        for sid in unreadable:
            print('    %s' % sid)
    if no_benchmark:
        print()
        print('  NEEDS READING - no entry in srg-rules.json, so no benchmark text to')
        print('  refresh against:')
        for sid in no_benchmark:
            print('    %s' % sid)

    if not a.apply:
        print()
        print('  dry run. re-run with --apply to write.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
