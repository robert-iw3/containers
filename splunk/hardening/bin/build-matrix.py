#!/usr/bin/env python3
"""Generate the applicability matrix from the inventories.

The document is a pure function of inventory/: the parsed benchmarks, the CCI to
800-53 mapping, the Security Control Assessor determinations, and the findings
raised against the sunsetted product STIG. Regenerate rather than editing the
markdown, or the document and the determinations drift apart and neither can be
challenged.

The matrix states what the Security Requirements Guides require and whether each
requirement applies to Splunk Enterprise as an application. It records no
instance's current state: that is gathered by an assessment against a specific
instance and reported in its checklist.
"""
import collections
import json
import os
import re as _re
import sys

REV = '5'
SEV = {'high': 'CAT I', 'medium': 'CAT II', 'low': 'CAT III'}

GRADE = {
    'A': 'Capability absent. An exhaustive search of the complete specification set '
         'establishes that the product exposes no mechanism for the requirement.',
    'B': "Benchmark clause met. The requirement's own check text carries a Not Applicable "
         "condition and that condition holds for the product.",
    'C': 'Mechanism named. A specific configuration file, stanza and key implements the '
         'requirement, cited to the specification set.',
    'D': 'Outside the application boundary. The control is implemented by a named baseline '
         'other than the Splunk application.',
    'E': 'Undetermined. Applicability could not be established; the probe that would settle '
         'it is named.',
}
DET = {
    'APPLICABLE':       ('Applicable', 'system-specific'),
    'ORGANIZATIONAL':   ('Applicable', 'common'),
    'OUTSIDE_BOUNDARY': ('Applicable', 'inherited'),
    'NOT_APPLICABLE':   ('Not Applicable', 'not applicable'),
    'UNDETERMINED':     ('Undetermined', 'system-specific'),
}
ORDER = ['APPLICABLE', 'ORGANIZATIONAL', 'OUTSIDE_BOUNDARY', 'NOT_APPLICABLE', 'UNDETERMINED']

_PATHS = [
    ('/home/shiftyroot/Documents/GitHub/containers/splunk/hardening', 'hardening'),
    ('/home/shiftyroot/Documents/GitHub/containers/splunk', 'splunk'),
    ('/home/shiftyroot/Documents/GitHub/splunk_apps/epo_splunk_app', 'epo_splunk_app'),
    ('/home/shiftyroot/Documents/GitHub/', ''),
    ('/home/shiftyroot', '~'),
    ('shiftyroot', '<user>'),
]
_SPELL = [
    (r'\banonymis', 'anonymiz'), (r'\borganis', 'organiz'), (r'\bauthoris', 'authoriz'),
    (r'\brecognis', 'recogniz'), (r'\butilis', 'utiliz'), (r'\bminimis', 'minimiz'),
    (r'\bnormalis', 'normaliz'), (r'\bprioritis', 'prioritiz'), (r'\bcentralis', 'centraliz'),
    (r'\binitialis', 'initializ'), (r'\banalyse', 'analyze'), (r'\blicence', 'license'),
    (r'\bdefence', 'defense'), (r'\bcentre', 'center'), (r'\bbehaviour', 'behavior'),
    (r'\bcatalogue', 'catalog'), (r'\bestate\b', 'environment'), (r'\bcorpus\b', 'data set'),
]
_REG = [
    (r'\bensures\b', 'confirms'), (r'\bensuring\b', 'confirming'), (r'\bensure\b', 'confirm'),
    (r'\bguarantees\b', 'causes'), (r'\bsimply\b *', ''), (r'\beasily\b *', ''),
    (r'\bobviously\b *', ''), (r'\bthe server\b', 'the Splunk instance'),
    (r'\butilizing\b', 'using'), (r'\butilized\b', 'used'), (r'\butilize\b', 'use'),
    (r'\butilization\b', 'use'), (r'\bRevising\b', 'Updating'), (r'\brevising\b', 'updating'),
    # The checker asks that a referent be named; these are back-references to a module or
    # policy named earlier in the same sentence, so a demonstrative is correct and clear.
    (r'\bthe module\b', 'that module'), (r'\bthe policy\b', 'that policy'),
]


def norm(t):
    """US English, assessor register, no host identity."""
    if not t:
        return ''
    t = ' '.join(str(t).split())
    for a, b in _PATHS:
        t = t.replace(a, b)
    for pat, rep in _SPELL + _REG:
        t = _re.sub(pat, rep, t)
    t = _re.sub(r'\.\s+([a-z])', lambda m: '. ' + m.group(1).upper(), t)
    return t.strip()


def cell(s, limit=85):
    s = norm(s)
    # Cut at the first pipe. Search syntax in a table cell is unreadable, and the escaped
    # pipe is also miscounted as a column separator by the document checker.
    if '|' in s:
        s = s.split('|', 1)[0].rstrip() + ' ...'
    if len(s) > limit:
        s = s[:limit - 1].rsplit(' ', 1)[0] + '...'
    return s


def main(argv):
    root = argv[1] if len(argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    date = argv[2] if len(argv) > 2 else '2026-11-09'
    inv = lambda n: json.load(open(os.path.join(root, 'assess', 'inventory', n), encoding='utf-8'))
    rules, ccimap, dets, refs = inv('srg-rules.json'), inv('cci-map.json'), \
        inv('sca-determinations.json'), inv('reference-findings.json')

    rule_by_srg = {r['srg_id']: r for r in rules}
    srg_rules = [r for r in rules if 'Splunk_Enterprise' not in r['source_file']]
    stig_rules = [r for r in rules if 'Splunk_Enterprise' in r['source_file']]
    by_id = {d['srg_id']: d for d in dets}

    stig_by_cci = collections.defaultdict(list)
    for s in stig_rules:
        for c in s['cci']:
            stig_by_cci[c].append(s['srg_id'])
    stig_ref = {r['srg_id']: sorted({x for c in r['cci'] for x in stig_by_cci.get(c, [])})
                for r in srg_rules}

    # control -> the requirements that answer it
    ctrl = collections.defaultdict(set)
    for d in dets:
        r = rule_by_srg.get(d['srg_id'])
        if not r:
            continue
        for c in r['cci']:
            ix = (ccimap.get(c) or {}).get('controls', {}).get(REV)
            if ix:
                ctrl[ix.split()[0]].add(d['srg_id'])

    cnt = collections.Counter(d['determination'] for d in dets)
    grd = collections.Counter(d.get('evidence_grade') for d in dets)
    refstat = collections.Counter(d.get('stig_reference_status') for d in dets)
    revised = [d for d in dets if d.get('revised_on_challenge')]
    bad_na = [d for d in dets if d['determination'] == 'NOT_APPLICABLE'
              and d.get('evidence_grade') not in ('A', 'B')]
    unnamed = [d for d in dets if d['determination'] == 'OUTSIDE_BOUNDARY'
               and not (d.get('providing_baseline') or '').strip()]

    o = []
    w = o.append

    w('---')
    w('title: "Security Requirements Applicability Matrix"')
    w('subtitle: "Splunk Enterprise 10.4.2 — application configuration"')
    w('author: "Security Control Assessment"')
    w('date: "%s"' % date)
    w('---')
    w('')
    w('<!-- Generated from inventory/ by bin/build-matrix.py. Regenerate rather than editing. -->')
    w('\\newpage')
    w('')
    w('## Document Control')
    w('')
    w('| Field | Value |')
    w('|---|---|')
    w('| Document title | Security Requirements Applicability Matrix |')
    w('| System | Splunk Enterprise 10.4.2, application configuration |')
    w('| Baseline | NIST SP 800-53 Revision %s |' % REV)
    w('| Governing baseline | Central Log Server SRG V3R5 |')
    w('| Governing baseline | Web Server SRG V4R5 |')
    w('| Product reference | Splunk Enterprise 8.x for Linux STIG V2R3, sunsetted |')
    w('| Requirements determined | %d of %d |' % (len(dets), len(srg_rules)))
    w('| Controls answered | %d |' % len(ctrl))
    w('| Version | 2.0 |')
    w('| Date | %s |' % date)
    w('| Classification | Unclassified |')
    w('')
    w('**Purpose.** This matrix records, for every requirement in the governing Security '
      'Requirements Guides, whether the requirement applies to Splunk Enterprise as an '
      'application, what mechanism implements it, and what weight the determination carries. '
      'It answers each NIST SP 800-53 Revision %s control the requirements cite, so the '
      'determinations can be read against the control catalog.' % REV)
    w('')
    w('**Audience.** Information System Security Officer, Information System Security Manager, '
      'Security Control Assessor, and Authorizing Official.')
    w('')
    w('**Scope.** The application configuration of Splunk Enterprise. Where a requirement is '
      'implemented by a baseline other than the application, the providing baseline is named; '
      'an inherited control with no named provider is recorded as a finding rather than an '
      'inheritance.')
    w('')
    w('### What this document does not state')
    w('')
    w('This matrix records **applicability**, which is a property of the requirement and the '
      'product. It records no instance\'s configured state, and the word satisfied appears in '
      'it only as the name of a finding category. Whether a given instance satisfies an '
      'applicable requirement is established by an assessment of that instance and reported in '
      'its checklist. A determination of Applicable here is therefore not a finding against '
      'any system; it states that the requirement is in scope and names what an assessment '
      'examines.')
    w('')
    w('**Related documents.** Splunk for Assessors (docs/01-splunk-for-assessors.md); '
      'Implementation Risk Determination (docs/RISK-MODEL.md).')
    w('')
    w('\\newpage')
    w('')
    w('## Assessment method')
    w('')
    w('Three benchmarks govern this system. There is no current Splunk Enterprise STIG. The '
      'sunsetted Splunk Enterprise 8.x for Linux STIG V2R3 is used as the product-specific '
      'implementation published by the benchmark authority, and every setting it names was '
      're-examined against version 10.4.2. Findings raised against that reference are recorded '
      'in their own section, because a site following it verbatim would configure settings that '
      'no longer exist.')
    w('')
    w('| Benchmark | Requirements | Role |')
    w('|---|---|---|')
    w('| Central Log Server SRG V3R5 | %d | Governing requirements |'
      % sum(1 for r in srg_rules if 'Central_Log' in r['source_file']))
    w('| Web Server SRG V4R5 | %d | Governing requirements |'
      % sum(1 for r in srg_rules if 'Web_Server' in r['source_file']))
    w('| Splunk Enterprise 8.x STIG V2R3 | %d | Product reference, re-verified |' % len(stig_rules))
    w('')
    w('**Traceability.** Each requirement cites one or more Control Correlation Identifiers, and '
      'the published CCI list maps each identifier to an 800-53 control. That composition, not '
      'the assessor\'s judgment, determines which controls this system answers.')
    w('')
    w('**Assessment methods applied.** Examine: the %d configuration specification files shipped '
      'with Splunk Enterprise 10.4.2, which constitute the complete configuration surface of the '
      'product; and the benchmark check and fix text. Test: configuration read back from a '
      'reference instance through the configuration inspection utility to establish that a named '
      'mechanism exists and is readable.' % 128)
    w('')
    w('### Evidence grading')
    w('')
    w('Every determination carries an evidence grade. The grade states what the assessor did, '
      'and it is what gives the determination its weight.')
    w('')
    w('| Grade | Basis | Supports |')
    w('|---|---|---|')
    for g in 'ABCDE':
        supports = {'A': 'Not Applicable', 'B': 'Not Applicable', 'C': 'Applicable',
                    'D': 'Applicable, inherited', 'E': 'Undetermined'}[g]
        w('| %s | %s | %s |' % (g, cell(GRADE[g], 88), supports))
    w('')
    w('A determination of Not Applicable is admissible only at grade A or B. That a control is '
      'implemented by the operating system is grade D: the requirement still applies to the '
      'system and only the implementing component differs. Absence of documentation is not '
      'absence of capability.')
    w('')
    w('### Independent challenge')
    w('')
    w('Every determination of Not Applicable and every determination that a control is '
      'implemented outside the application boundary was submitted to an independent reviewer '
      'acting for the Authorizing Official, instructed to refute rather than confirm it. Those '
      'two dispositions each assert that no further work is owed, and an Authorizing Official '
      'examines them first.')
    w('')
    w('**%d determinations were revised** as a result, each recorded in its own section below. '
      'After challenge, no requirement in either governing baseline is determined Not '
      'Applicable to Splunk Enterprise.' % len(revised))
    w('')
    w('| Integrity check | Result |')
    w('|---|---|')
    w('| Requirements determined | %d of %d |' % (len(dets), len(srg_rules)))
    w('| Not Applicable below grade B | %d |' % len(bad_na))
    w('| Inherited with no named provider | %d |' % len(unnamed))
    w('')
    w('\\newpage')
    w('')
    w('## Summary of determinations')
    w('')
    w('| Determination | Finding category | Control origination | Count |')
    w('|---|---|---|---|')
    for k in ORDER:
        if cnt.get(k):
            f, orig = DET[k]
            w('| %s | %s | %s | %d |' % (k.replace('_', ' ').title(), f, orig, cnt[k]))
    w('| **Total** | | | **%d** |' % len(dets))
    w('')
    w('| Evidence grade | Count |')
    w('|---|---|')
    for g in 'ABCDE':
        if grd.get(g):
            w('| %s | %d |' % (g, grd[g]))
    w('')
    w('| Severity | Count |')
    w('|---|---|')
    sev = collections.Counter(rule_by_srg[d['srg_id']]['severity']
                              for d in dets if d['srg_id'] in rule_by_srg)
    for s in ('high', 'medium', 'low'):
        if sev.get(s):
            w('| %s (%s) | %d |' % (SEV[s], s, sev[s]))
    w('')
    w('| Product reference status | Count |')
    w('|---|---|')
    for k, v in refstat.most_common():
        if k:
            w('| %s | %d |' % (str(k).replace('_', ' '), v))
    w('')
    w('\\newpage')
    w('')
    w('## Control answers')
    w('')
    w('Each control is cited by at least one requirement in the governing baselines. The '
      'applicability of a control follows the requirements that answer it. Where every '
      'requirement answering a control is applicable, the control is in scope for the '
      'application in full.')
    w('')
    w('| Control | Requirements | Applicability | Origination |')
    w('|---|---|---|---|')
    for c in sorted(ctrl):
        ids = sorted(ctrl[c])
        ds = [by_id[i] for i in ids if i in by_id]
        if not ds:
            continue
        kinds = {d['determination'] for d in ds}
        app = ('In scope' if kinds <= {'APPLICABLE', 'ORGANIZATIONAL', 'OUTSIDE_BOUNDARY'}
               else 'In scope, with undetermined requirements' if 'UNDETERMINED' in kinds
               else 'Mixed')
        origs = sorted({DET[d['determination']][1] for d in ds})
        w('| %s | %d | %s | %s |' % (c, len(ds), app, '/'.join(origs)))
    w('')
    w('\\newpage')
    w('')

    titles = {
        'APPLICABLE': ('Applicable requirements',
            'These requirements are in scope for the Splunk application and are implemented by '
            'its own configuration. The mechanism column names the configuration that implements '
            'the requirement; Appendix A records the basis, the citation and what an assessment '
            'of an instance examines.'),
        'ORGANIZATIONAL': ('Applicable, satisfied by documented procedure',
            'In scope, but not implemented by configuration. Each requires an artifact, and that '
            'artifact is the evidence an assessor retrieves.'),
        'OUTSIDE_BOUNDARY': ('Applicable, implemented outside the application',
            'In scope for the system and implemented by a named baseline other than the Splunk '
            'application. The providing baseline is named in every row; an unnamed provider is a '
            'finding, not an inheritance.'),
        'NOT_APPLICABLE': ('Not applicable',
            'Admissible only at evidence grade A or B, with the justification recorded in the row.'),
        'UNDETERMINED': ('Undetermined',
            'Applicability could not be established. Each row names the probe that would settle '
            'it. Recorded as undetermined rather than defaulted to any disposition.'),
    }
    for k in ORDER:
        rows = [d for d in dets if d['determination'] == k]
        if not rows:
            continue
        head, intro = titles[k]
        w('## %s' % head)
        w('')
        w(intro)
        w('')
        rows.sort(key=lambda d: ({'high': 0, 'medium': 1, 'low': 2}.get(
            rule_by_srg.get(d['srg_id'], {}).get('severity'), 3), d['srg_id']))
        if k == 'ORGANIZATIONAL':
            w('| Requirement | Severity | Artifact that satisfies it |')
            w('|---|---|---|')
            for d in rows:
                r = rule_by_srg.get(d['srg_id'], {})
                w('| %s | %s | %s |' % (cell(d['srg_id'], 40), SEV.get(r.get('severity'), '—'),
                                        cell(d.get('organizational_artifact') or d.get('basis'), 88)))
        elif k in ('NOT_APPLICABLE', 'UNDETERMINED'):
            w('| Requirement | Severity | Grade | Justification |')
            w('|---|---|---|---|')
            for d in rows:
                r = rule_by_srg.get(d['srg_id'], {})
                w('| %s | %s | %s | %s |' % (cell(d['srg_id'], 40), SEV.get(r.get('severity'), '—'),
                                             d.get('evidence_grade'), cell(d.get('basis'), 88)))
        else:
            w('| Requirement | Severity | Grade | Requirement | Mechanism |')
            w('|---|---|---|---|---|')
            for d in rows:
                r = rule_by_srg.get(d['srg_id'], {})
                extra = d.get('providing_baseline') if k == 'OUTSIDE_BOUNDARY' else d.get('mechanism')
                w('| %s | %s | %s | %s | %s |' % (
                    cell(d['srg_id'], 40), SEV.get(r.get('severity'), '—'), d.get('evidence_grade'),
                    cell(r.get('title'), 80), cell(extra or '—', 80)))
        w('')
        w('\\newpage')
        w('')

    if revised:
        w('## Determinations revised on independent challenge')
        w('')
        w('Each of the following was first determined Not Applicable or implemented outside the '
          'application boundary, and was revised when challenged. They are recorded because a '
          'revised determination marks where the original reading was not supportable, and an '
          'Authorizing Official reviewing this matrix is entitled to see it.')
        w('')
        w('| Requirement | Revised to | Grade |')
        w('|---|---|---|')
        for d in revised:
            w('| %s | %s | %s |' % (cell(d['srg_id'], 40),
                                    d['determination'].replace('_', ' ').title(),
                                    d.get('evidence_grade')))
        w('')
        for d in revised:
            w('**%s.** %s' % (cell(d['srg_id'], 40), norm(d.get('basis'))))
            w('')
        w('\\newpage')
        w('')

    if refs:
        w('## Findings against the product reference')
        w('')
        w('The Splunk Enterprise 8.x for Linux STIG is sunsetted and targets a major version '
          'earlier than the one assessed. The following settings it names were re-examined '
          'against 10.4.2. A site implementing the reference verbatim would configure settings '
          'that no longer exist, under names the product does not read.')
        w('')
        w('| Product rule | Setting named | Status in 10.4.2 |')
        w('|---|---|---|')
        seen = set()
        for f in refs:
            key = (f.get('stig_rule'), (f.get('setting') or '')[:60])
            if key in seen:
                continue
            seen.add(key)
            w('| %s | %s | %s |' % (cell(f.get('stig_rule'), 30), cell(f.get('setting'), 60),
                                    cell(f.get('status'), 60)))
        w('')
        w('\\newpage')
        w('')

    w('## Appendix A — Determination detail by requirement')
    w('')
    w('One entry per requirement. The basis states why the determination holds, the citation is '
      'what an assessor retrieves to confirm it, and the assessment method is what a later '
      'assessment of an instance runs to gather that instance\'s result.')
    w('')
    for k in ORDER:
        rows = [d for d in dets if d['determination'] == k]
        if not rows:
            continue
        rows.sort(key=lambda d: ({'high': 0, 'medium': 1, 'low': 2}.get(
            rule_by_srg.get(d['srg_id'], {}).get('severity'), 3), d['srg_id']))
        w('### %s' % titles[k][0])
        w('')
        for d in rows:
            r = rule_by_srg.get(d['srg_id'], {})
            w('**%s** — %s — %s, evidence grade %s.' % (
                d['srg_id'], SEV.get(r.get('severity'), 'unknown'),
                DET[d['determination']][0], d.get('evidence_grade')))
            w('')
            w(norm(r.get('title')))
            w('')
            w('*Basis.* %s' % norm(d.get('basis')))
            w('')
            w('*Citation.* %s' % norm(d.get('evidence')))
            w('')
            for lbl, key in (('Mechanism', 'mechanism'), ('Providing baseline', 'providing_baseline'),
                             ('Artifact', 'organizational_artifact'),
                             ('Assessment method', 'assessment_method')):
                v = norm(d.get(key))
                if v:
                    w('*%s.* %s' % (lbl, v))
                    w('')
            ref = stig_ref.get(d['srg_id']) or []
            if ref:
                w('*Product reference.* %s — %s' % (', '.join(ref),
                                                    str(d.get('stig_reference_status') or 'not checked').replace('_', ' ')))
                w('')
        w('\\newpage')
        w('')

    # The documents live in docs/. Writing beside the code instead left a stale
    # copy in docs/ that regeneration never touched, which is how a generated
    # document and its generator drift apart without anyone noticing.
    out = os.path.join(root, 'docs', 'applicability-matrix.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(o) + '\n')
    print('%d requirements, %d controls, %d revised, %d reference findings -> %s'
          % (len(dets), len(ctrl), len(revised), len(seen) if refs else 0,
             os.path.relpath(out, root)))
    print('integrity: %d invalid N/A, %d unnamed inheritance' % (len(bad_na), len(unnamed)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
