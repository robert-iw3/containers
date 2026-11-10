#!/usr/bin/env python3
"""Resolve every CCI in the parsed rule set to its NIST SP 800-53 control.

CCI is the join key for the whole artifact chain: a STIG or SRG rule cites CCIs,
each CCI maps to an 800-53 control, and the RMF artifacts are organized by
control. Nothing here authors a mapping - it reads DISA's published CCI list.

Writes inventory/cci-map.json: per CCI, DISA's type and definition, and the
control index at each 800-53 revision present in the list.

A CCI that does not resolve is a hard failure, not a blank row. An unresolved
CCI means a rule cannot be tied to a control, and an artifact that silently
omits it reads as "nothing required".
"""
import json
import os
import sys
import xml.etree.ElementTree as ET

NIST = 'NIST SP 800-53'


def _lt(el):
    return el.tag.split('}')[-1]


def load_cci(path):
    """Return {cci_id: {type, definition, controls: {revision: index}}}."""
    root = ET.parse(path).getroot()
    out = {}
    for item in root.iter():
        if _lt(item) != 'cci_item':
            continue
        rec = {'type': None, 'definition': '', 'controls': {}}
        for child in item.iter():
            tag = _lt(child)
            if tag == 'type':
                rec['type'] = (child.text or '').strip()
            elif tag == 'definition':
                rec['definition'] = (child.text or '').strip()
            elif tag == 'reference' and NIST in (child.get('title') or ''):
                # The same CCI carries an index per revision; keep them all so a
                # site assessing against Rev 4 is not forced onto Rev 5.
                rec['controls'][child.get('version')] = child.get('index')
        out[item.get('id')] = rec
    return out


def main(argv):
    root = argv[1] if len(argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), os.pardir)
    cci_xml = os.path.join(root, 'reference', 'CCI_List.xml')
    rules_json = os.path.join(root, 'assess', 'inventory', 'srg-rules.json')
    out_path = os.path.join(root, 'assess', 'inventory', 'cci-map.json')

    for p in (cci_xml, rules_json):
        if not os.path.isfile(p):
            sys.exit('missing input: %s' % p)

    cci = load_cci(cci_xml)
    rules = json.load(open(rules_json, encoding='utf-8'))
    ours = sorted({c for r in rules for c in r['cci']})

    unresolved = [c for c in ours if c not in cci]
    if unresolved:
        sys.exit('%d CCI(s) absent from the DISA list, so they cannot be tied to a '
                 'control: %s' % (len(unresolved), ', '.join(unresolved)))

    revs = sorted({v for c in ours for v in cci[c]['controls']})
    mapping = {c: cci[c] for c in ours}
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(mapping, fh, indent=2, sort_keys=True)

    # Report the shape, because these counts are what the artifacts are built on.
    families = {}
    for c in ours:
        ix = mapping[c]['controls'].get('5') or mapping[c]['controls'].get('4') or ''
        if ix:
            families.setdefault(ix.split()[0], []).append(c)
    types = {}
    for c in ours:
        t = mapping[c]['type'] or 'unspecified'
        types[t] = types.get(t, 0) + 1

    print('%d CCI(s) across %d rule(s), all resolved' % (len(ours), len(rules)))
    print('800-53 revisions in the list: %s' % ', '.join(revs))
    print('DISA type: %s' % ', '.join('%s=%d' % kv for kv in sorted(types.items())))
    print('%d distinct controls, %d families' % (
        len(families), len({k.split('-')[0] for k in families})))
    print('-> %s' % os.path.relpath(out_path, root))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
