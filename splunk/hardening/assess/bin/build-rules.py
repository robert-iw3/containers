#!/usr/bin/env python3
"""Generate one rule file per requirement.

A rule file is the unit a site customizes. It holds everything needed to assess
one requirement - what it asks, what the application can do about it, the
conditions that decide it, and where each of those came from - in a format that
is read by shell at run time and edited by hand without tooling.

One requirement per file on purpose. A site that disagrees with a determination
edits that file; it does not fork the toolkit, regenerate an inventory, or hold a
patch against a large generated document.

Regenerating OVERWRITES. A site keeping local edits should hold them in version
control, which is why the files are small and line-oriented.
"""
import json
import os
import re
import sys

SEV_CAT = {'high': 'CAT I', 'medium': 'CAT II', 'low': 'CAT III'}


def wrap(text, width=74, indent=' ' * 17):
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


def condition_line(c):
    """conf [stanza] key operator value - the form the evaluator reads."""
    stanza = '[%s]' % c.get('stanza', '') if c.get('stanza') else '[]'
    op = c.get('operator', '')
    val = (c.get('value') or '').strip()
    return ' '.join(x for x in (c.get('conf', ''), stanza, c.get('key', ''), op, val) if x)


def main(argv):
    root = argv[1] if len(argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    inv = lambda n: json.load(open(os.path.join(root, 'inventory', n), encoding='utf-8'))
    crit = inv('criteria.json')
    rules = {r['srg_id']: r for r in
             json.load(open(os.path.join(os.path.dirname(root), 'assess', 'inventory',
                                         'srg-rules.json'), encoding='utf-8'))}
    dets = {d['srg_id']: d for d in inv('sca-determinations.json')}
    ccimap = inv('cci-map.json')
    gloss = {}
    gp = os.path.join(root, 'inventory', 'conf-glossary.tsv')
    if os.path.isfile(gp):
        with open(gp, encoding='utf-8') as fh:
            head = fh.readline().rstrip('\n').split('\t')
            for line in fh:
                f = line.rstrip('\n').split('\t')
                if len(f) >= len(head):
                    gloss[f[0]] = dict(zip(head, f))

    out_dir = os.path.join(root, 'rules')
    os.makedirs(out_dir, exist_ok=True)
    for old in os.listdir(out_dir):
        if old.endswith('.rule'):
            os.remove(os.path.join(out_dir, old))

    n = machine = manual = unver = 0
    for c in sorted(crit, key=lambda x: x.get('srg_id', '')):
        sid = c.get('srg_id')
        r = rules.get(sid)
        if not r:
            continue
        d = dets.get(sid, {})
        controls = sorted({(ccimap.get(x) or {}).get('controls', {}).get('5', '').split()[0]
                           for x in r['cci'] if (ccimap.get(x) or {}).get('controls', {}).get('5')})
        confs = sorted({k.get('conf') for k in (c.get('conditions') or []) if k.get('conf')})

        L = []
        L.append('# %s  -  %s' % (sid, SEV_CAT.get(r['severity'], r['severity'])))
        L.append('# %s' % wrap(r['title'], 74, '# '))
        L.append('#')
        L.append('# Generated from the benchmark and the assessment determinations. Edit this')
        L.append('# file to change how this requirement is assessed here; it is read at run')
        L.append('# time. Regenerating overwrites it.')
        L.append('')
        L.append('id:              %s' % sid)
        L.append('group:           %s' % r['group_id'])
        L.append('severity:        %s' % r['severity'])
        L.append('cat:             %s' % SEV_CAT.get(r['severity'], ''))
        L.append('determination:   %s' % d.get('determination', 'UNDETERMINED'))
        L.append('grade:           %s' % d.get('evidence_grade', '-'))
        L.append('decidable:       %s' % c.get('decidable', 'manual'))
        # derived    from the benchmark text and the shipped specification only
        # documented confirmed against the vendor published documentation
        # tested     confirmed by observing the product behave that way
        # What the criterion rests on. Not how many readers it had.
        L.append('confidence:      %s' % (c.get('confidence') or 'derived'))
        if c.get('revised_on_verification'):
            L.append('revised:         yes')
        L.append('cci:             %s' % ' '.join(r['cci']))
        if controls:
            L.append('control_rev5:    %s' % ' '.join(controls))
        L.append('')
        if c.get('application_contribution'):
            L.append('contribution:    %s' % wrap(c['application_contribution']))
            L.append('')
        for conf in confs:
            g = gloss.get(conf)
            if g:
                L.append('governs:         %s - %s' % (conf, wrap(g['description'])))
        if confs:
            L.append('')
        for k in (c.get('conditions') or []):
            L.append('check:           %s' % condition_line(k))
        if c.get('conditions'):
            L.append('')
        for e in (c.get('external_dependencies') or []):
            L.append('external:        %s' % wrap(e))
        if c.get('external_dependencies'):
            L.append('')
        if c.get('manual_reason'):
            L.append('manual_reason:   %s' % wrap(c['manual_reason']))
            L.append('')
        if c.get('citation'):
            L.append('citation:        %s' % wrap(c['citation']))
        if c.get('finding_statement'):
            L.append('finding:         %s' % wrap(c['finding_statement']))
        L.append('')

        with open(os.path.join(out_dir, '%s.rule' % sid), 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(L))
        n += 1
        if c.get('decidable') == 'machine':
            machine += 1
        else:
            manual += 1
        if not c.get('group_verified'):
            unver += 1

    print('%d rule file(s) -> %s' % (n, os.path.relpath(out_dir, root)))
    print('  machine-decidable : %d' % machine)
    print('  manual            : %d' % manual)
    print('  criterion unverified : %d  (not used to decide a status)' % unver)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
