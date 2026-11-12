#!/usr/bin/env python3
"""Compare two revisions of one DISA SRG and report what the revision changes here.

A revision touches an unknown subset of its requirements, so without a diff a new
release means re-reading the whole benchmark. This reports what moved: added,
withdrawn, changed, unchanged - and for a changed requirement, which part changed.

A changed check text can invalidate the criteria a site wrote against it; a changed
fix text usually cannot. The report separates the two, because that is the
difference between a re-read and a rewrite.

Each requirement is cross-referenced against the rule set, so the report names the
rule file that has to be written, retired, or re-read. Rule files are source, not
build artifacts: a withdrawn requirement's rule file may carry hand-written vendor
verification and retired checks, which is why this names it rather than removing it.

Read-only. Nothing here writes to the rule set or to the benchmarks, so there is no
--apply.

  srg-diff.py --old OLD-xccdf.xml --new NEW-xccdf.xml [--rules DIR] [--json] [--full]
"""
import argparse
import difflib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

# DISA packs several distinct fields into the single XCCDF <description> element as
# escaped pseudo-XML, so a field-by-field diff has to split it first. The same map is
# used by extract-srg.py; fields absent from a benchmark stay empty.
DESC_FIELDS = {
    'VulnDiscussion': 'discussion',
    'FalsePositives': 'false_positives',
    'FalseNegatives': 'false_negatives',
    'Documentable': 'documentable',
    'Mitigations': 'mitigations',
    'SeverityOverrideGuidance': 'security_override_guidance',
    'PotentialImpacts': 'potential_impacts',
    'ThirdPartyTools': 'third_party_tools',
    'MitigationControl': 'mitigation_control',
    'Responsibility': 'responsibility',
    'IAControls': 'ia_controls',
}

# Impact of a changed part, ranked. "criteria" means the change can invalidate what a
# site wrote in its rule file; "metadata" means a rule file field is now stale but the
# assessment logic stands; "narrative" means read it, the criteria still hold.
IMPACT_RANK = {'criteria': 3, 'metadata': 2, 'narrative': 1}

# (field, label, kind, impact). kind drives how a difference is displayed: scalar is a
# one-line value, set is an identifier list, block is wrapped prose or steps.
PARTS = (
    ('check', 'check text', 'block', 'criteria'),
    ('cci', 'CCI set', 'set', 'metadata'),
    ('severity', 'severity', 'scalar', 'metadata'),
    ('group_id', 'group ID (V-number)', 'scalar', 'metadata'),
    ('title', 'title', 'scalar', 'narrative'),
    ('discussion', 'discussion', 'block', 'narrative'),
    ('fix', 'fix text', 'block', 'narrative'),
    ('documentable', 'documentable', 'scalar', 'narrative'),
    ('false_positives', 'false positives', 'block', 'narrative'),
    ('false_negatives', 'false negatives', 'block', 'narrative'),
    ('mitigations', 'mitigations', 'block', 'narrative'),
    ('security_override_guidance', 'severity override guidance', 'block', 'narrative'),
    ('potential_impacts', 'potential impacts', 'block', 'narrative'),
    ('third_party_tools', 'third party tools', 'block', 'narrative'),
    ('mitigation_control', 'mitigation control', 'block', 'narrative'),
    ('responsibility', 'responsibility', 'scalar', 'narrative'),
    ('ia_controls', 'IA controls', 'scalar', 'narrative'),
    ('legacy_ids', 'legacy IDs', 'set', 'narrative'),
)

# Keys a site writes or corrects by hand. A rule file carrying any of them holds work
# that a revision puts at risk, so the report flags it rather than listing it quietly.
INVESTMENT_KEYS = ('vendor', 'retired_check', 'corrected', 'manual_reason', 'revised')

# The rule set's own severity-to-category convention, consistent across all 253 files.
CAT_BY_SEVERITY = {'high': 'CAT I', 'medium': 'CAT II', 'low': 'CAT III'}

MAX_DIFF_LINES = 20


# ---------------------------------------------------------------- benchmark parsing

def _ns(root):
    """Return the namespace map for this document.

    The benchmarks here are XCCDF 1.1 and a later SRG may ship 1.2, so the namespace
    is read off the root element instead of being hardcoded.
    """
    if root.tag.startswith('{'):
        return {'x': root.tag[1:].split('}', 1)[0]}
    return {'x': ''}


def _text(el, path, ns, default=''):
    v = el.findtext(path, default=default, namespaces=ns)
    return (v or default).strip()


def split_description(raw):
    """Pull the sub-fields out of the description blob."""
    out = {v: '' for v in DESC_FIELDS.values()}
    if not raw:
        return out
    found = False
    for tag, key in DESC_FIELDS.items():
        m = re.search(r'<%s>(.*?)</%s>' % (tag, tag), raw, re.S)
        if m:
            out[key] = m.group(1).strip()
            found = True
    if not found:
        # Not every benchmark wraps its description. Keep the text as the discussion
        # rather than discarding it from the comparison.
        out['discussion'] = raw.strip()
    return out


def rule_revision(rule_id):
    """Return DISA's revision counter out of a rule ID such as SV-206350r960735_rule."""
    m = re.search(r'r(\d+)', rule_id or '')
    return m.group(1) if m else ''


def parse_benchmark(path):
    """Return document metadata and {srg_id: requirement} for one XCCDF file."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        sys.exit('%s: not parseable as XML: %s' % (path, exc))
    ns = _ns(root)

    release = ''
    for pt in root.findall('x:plain-text', ns):
        if pt.get('id') == 'release-info':
            release = ' '.join((pt.text or '').split())
    status = root.find('x:status', ns)
    doc = {
        'path': os.path.abspath(path),
        'file': os.path.basename(path),
        'title': _text(root, 'x:title', ns),
        'version': _text(root, 'x:version', ns),
        'release_info': release,
        'release': '',
        'status': (status.text or '').strip() if status is not None else '',
        'status_date': status.get('date', '') if status is not None else '',
    }
    m = re.search(r'Release:\s*(\d+)', release)
    if m:
        doc['release'] = m.group(1)

    reqs = {}
    collisions = []
    keyless = []
    for group in root.findall('.//x:Group', ns):
        rule = group.find('x:Rule', ns)
        if rule is None:
            continue
        idents = [(i.get('system', '').rsplit('/', 1)[-1], (i.text or '').strip())
                  for i in rule.findall('x:ident', ns)]
        desc = split_description(_text(rule, 'x:description', ns))
        srg_id = _text(rule, 'x:version', ns)
        req = {
            'srg_id': srg_id,
            'group_id': group.get('id') or '',
            'rule_id': rule.get('id') or '',
            'rule_revision': rule_revision(rule.get('id')),
            'severity': rule.get('severity', 'unknown'),
            'title': _text(rule, 'x:title', ns),
            'check': _text(rule, './/x:check-content', ns),
            'fix': _text(rule, 'x:fixtext', ns),
            'cci': sorted(v for s, v in idents if s == 'cci'),
            'legacy_ids': sorted(v for s, v in idents if s == 'legacy'),
        }
        req.update(desc)
        if not srg_id:
            # The SRG ID is the key the rule set and the checklist are both built on.
            # Without one the group ID is the only handle left.
            req['srg_id'] = req['group_id']
            keyless.append(req['group_id'])
        if req['srg_id'] in reqs:
            collisions.append(req['srg_id'])
            continue
        reqs[req['srg_id']] = req

    doc['count'] = len(reqs)
    doc['collisions'] = sorted(set(collisions))
    doc['keyless'] = keyless
    return doc, reqs


# ---------------------------------------------------------------- rule set index

def parse_rule_file(path):
    """Return the fields and hand-written markers of one rule file."""
    info = {
        'path': path,
        'file': os.path.basename(path),
        'exists': True,
        'id': '',
        'group': '',
        'severity': '',
        'cat': '',
        'cci': '',
        'determination': '',
        'decidable': '',
        'confidence': '',
        'counts': {},
    }
    counts = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = re.match(r'([a-z_]+):\s*(.*)$', line)
            if not m:
                continue
            key, val = m.group(1), m.group(2).strip()
            counts[key] = counts.get(key, 0) + 1
            if key in ('id', 'group', 'severity', 'cat', 'cci', 'determination',
                       'decidable', 'confidence') and not info[key]:
                info[key] = val
    info['counts'] = counts
    info['investment'] = [(k, counts[k]) for k in INVESTMENT_KEYS if counts.get(k)]
    return info


def load_rules(rules_dir):
    """Return {srg_id: rule info} keyed by the file's own id field."""
    index, warnings = {}, []
    if not rules_dir or not os.path.isdir(rules_dir):
        return index, ['rule directory %s does not exist, so no rule file is '
                       'cross-referenced' % rules_dir] if rules_dir else []
    for name in sorted(os.listdir(rules_dir)):
        if not name.endswith('.rule'):
            continue
        info = parse_rule_file(os.path.join(rules_dir, name))
        key = info['id'] or name[:-5]
        if info['id'] and info['id'] != name[:-5]:
            warnings.append('%s declares id %s, so the file name and the requirement '
                            'it assesses disagree' % (name, info['id']))
        if key in index:
            warnings.append('%s and %s both claim id %s' % (
                index[key]['file'], name, key))
            continue
        index[key] = info
    return index, warnings


def rule_for(index, rules_dir, srg_id):
    """Return the rule file info for a requirement, present or not."""
    if srg_id in index:
        return index[srg_id]
    return {
        'path': os.path.join(rules_dir, '%s.rule' % srg_id) if rules_dir else '',
        'file': '%s.rule' % srg_id,
        'exists': False,
        'investment': [],
        'counts': {},
    }


INVESTMENT_LABEL = {
    'vendor': '%d vendor pointer(s)',
    'retired_check': '%d retired check(s)',
    'corrected': '%d corrected criterion(s)',
    'manual_reason': '%d written manual-check reason(s)',
    'revised': 'criteria marked revised',
}


def investment_text(rule):
    if not rule.get('investment'):
        return ''
    out = []
    for key, n in rule['investment']:
        label = INVESTMENT_LABEL.get(key, '%d ' + key.replace('_', ' '))
        out.append(label % n if '%d' in label else label)
    return ', '.join(out)


# ---------------------------------------------------------------- comparison

def collapse(text):
    """The comparison form: every run of whitespace becomes one space.

    DISA re-wraps requirement text between releases, so a comparison that keeps line
    breaks reports a reflow as a changed requirement.
    """
    return ' '.join((text or '').split())


# A sentence boundary, not a boundary after a list label such as "1." or "a.".
SENTENCE_END = re.compile(r'(?<=[.!?:])(?<![A-Za-z0-9][.])\s+(?=[A-Z("\'])')


def display_lines(text):
    """The units of a shown diff: one sentence each, paragraphs kept apart.

    Sentences rather than source lines keep the displayed diff stable when only the
    line wrapping moved.
    """
    out = []
    body = (text or '').replace('\r\n', '\n').replace('\r', '\n')
    for para in re.split(r'\n\s*\n', body):
        para = ' '.join(para.split())
        if para:
            out.extend(SENTENCE_END.split(para))
    return out


def part_diff(field, kind, old, new, full=False):
    """Return the displayable difference for one part, or None if it is equal."""
    if kind == 'set':
        o, n = list(old.get(field) or []), list(new.get(field) or [])
        if o == n:
            return None
        return {
            'old': ', '.join(o) or '(none)',
            'new': ', '.join(n) or '(none)',
            'added': [x for x in n if x not in o],
            'removed': [x for x in o if x not in n],
            'diff': [],
        }
    o_raw, n_raw = old.get(field) or '', new.get(field) or ''
    o, n = collapse(o_raw), collapse(n_raw)
    if o == n:
        return None
    if kind == 'scalar':
        return {'old': o or '(empty)', 'new': n or '(empty)', 'diff': []}
    o_disp, n_disp = display_lines(o_raw), display_lines(n_raw)
    lines = list(difflib.unified_diff(o_disp, n_disp, lineterm='', n=1))[2:]
    truncated = 0
    if not full and len(lines) > MAX_DIFF_LINES:
        truncated = len(lines) - MAX_DIFF_LINES
        lines = lines[:MAX_DIFF_LINES]
    return {
        'old': o,
        'new': n,
        'diff': lines,
        'truncated': truncated,
        'old_lines': len(o_disp),
        'new_lines': len(n_disp),
    }


def compare_requirement(old, new, full=False):
    """Return the list of changed parts for one requirement, highest impact first."""
    parts = []
    for field, label, kind, impact in PARTS:
        d = part_diff(field, kind, old, new, full)
        if d is None:
            continue
        d.update({'part': field, 'label': label, 'kind': kind, 'impact': impact})
        parts.append(d)
    parts.sort(key=lambda p: -IMPACT_RANK[p['impact']])
    return parts


def whitespace_only(old, new):
    """True when two otherwise equal requirements differ in how their text is wrapped.

    Only meaningful for a requirement that compared equal, where any remaining raw
    difference is a re-wrap.
    """
    return any((old.get(field) or '') != (new.get(field) or '')
               for field, _label, kind, _impact in PARTS if kind != 'set')


def diff_benchmarks(old_doc, old_reqs, new_doc, new_reqs, rules, rules_dir, full=False):
    old_ids, new_ids = set(old_reqs), set(new_reqs)

    added_ids = sorted(new_ids - old_ids)
    withdrawn_ids = sorted(old_ids - new_ids)

    # A requirement whose SRG ID changed but whose group ID did not is re-identified,
    # not withdrawn and replaced. Reported separately so its rule file is not retired
    # by mistake.
    old_by_group = {}
    for sid in withdrawn_ids:
        g = old_reqs[sid]['group_id']
        if g:
            old_by_group.setdefault(g, []).append(sid)
    reidentified = []
    for sid in list(added_ids):
        g = new_reqs[sid]['group_id']
        cands = old_by_group.get(g) or []
        if len(cands) == 1:
            old_sid = cands[0]
            reidentified.append({
                'old_srg_id': old_sid,
                'new_srg_id': sid,
                'group_id': g,
                'title': new_reqs[sid]['title'],
                'parts': compare_requirement(old_reqs[old_sid], new_reqs[sid], full),
                'rule': rule_for(rules, rules_dir, old_sid),
            })
            added_ids.remove(sid)
            withdrawn_ids.remove(old_sid)
            old_by_group[g] = []

    changed, unchanged, ws_only, rev_bump = [], [], [], []
    for sid in sorted(old_ids & new_ids):
        o, n = old_reqs[sid], new_reqs[sid]
        parts = compare_requirement(o, n, full)
        if parts:
            changed.append({
                'srg_id': sid,
                'group_id': n['group_id'],
                'title': n['title'],
                'severity': n['severity'],
                'impact': max((p['impact'] for p in parts),
                              key=lambda i: IMPACT_RANK[i]),
                'rule_revision_old': o['rule_revision'],
                'rule_revision_new': n['rule_revision'],
                'parts': parts,
                'rule': rule_for(rules, rules_dir, sid),
            })
        else:
            unchanged.append(sid)
            if whitespace_only(o, n):
                ws_only.append(sid)
            if o['rule_revision'] and o['rule_revision'] != n['rule_revision']:
                # DISA bumped the rule revision without changing any compared part, so
                # something outside the compared fields moved.
                rev_bump.append({'srg_id': sid, 'old': o['rule_revision'],
                                 'new': n['rule_revision']})

    changed.sort(key=lambda c: (-IMPACT_RANK[c['impact']], c['srg_id']))

    def entry(sid, reqs):
        r = reqs[sid]
        return {
            'srg_id': sid,
            'group_id': r['group_id'],
            'title': r['title'],
            'severity': r['severity'],
            'cat': CAT_BY_SEVERITY.get(r['severity'], ''),
            'cci': r['cci'],
            'rule': rule_for(rules, rules_dir, sid),
        }

    return {
        'old': old_doc,
        'new': new_doc,
        'same_srg': old_doc['title'] == new_doc['title'],
        'summary': {
            'added': len(added_ids),
            'withdrawn': len(withdrawn_ids),
            'reidentified': len(reidentified),
            'changed': len(changed),
            'unchanged': len(unchanged),
            'whitespace_only': len(ws_only),
            'criteria_impact': sum(1 for c in changed if c['impact'] == 'criteria'),
            'metadata_impact': sum(1 for c in changed if c['impact'] == 'metadata'),
            'narrative_impact': sum(1 for c in changed if c['impact'] == 'narrative'),
        },
        'added': [entry(s, new_reqs) for s in added_ids],
        'withdrawn': [entry(s, old_reqs) for s in withdrawn_ids],
        'reidentified': reidentified,
        'changed': changed,
        'unchanged': {'count': len(unchanged), 'srg_ids': unchanged,
                      'whitespace_only': ws_only,
                      'rule_revision_bumped': rev_bump},
    }


# ---------------------------------------------------------------- report

def _num(text):
    """Coerce a version or release string to a number.

    A benchmark that labels its version non-numerically must not abort the report, so
    an unparseable value sorts as 0 and the ordering check simply does not fire.
    """
    m = re.match(r'\s*(\d+)', text or '')
    return int(m.group(1)) if m else 0


def hr(title):
    return '\n%s\n%s' % (title, '-' * len(title))


def emit(result, rules_dir, warnings, out=sys.stdout):
    w = out.write
    old, new, s = result['old'], result['new'], result['summary']

    w('SRG revision diff\n')
    w('=================\n\n')
    for label, doc in (('old', old), ('new', new)):
        w('%-4s %s\n' % (label, doc['file']))
        w('     %s  version %s  %s\n' % (
            doc['title'] or '(untitled)', doc['version'] or '?',
            doc['release_info'] or '(no release info)'))
        w('     %s %s, %d requirement(s)\n' % (
            doc['status'] or 'status unknown', doc['status_date'], doc['count']))
    if rules_dir:
        w('\nrules %s\n' % rules_dir)

    notes = list(warnings)
    if not result['same_srg']:
        notes.append('the two documents are different SRGs ("%s" against "%s"), so '
                     'this is not a revision comparison: every requirement reports as '
                     'added or withdrawn' % (old['title'], new['title']))
    if (old['release_info'] and old['release_info'] == new['release_info']
            and old['title'] == new['title']):
        notes.append('both documents are the same release, so no change is expected')
    if (old['title'] == new['title'] and old['release'] and new['release']
            and (_num(old['version']), _num(old['release']))
            > (_num(new['version']), _num(new['release']))):
        notes.append('the document given as --old is a later release than --new; the '
                     'arguments may be swapped')
    for doc, label in ((old, 'old'), (new, 'new')):
        if doc['collisions']:
            notes.append('%s: %d SRG ID(s) appear more than once and only the first was '
                         'kept: %s' % (label, len(doc['collisions']),
                                       ', '.join(doc['collisions'])))
        if doc['keyless']:
            notes.append('%s: %d requirement(s) carry no SRG ID and were keyed on their '
                         'group ID: %s' % (label, len(doc['keyless']),
                                           ', '.join(doc['keyless'])))
    if notes:
        w(hr('NOTES') + '\n')
        for n in notes:
            w('  - %s\n' % n)

    w(hr('SUMMARY') + '\n')
    w('  added        %4d   new requirement(s): each needs a criterion and a rule file\n'
      % s['added'])
    w('  withdrawn    %4d   gone from the new document: rule file orphaned\n'
      % s['withdrawn'])
    w('  re-identified%4d   same group ID, new SRG ID: rename, not a withdrawal\n'
      % s['reidentified'])
    w('  changed      %4d   %d criteria-affecting, %d metadata, %d narrative\n' % (
        s['changed'], s['criteria_impact'], s['metadata_impact'],
        s['narrative_impact']))
    w('  unchanged    %4d   %d of them re-wrapped text only\n' % (
        s['unchanged'], s['whitespace_only']))

    # Added
    w(hr('ADDED - %d' % s['added']) + '\n')
    if not result['added']:
        w('  none\n')
    for e in result['added']:
        w('\n  %s  %s  %s\n' % (e['srg_id'], e['cat'] or e['severity'], e['group_id']))
        w('      %s\n' % wrap(e['title'], 6))
        w('      CCI %s\n' % (', '.join(e['cci']) or '(none)'))
        if e['rule']['exists']:
            w('      *** a rule file already exists for a requirement absent from the '
              'old document: %s\n' % e['rule']['file'])
            w('          it was scaffolded ahead of the benchmark or belongs to another '
              'baseline; confirm before relying on it\n')
        else:
            w('      no rule file yet: %s must be written\n' % e['rule']['file'])

    # Withdrawn
    w(hr('WITHDRAWN - %d' % s['withdrawn']) + '\n')
    if not result['withdrawn']:
        w('  none\n')
    for e in result['withdrawn']:
        w('\n  %s  %s  %s\n' % (e['srg_id'], e['cat'] or e['severity'], e['group_id']))
        w('      %s\n' % wrap(e['title'], 6))
        if e['rule']['exists']:
            inv = investment_text(e['rule'])
            w('      orphaned rule file: %s\n' % e['rule']['path'])
            if inv:
                w('      *** carries hand-written work (%s): read it before retiring '
                  'it\n' % inv)
            w('          the checklist should stop carrying this requirement\n')
        else:
            w('      no rule file exists, so nothing to retire\n')

    # Re-identified
    if result['reidentified']:
        w(hr('RE-IDENTIFIED - %d' % s['reidentified']) + '\n')
        for e in result['reidentified']:
            w('\n  %s -> %s  (group %s)\n' % (
                e['old_srg_id'], e['new_srg_id'], e['group_id']))
            w('      %s\n' % wrap(e['title'], 6))
            if e['rule']['exists']:
                w('      rename the rule file: %s -> %s.rule\n' % (
                    e['rule']['file'], e['new_srg_id']))
            else:
                w('      no rule file under either ID\n')
            if e['parts']:
                w('      the requirement text also changed:\n')
                for p in e['parts']:
                    w('        %s (%s)\n' % (p['label'], p['impact']))

    # Changed
    w(hr('CHANGED - %d' % s['changed']) + '\n')
    if not result['changed']:
        w('  none\n')
    for c in result['changed']:
        w('\n  %s  %s  %s   [%s]\n' % (
            c['srg_id'], CAT_BY_SEVERITY.get(c['severity'], c['severity']),
            c['group_id'], c['impact']))
        w('      %s\n' % wrap(c['title'], 6))
        if c['rule_revision_old'] != c['rule_revision_new']:
            w('      DISA rule revision r%s -> r%s\n' % (
                c['rule_revision_old'] or '?', c['rule_revision_new'] or '?'))
        else:
            w('      *** DISA did not change the rule revision (r%s) although the '
              'text did\n' % (c['rule_revision_new'] or '?'))
        emit_rule_note(w, c)
        for p in c['parts']:
            w('\n      %s changed  (%s)\n' % (p['label'], p['impact']))
            w('%s' % render_part(p))
            w('        %s\n' % consequence(p))

    # Unchanged
    u = result['unchanged']
    w(hr('UNCHANGED - %d' % u['count']) + '\n')
    w('  %d requirement(s) identical in both documents\n' % u['count'])
    if u['whitespace_only']:
        w('  %d of them differ only in line wrapping, which is not a change to the '
          'requirement\n' % len(u['whitespace_only']))
    if u['rule_revision_bumped']:
        w('\n  *** %d unchanged requirement(s) carry a new DISA rule revision, so\n'
          '      something outside the %d compared fields moved; read the requirement\n'
          % (len(u['rule_revision_bumped']), len(PARTS)))
        for e in u['rule_revision_bumped']:
            w('      %s  r%s -> r%s\n' % (e['srg_id'], e['old'], e['new']))


def emit_rule_note(w, c):
    """State what the changed requirement's rule file is and what it holds."""
    rule = c['rule']
    if not rule['exists']:
        w('      no rule file: %s does not exist, so nothing is invalidated\n'
          % rule['file'])
        return
    checks = rule['counts'].get('check', 0)
    w('      rule file %s  (%d check line(s), determination %s, decidable %s)\n' % (
        rule['file'], checks, rule.get('determination') or '?',
        rule.get('decidable') or '?'))
    inv = investment_text(rule)
    criteria_hit = any(p['impact'] == 'criteria' for p in c['parts'])
    if inv and criteria_hit:
        w('      *** this rule file carries hand-written work (%s) and the check text '
          'moved:\n          re-read the criteria against the new check text before '
          'the next assessment\n' % inv)
    elif inv:
        w('      *** carries hand-written work (%s); the check text did not move, so '
          'the criteria stand\n' % inv)
    for p in c['parts']:
        if p['part'] == 'severity':
            w('          rule file records severity %s / %s; the new document says %s, '
              'so cat must become %s\n' % (
                  rule.get('severity') or '?', rule.get('cat') or '?',
                  p['new'], CAT_BY_SEVERITY.get(p['new'], '?')))
        if p['part'] == 'cci':
            w('          rule file records cci %s; re-run map-cci.py so control_rev5 '
              'follows the new CCI set\n' % (rule.get('cci') or '?'))
        if p['part'] == 'group_id':
            w('          rule file records group %s; the checklist V-number changes\n'
              % (rule.get('group') or '?'))


def consequence(part):
    """Say what the changed part costs, so a re-read is not confused with a rewrite."""
    return {
        'check': 'the criteria in the rule file were written against the old check '
                 'text: re-read them, they may no longer assess this requirement',
        'cci': 'the control mapping moves with the CCI set: re-run map-cci.py and '
               'update the rule file cci and control_rev5 fields',
        'severity': 'mechanical: update severity and cat in the rule file; the '
                    'criteria are unaffected',
        'group_id': 'mechanical: the checklist carries the new V-number; the criteria '
                    'are unaffected',
        'fix': 'the fix text is remediation guidance and no criterion is derived from '
               'it: no rewrite implied',
        'title': 'the rule file header comment carries the title; cosmetic',
        'discussion': 'rationale only, but read it: a widened discussion can widen '
                      'what the check text is taken to mean',
    }.get(part['part'],
          'narrative field: read it, the criteria are unaffected')


def wrap(text, indent, width=86):
    """Wrap one line of text for the report."""
    words, lines, cur = ' '.join((text or '').split()).split(), [], ''
    for word in words:
        if cur and len(cur) + 1 + len(word) > width - indent:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + ' ' + word).strip()
    if cur:
        lines.append(cur)
    return ('\n' + ' ' * indent).join(lines) or '(no title)'


def render_part(part):
    out = []
    if part['kind'] == 'set':
        if part.get('removed'):
            out.append('        removed: %s\n' % ', '.join(part['removed']))
        if part.get('added'):
            out.append('        added:   %s\n' % ', '.join(part['added']))
    elif part['kind'] == 'scalar':
        out.append('        old: %s\n' % wrap(part['old'], 13))
        out.append('        new: %s\n' % wrap(part['new'], 13))
    else:
        out.append('        %d sentence(s) -> %d sentence(s)\n' % (
            part.get('old_lines', 0), part.get('new_lines', 0)))
        for line in part['diff']:
            out.append('        %s\n' % line.rstrip())
        if part.get('truncated'):
            out.append('        ... %d more diff line(s); --full shows them all\n'
                       % part['truncated'])
    return ''.join(out)


# ---------------------------------------------------------------- entry point

def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    default_rules = os.path.join(here, os.pardir, 'assess', 'rules')
    ap = argparse.ArgumentParser(
        description='Compare two revisions of one DISA SRG and report what changed, '
                    'cross-referenced against the rule set. Read-only.')
    ap.add_argument('--old', required=True, help='the earlier XCCDF document')
    ap.add_argument('--new', required=True, help='the later XCCDF document')
    ap.add_argument('--rules', default=os.path.normpath(default_rules),
                    help='rule directory to cross-reference (default: assess/rules)')
    ap.add_argument('--no-rules', action='store_true',
                    help='skip the rule set cross-reference')
    ap.add_argument('--json', action='store_true',
                    help='emit the result as JSON instead of the report')
    ap.add_argument('--full', action='store_true',
                    help='show every diff line rather than the first %d per part'
                         % MAX_DIFF_LINES)
    args = ap.parse_args(argv[1:])

    for p in (args.old, args.new):
        if not os.path.isfile(p):
            sys.exit('missing input: %s' % p)

    old_doc, old_reqs = parse_benchmark(args.old)
    new_doc, new_reqs = parse_benchmark(args.new)
    if not old_reqs or not new_reqs:
        sys.exit('no requirements parsed from %s - check the XCCDF namespace'
                 % (args.old if not old_reqs else args.new))

    rules_dir = '' if args.no_rules else os.path.abspath(args.rules)
    rules, warnings = load_rules(rules_dir)

    result = diff_benchmarks(old_doc, old_reqs, new_doc, new_reqs,
                             rules, rules_dir, args.full)
    result['warnings'] = warnings
    result['rules_dir'] = rules_dir
    result['rules_indexed'] = len(rules)

    if args.json:
        json.dump(result, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write('\n')
    else:
        emit(result, rules_dir, warnings)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
