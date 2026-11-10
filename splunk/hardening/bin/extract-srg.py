#!/usr/bin/env python3
"""Parse the DISA SRG XCCDF files into one inventory.

Reads every *-xccdf.xml under srg/ and emits inventory/srg-rules.json plus a
tab-separated index. The XCCDF is the only source of rule text; nothing here
authors a requirement. Severity, CCI and the SRG-APP identifier come straight
out of the file so a later mapping can be traced back to it.
"""
import json
import os
import sys
import re
import xml.etree.ElementTree as ET

# DISA packs several distinct fields into the single XCCDF <description> element
# as escaped pseudo-XML. Carried through whole it renders as one unreadable blob
# in a checklist and leaves False Positives, Mitigations, Potential Impact and
# Responsibility empty, because their content is sitting inside the blob.
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
        # Not every benchmark wraps its description. Keep the text as the
        # discussion rather than discarding it.
        out['discussion'] = raw.strip()
    return out

NS = {'x': 'http://checklists.nist.gov/xccdf/1.1'}


def _text(el, path, default=''):
    v = el.findtext(path, default=default, namespaces=NS)
    return (v or default).strip()


def parse_file(path):
    """Return (baseline_title, [rule dicts]) for one XCCDF file."""
    root = ET.parse(path).getroot()
    baseline = _text(root, 'x:title') or os.path.basename(path)
    out = []
    for group in root.findall('.//x:Group', NS):
        rule = group.find('x:Rule', NS)
        if rule is None:
            continue
        idents = [(i.get('system', '').rsplit('/', 1)[-1], (i.text or '').strip())
                  for i in rule.findall('x:ident', NS)]
        desc = split_description(_text(rule, 'x:description'))
        out.append({
            'baseline': baseline,
            'source_file': os.path.basename(path),
            'group_id': group.get('id'),
            'rule_id': rule.get('id'),
            'srg_id': _text(rule, 'x:version'),
            'severity': rule.get('severity', 'unknown'),
            'title': _text(rule, 'x:title'),
            'discussion': desc['discussion'],
            'description_raw': _text(rule, 'x:description'),
            'false_positives': desc['false_positives'],
            'false_negatives': desc['false_negatives'],
            'documentable': desc['documentable'],
            'mitigations': desc['mitigations'],
            'security_override_guidance': desc['security_override_guidance'],
            'potential_impacts': desc['potential_impacts'],
            'third_party_tools': desc['third_party_tools'],
            'mitigation_control': desc['mitigation_control'],
            'responsibility': desc['responsibility'],
            'ia_controls': desc['ia_controls'],
            'check': _text(rule, './/x:check-content'),
            'fix': _text(rule, 'x:fixtext'),
            'cci': [v for s, v in idents if s == 'cci'],
            'legacy_ids': [v for s, v in idents if s == 'legacy'],
        })
    return baseline, out


def main(argv):
    root = argv[1] if len(argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), os.pardir)
    srg_dir = os.path.join(root, 'benchmarks')
    out_dir = os.path.join(root, 'assess', 'inventory')
    if not os.path.isdir(srg_dir):
        sys.exit('no srg/ directory under %s' % root)
    os.makedirs(out_dir, exist_ok=True)

    rules = []
    for name in sorted(os.listdir(srg_dir)):
        if name.endswith('.xml'):
            baseline, got = parse_file(os.path.join(srg_dir, name))
            print('%-58s %3d rules  %s' % (name, len(got), baseline))
            rules.extend(got)

    if not rules:
        sys.exit('no rules parsed - check the XCCDF namespace')

    with open(os.path.join(out_dir, 'srg-rules.json'), 'w', encoding='utf-8') as fh:
        json.dump(rules, fh, indent=2, sort_keys=True)

    # A flat index for reading and for grep. Rule text stays in the JSON.
    idx = os.path.join(out_dir, 'srg-index.tsv')
    with open(idx, 'w', encoding='utf-8') as fh:
        fh.write('group_id\tsrg_id\tseverity\tcci\ttitle\n')
        for r in rules:
            fh.write('%s\t%s\t%s\t%s\t%s\n' % (
                r['group_id'], r['srg_id'], r['severity'],
                ','.join(r['cci']) or '-',
                ' '.join(r['title'].split())))

    cci = sorted({c for r in rules for c in r['cci']})
    print('\n%d rules, %d distinct CCIs -> inventory/srg-rules.json, srg-index.tsv'
          % (len(rules), len(cci)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
