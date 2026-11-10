#!/usr/bin/env python3
"""Import setting-level vendor verification into the tracked inventory.

Verification is produced by reading the vendor's own configuration-file
reference for a setting and, where possible, exercising the setting on a live
instance. Both the citation and the test are evidence an assessor can follow,
so they are kept rather than consumed: the checklist cites them, and a rule
whose criterion rests on a cited page is recorded at a higher confidence than
one derived from the specification file alone.

Input is one or more workflow journals (JSONL). A journal is append-only, so a
re-import of the same journal is idempotent. Later journals update earlier
entries for the same (conf, stanza, key), which is how a correction lands.

Usage:
  bin/import-vendor-verification.py --journal PATH [--journal PATH ...] \
      --source-label TEXT [--out assess/inventory/vendor-verification.json]
"""
import argparse, json, os, sys, datetime

# A verified setting carries these. Anything else in an agent payload is
# working material and is not retained.
FIELDS = ('stanza', 'key', 'exists_in_version', 'vendor_doc_url', 'vendor_says',
          'live_test', 'live_evidence', 'verdict', 'correction', 'affects', 'notes')

# live_test values that mean the setting's behavior was exercised, not just read.
TESTED = ('accepted', 'rejected')

VERDICTS = ('criterion_sound', 'criterion_wrong_operand', 'criterion_wrong_semantics',
            'criterion_wrong_setting', 'finding_is_false')


def read_journal(path):
    """Yield (label, result) for each agent that returned a result."""
    label = {}
    out = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue                      # a partial trailing write
            if rec.get('type') == 'started':
                label[rec.get('agentId')] = rec.get('label', '')
            elif rec.get('type') == 'result':
                out.append((label.get(rec.get('agentId'), ''), rec.get('result')))
    return out


def entry_key(conf, item):
    return '%s\t%s\t%s' % (conf, item.get('stanza') or '', item.get('key') or '')


def confidence_for(item):
    """documented once a vendor page is cited; tested once it was exercised."""
    if item.get('live_test') in TESTED:
        return 'tested'
    if item.get('vendor_doc_url'):
        return 'documented'
    return 'derived'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--journal', action='append', required=True)
    ap.add_argument('--source-label', required=True,
                    help='what produced this verification, e.g. "round 2 vendor verification"')
    ap.add_argument('--date', default=datetime.date.today().isoformat())
    ap.add_argument('--out', default=os.path.join('assess', 'inventory',
                                                  'vendor-verification.json'))
    a = ap.parse_args()

    store = {'schema': 1, 'settings': {}, 'conflicts': {}, 'imports': []}
    if os.path.exists(a.out):
        with open(a.out, encoding='utf-8') as fh:
            store = json.load(fh)
        store.setdefault('settings', {})
        store.setdefault('conflicts', {})
        store.setdefault('imports', [])

    added = updated = skipped = 0
    confs = set()

    for jp in a.journal:
        if not os.path.exists(jp):
            sys.stderr.write('no such journal: %s\n' % jp)
            return 2
        for label, result in read_journal(jp):
            if not isinstance(result, dict):
                continue
            conf = result.get('conf') or label.split(':')[-1]
            confs.add(conf)

            conflicts = result.get('doc_vs_spec_conflicts') or []
            if conflicts:
                store['conflicts'][conf] = conflicts

            for item in result.get('settings') or []:
                if not item.get('key'):
                    skipped += 1
                    continue
                rec = {}
                for f in FIELDS:
                    # the agents name the field for the version they checked
                    src = 'exists_in_10_4_2' if f == 'exists_in_version' else f
                    if item.get(src) not in (None, ''):
                        rec[f] = item[src]
                rec['conf'] = conf
                rec['confidence'] = confidence_for(item)
                rec['source'] = a.source_label
                rec['imported'] = a.date
                if rec.get('verdict') and rec['verdict'] not in VERDICTS:
                    sys.stderr.write('unknown verdict %r for %s/%s\n'
                                     % (rec['verdict'], conf, item['key']))
                k = entry_key(conf, item)
                if k in store['settings']:
                    updated += 1
                else:
                    added += 1
                store['settings'][k] = rec

    store['imports'].append({'label': a.source_label, 'date': a.date,
                             'journals': a.journal, 'conf_files': sorted(confs)})

    tmp = a.out + '.tmp'
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(store, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write('\n')
    os.replace(tmp, a.out)

    n = len(store['settings'])
    nodoc = sum(1 for v in store['settings'].values() if not v.get('vendor_doc_url'))
    byconf = {}
    for v in store['settings'].values():
        byconf[v['conf']] = byconf.get(v['conf'], 0) + 1
    tested = sum(1 for v in store['settings'].values() if v['confidence'] == 'tested')
    documented = sum(1 for v in store['settings'].values() if v['confidence'] == 'documented')

    print('%s: %d settings across %d conf files (%d added, %d updated, %d skipped)'
          % (a.out, n, len(byconf), added, updated, skipped))
    print('  confidence: %d tested, %d documented, %d derived'
          % (tested, documented, n - tested - documented))
    print('  without a vendor citation: %d' % nodoc)
    print('  conf files with doc-vs-spec conflicts recorded: %d' % len(store['conflicts']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
