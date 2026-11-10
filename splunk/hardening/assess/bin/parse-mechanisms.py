#!/usr/bin/env python3
"""Flatten the determinations' mechanism prose into checkable triples.

Build-time step. The assessor that runs on a Splunk host reads the flat output and
never parses prose, which is what keeps it free of external dependencies.

A mechanism reads like
    web.conf [settings] maxSockets, maxThreads; server.conf [httpServer] maxSockets
and becomes one row per conf / stanza / key:
    SRG-APP-000001-WSR-000001  web.conf  settings  maxSockets

A segment that names a conf file but no key is still emitted with an empty key, so
the assessor reads the whole stanza: losing it would silently drop coverage.
"""
import json
import os
import re
import sys

SPEC_DIR = os.environ.get(
    'SPLUNK_SPEC_DIR',
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))), 'splunk-spec-files'))

CONF = re.compile(r'\b([A-Za-z_][A-Za-z0-9_-]*\.conf)\b')
STANZA = re.compile(r'\[([^\]]{1,120})\]')
# A key is a bare token; it may carry dots (tools.sessions.on) or be an environment
# variable name (SPLUNK_FIPS). Anything with a space, slash or quote is prose.
KEY = re.compile(r'^[A-Za-z_][A-Za-z0-9_.\-]*$')
NOISE = {'and', 'or', 'the', 'in', 'on', 'under', 'with', 'for', 'to', 'at', 'of',
         'via', 'per', 'plus', 'see', 'also', 'conf', 'stanza', 'stanzas', 'key',
         'keys', 'setting', 'settings', 'default', 'defaults', 'none', 'n', 'a'}


def segments(mech):
    """Split a mechanism into parts, each naming at most one conf file."""
    for part in re.split(r'[;]+', mech):
        part = part.strip()
        if part:
            yield part


def parse(mech):
    """Yield (conf, stanza, key) triples. stanza and key may be ''. """
    out = []
    for seg in segments(mech):
        confs = CONF.findall(seg)
        if not confs:
            continue
        conf = confs[0].lower()
        stanzas = STANZA.findall(seg)
        stanza = stanzas[0].strip() if stanzas else ''
        # Keys are what follows the conf name and the stanza.
        tail = seg[seg.lower().find(conf) + len(conf):]
        if stanzas:
            cut = tail.find(']')
            if cut >= 0:
                tail = tail[cut + 1:]
        keys = []
        for tok in re.split(r'[,\s]+', tail):
            tok = tok.strip().strip('.,:;()`\'"')
            if not tok or tok.lower() in NOISE:
                continue
            if KEY.match(tok) and not tok.lower().endswith('.conf'):
                keys.append(tok)
        if keys:
            for k in keys:
                out.append((conf, stanza, k))
        else:
            out.append((conf, stanza, ''))
    return out


def declared_keys():
    """Every setting name each shipped .conf.spec declares."""
    out = {}
    if not os.path.isdir(SPEC_DIR):
        return out
    for f in os.listdir(SPEC_DIR):
        if not f.endswith('.conf.spec'):
            continue
        ks = set()
        with open(os.path.join(SPEC_DIR, f), encoding='utf-8', errors='replace') as fh:
            for line in fh:
                m = re.match(r'^([A-Za-z_][A-Za-z0-9_.\-]*)\s*=', line)
                if m:
                    ks.add(m.group(1).lower())
        out[f[:-5]] = ks
    return out


def looks_like_a_setting(tok):
    """A setting name carries case, a dot or an underscore; prose does not.

    The mechanism text is prose, so a bare lowercase word in it is almost always
    English rather than a key: per-endpoint, recorded, account. Requiring one of
    those three marks keeps maxSockets, tools.sessions.on, SPLUNK_FIPS and
    logging_format while dropping the prose.
    """
    return any(c.isupper() for c in tok) or '.' in tok or '_' in tok


def main(argv):
    root = argv[1] if len(argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dets = json.load(open(os.path.join(root, 'inventory', 'sca-determinations.json'), encoding='utf-8'))
    rules = {r['srg_id']: r for r in
             json.load(open(os.path.join(root, 'inventory', 'srg-rules.json'), encoding='utf-8'))}

    out_path = os.path.join(root, 'inventory', 'checks.tsv')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    spec = declared_keys()
    rows, no_triple, dropped, undeclared = [], [], [], []
    for d in dets:
        if d['determination'] != 'APPLICABLE':
            continue
        trip = parse(d.get('mechanism') or '')
        if not trip:
            no_triple.append(d['srg_id'])
            continue
        sev = rules.get(d['srg_id'], {}).get('severity', 'unknown')
        kept = 0
        for conf, stanza, key in trip:
            if not key:
                rows.append((d['srg_id'], sev, conf, stanza, '', 'stanza'))
                kept += 1
                continue
            known = spec.get(conf)
            if known is not None and key.lower() in known:
                rows.append((d['srg_id'], sev, conf, stanza, key, 'declared'))
                kept += 1
            elif looks_like_a_setting(key):
                # Not in the shipped specification but shaped like a setting. Some
                # keys are genuinely present in 10.4.2 and absent from the spec set -
                # audit.conf is the measured case - so these are assessed and marked
                # rather than discarded.
                rows.append((d['srg_id'], sev, conf, stanza, key, 'undeclared'))
                undeclared.append((conf, key))
                kept += 1
            else:
                dropped.append((conf, key))
        if not kept:
            # Every token parsed as a key was prose. That happens on a requirement
            # whose mechanism IS the whole configuration surface rather than a named
            # setting - the meta-requirement to configure per the security settings is
            # the case. Emit one whole-file row per conf the mechanism names, so the
            # requirement is assessed by reading the configuration in aggregate
            # instead of being silently dropped.
            named = []
            for c in CONF.findall(d.get('mechanism') or ''):
                c = c.lower()
                if c not in named:
                    named.append(c)
            if named:
                for c in named:
                    rows.append((d['srg_id'], sev, c, '', '', 'aggregate'))
            else:
                no_triple.append(d['srg_id'])

    seen, uniq = set(), []
    for r in rows:
        if r in seen:
            continue
        seen.add(r)
        uniq.append(r)

    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write('srg_id\tseverity\tconf\tstanza\tkey\tkey_status\n')
        for r in sorted(uniq):
            fh.write('\t'.join(r) + '\n')

    reqs = len({r[0] for r in uniq})
    confs = len({r[2] for r in uniq})
    dec = sum(1 for r in uniq if r[5] == 'declared')
    und = sum(1 for r in uniq if r[5] == 'undeclared')
    stz = sum(1 for r in uniq if r[5] == 'stanza')
    print('%d applicable requirement(s) -> %d check row(s)' % (
        sum(1 for d in dets if d['determination'] == 'APPLICABLE'), len(uniq)))
    print('  requirements covered     : %d' % reqs)
    print('  distinct conf files      : %d' % confs)
    print('  key declared in the spec : %d' % dec)
    print('  key undeclared, assessed : %d' % und)
    agg = sum(1 for r in uniq if r[5] == 'aggregate')
    print('  whole-stanza rows        : %d' % stz)
    print('  whole-file rows (aggregate) : %d' % agg)
    print('  prose fragments dropped  : %d' % len(set(dropped)))
    if no_triple:
        print('  NO TRIPLE EXTRACTED  : %d  %s' % (len(no_triple), no_triple[:8]))
    print('-> %s' % os.path.relpath(out_path, root))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
