#!/usr/bin/env python3
"""Emit DISA checklists from an assessment.

Produces both formats from one result set:
  .ckl   legacy XML, opened by STIG Viewer 2.x
  .cklb  JSON, opened by STIG Viewer 3.x

THE TWO FORMATS DO NOT SHARE A STATUS VOCABULARY. The XML takes NotAFinding,
Open, Not_Applicable and Not_Reviewed; the JSON takes not_a_finding, open,
not_applicable and not_reviewed. Reusing one map for both silently produces a
file the viewer rejects, so the mapping is declared once per format here.

FINDING DETAILS CARRY THE EXACT CONFIGURATION. Each finding states the literal
configuration line observed, the file that supplied it, and the layer that file
belongs to, because a value without its source cannot be checked and cannot be
told apart from a value an app failed to override.

NOTHING IS OMITTED AND NOTHING IS ASSUMED SATISFIED. Every requirement in the
governing benchmark appears. A requirement with no criterion to judge it against
is Not_Reviewed, which is the honest status: a checklist that reports a
requirement as satisfied because nobody assessed it is the failure a checklist
exists to prevent. The cklb `size` field is the origin benchmark's total rule
count, so a reader can compare it to the rules present and detect a subset.
"""
import textwrap
import argparse
import collections
import hashlib
import json
import os
import re
import sys
import uuid
import xml.etree.ElementTree as ET

# Producer identity. Not "DISA STIG Viewer": this file was not produced by it, and
# a checklist that misstates its own provenance is not evidence.
PRODUCER = 'Splunk configuration assessment :: hardening/bin/emit-checklist.py'

# The 26 VULN_ATTRIBUTE names, in the order a checklist carries them.
VULN_FIELDS = [
    'Vuln_Num', 'Severity', 'Group_Title', 'Rule_ID', 'Rule_Ver', 'Rule_Title',
    'Vuln_Discuss', 'IA_Controls', 'Check_Content', 'Fix_Text', 'False_Positives',
    'False_Negatives', 'Documentable', 'Mitigations', 'Potential_Impact',
    'Third_Party_Tools', 'Mitigation_Control', 'Responsibility',
    'Security_Override_Guidance', 'Check_Content_Ref', 'Weight', 'Class', 'STIGRef',
    'TargetKey', 'STIG_UUID',
]
CKL_STATUS = {'not_reviewed': 'Not_Reviewed', 'open': 'Open',
              'not_applicable': 'Not_Applicable', 'not_a_finding': 'NotAFinding'}
# Benchmark metadata is READ FROM THE XCCDF, never hardcoded. An earlier version
# carried a table of titles and release strings, and its Benchmark Date for the
# Central Log Server SRG was wrong by three months - which is what a transcribed
# copy of a vendor's metadata does over time. This also makes the emitter general:
# any benchmark in the library can be emitted without editing code.
BENCH_CACHE = {}


def benchmark_meta(xccdf_dir, filename):
    """id, title, version, release and total rule count, from the document."""
    if filename in BENCH_CACHE:
        return BENCH_CACHE[filename]
    path = os.path.join(xccdf_dir, filename)
    meta = {'stigid': os.path.splitext(filename)[0], 'title': filename,
            'display': filename, 'release': '', 'version': '', 'total': 0}
    if os.path.isfile(path):
        root = ET.parse(path).getroot()
        nsurl = root.tag.split('}')[0].strip('{') if '}' in root.tag else ''
        def txt(tag):
            e = root.find('{%s}%s' % (nsurl, tag)) if nsurl else root.find(tag)
            return ' '.join((e.text or '').split()) if e is not None else ''
        title = txt('title')
        meta['title'] = title or filename
        # A compact name for the display field: the long form is for the title.
        meta['display'] = (title.replace('Security Requirements Guide', 'SRG')
                                .replace('Security Technical Implementation Guide', 'STIG'))
        meta['version'] = txt('version')
        meta['stigid'] = (root.get('id') or meta['stigid']).replace('xccdf_mil.disa.stig_benchmark_', '')
        blob = ET.tostring(root, encoding='unicode')[:60000]
        m = re.search(r'Release:\s*(\d+)\s*Benchmark Date:\s*(\d{1,2} \w+ \d{4})', blob)
        if m:
            meta['release'] = 'Release: %s Benchmark Date: %s' % (m.group(1), m.group(2))
        meta['total'] = sum(1 for r in root.iter() if r.tag.split('}')[-1] == 'Rule')
    BENCH_CACHE[filename] = meta
    return meta


def stable_uuid(*parts):
    """A UUID derived from identity, so re-emitting the same assessment is comparable."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'splunk-harden:' + ':'.join(str(p) for p in parts)))


def load_results(path):
    """observations keyed by srg_id."""
    obs = collections.defaultdict(list)
    with open(path, encoding='utf-8') as fh:
        head = fh.readline().rstrip('\n').split('\t')
        idx = {k: i for i, k in enumerate(head)}
        for line in fh:
            f = line.rstrip('\n').split('\t')
            if len(f) < len(head):
                f += [''] * (len(head) - len(f))
            obs[f[idx['srg_id']]].append({k: f[i] for k, i in idx.items()})
    return obs


# Plain-language context, so a finding is readable by someone who does not
# administer Splunk. Built by bin/build-conf-glossary.py from the vendor's own
# specification files, with the citation carried so a reader can check it.
def load_glossary(root):
    out = {}
    p = os.path.join(root, 'inventory', 'conf-glossary.tsv')
    if not os.path.isfile(p):
        return out
    with open(p, encoding='utf-8') as fh:
        head = fh.readline().rstrip('\n').split('\t')
        for line in fh:
            f = line.rstrip('\n').split('\t')
            if len(f) >= len(head):
                out[f[0]] = dict(zip(head, f))
    return out


# What each configuration layer means, in words rather than a label. The layer is
# what decides whether a setting an app supplies is actually in effect.
LAYER_PLAIN = {
    'system_local': ("the instance's own local settings, which override every app - "
                     "so an app cannot change this value"),
    'app': 'an installed app',
    'system_default': 'the value Splunk ships; nobody has changed it',
    'user': 'a per-user setting',
}


def load_verdicts(path):
    """srg_id -> status and the reason, from bin/evaluate.sh."""
    out = {}
    if not path or not os.path.isfile(path):
        return out
    with open(path, encoding='utf-8') as fh:
        head = fh.readline().rstrip('\n').split('\t')
        for line in fh:
            f = line.rstrip('\n').split('\t')
            if len(f) >= len(head):
                d = dict(zip(head, f))
                out[d['srg_id']] = d
    return out


# Vendor verification. Each setting behind a criterion was looked up in the
# vendor's own configuration-file reference and, where it could be exercised,
# tested on a running instance. The citation is evidence an assessor can follow,
# so the checklist carries it rather than asserting the criterion unsupported.
def load_vendor(root, rules_dir):
    """Returns (citations by srg_id, the verification store).

    Citations come from the rule files, which name the page each criterion now
    rests on. The prose lives in the store so the vendor's words are held once.
    """
    cites = {}
    if rules_dir and os.path.isdir(rules_dir):
        for fn in sorted(os.listdir(rules_dir)):
            if not fn.endswith('.rule'):
                continue
            rid, rows = fn[:-5], []
            with open(os.path.join(rules_dir, fn), encoding='utf-8') as fh:
                for line in fh:
                    if line.startswith('vendor:'):
                        parts = line.split(':', 1)[1].split()
                        if len(parts) >= 4:
                            rows.append((parts[0], parts[1].strip('[]'), parts[2],
                                         parts[-1]))
                    elif line.startswith('retired_check:'):
                        rows.append(('retired', '', line.split(':', 1)[1].strip(), ''))
            if rows:
                cites[rid] = rows
    store = {}
    sp = os.path.join(root, 'inventory', 'vendor-verification.json')
    if os.path.isfile(sp):
        with open(sp, encoding='utf-8') as fh:
            store = json.load(fh).get('settings', {})
    return cites, store


def vendor_block(srg_id, cites, store):
    """The sources this requirement's criteria rest on, for the checklist."""
    rows = cites.get(srg_id) or []
    if not rows:
        return []
    out = ['VENDOR SOURCES FOR THIS CRITERION']
    out.append('  Each setting below was looked up in the vendor documentation named, and')
    out.append('  where the setting could be exercised the behavior was tested on this')
    out.append('  instance. Follow the link to confirm the criterion independently.')
    retired = [r for r in rows if r[0] == 'retired']
    for conf, stanza, key, url in [r for r in rows if r[0] != 'retired']:
        rec = store.get('%s\t%s\t%s' % (conf, stanza, key)) or {}
        out.append('')
        out.append('  %s [%s] %s' % (conf, stanza, key))
        out.append('    source   %s' % url)
        if rec.get('vendor_says'):
            said = textwrap.wrap(' '.join(rec['vendor_says'].split()), 74)
            for i, ln in enumerate(said[:8]):
                out.append(('    says     ' if i == 0 else '             ') + ln)
            if len(said) > 8:
                out.append('             (continues; see the source)')
        lt = rec.get('live_test')
        if lt in ('accepted', 'rejected'):
            out.append('    tested   the instance %s this value when it was applied' % lt)
        elif lt == 'read_only_check':
            out.append('    tested   read from this instance; not altered')
        elif lt == 'untested':
            out.append('    tested   not exercised on this instance')
        if rec.get('exists_in_version') == 'absent':
            out.append('    NOTE     this setting does not exist in the running version')
    if retired:
        out.append('')
        out.append('  CRITERIA WITHDRAWN AFTER VERIFICATION')
        out.append('    The vendor documentation contradicted these tests, so they were')
        out.append('    withdrawn rather than counted. They are listed so the record shows')
        out.append('    what was considered.')
        for _, _, text, _ in retired:
            for ln in textwrap.wrap(text, 72):
                out.append('      ' + ln)
    return out


def read_manifest(path):
    meta = {}
    if not path or not os.path.isfile(path):
        return meta
    for line in open(path, encoding='utf-8'):
        m = re.match(r'^([a-z_]+)\s{2,}(.+)$', line.rstrip('\n'))
        if m:
            meta[m.group(1)] = m.group(2).strip()
    return meta


def instance_facts(obs):
    """The facts the assessment read from the product itself."""
    out = []
    for rows in obs.values():
        for r in rows:
            if r.get('conf') == 'fact' and r.get('found') == 'present':
                out.append((r.get('key'), r.get('value')))
    seen, uniq = set(), []
    for k, v in out:
        if k not in seen:
            seen.add(k); uniq.append((k, v))
    return sorted(uniq)


def finding_details(rows, meta, gloss=None, facts=None):
    """The exact configuration observed, with the file that supplied each value.

    Where a requirement has no configuration behind it, the pane still reports what
    the assessment read from the product. "The Central Log Server must be a version
    supported by the vendor" has no setting to read, but the running version is a
    fact this assessment established, and it is the first thing whoever adjudicates
    the requirement needs. Reporting nothing there sends them to find it by hand.
    """
    if not rows:
        out = ['No setting in the product governs this requirement.']
        if facts:
            out.append('')
            out.append('WHAT THIS ASSESSMENT READ FROM THE PRODUCT on %s at %s'
                       % (meta.get('host', 'unknown'), meta.get('collected_utc', 'unknown')))
            out.append('')
            # Version first: it is the fact most requirements without a setting
            # turn on, and it should not have to be hunted for in an ordered list.
            lead = [k for k in ('version', 'version_full', 'build', 'splunk_home',
                                'splunkd_state') if dict(facts).get(k)]
            for k in lead:
                out.append('  %-18s %s' % (k, dict(facts)[k]))
            rest = [(k, v) for k, v in facts if k not in lead]
            if rest:
                out.append('')
                for k, v in rest:
                    out.append('  %-18s %s' % (k, v))
            out.append('')
            out.append('Read with splunk btool and splunk version, which read and write nothing.')
        return '\n'.join(out)
    out = []
    host = meta.get('host', 'unknown')
    when = meta.get('collected_utc', 'unknown')
    out.append('OBSERVED CONFIGURATION on %s at %s' % (host, when))
    out.append('Read with splunk btool, which reads configuration and writes none.')
    out.append('')
    # Name the configuration files in plain terms before quoting settings out of
    # them. A reader who does not administer Splunk cannot otherwise tell what
    # "web.conf [settings] enableSplunkWebSSL" refers to.
    if gloss:
        confs = []
        for r in rows:
            if r.get('conf') and r['conf'] not in confs:
                confs.append(r['conf'])
        named = [c for c in confs if c in gloss]
        if named:
            out.append('WHAT THESE CONFIGURATION FILES GOVERN')
            for c in named:
                g = gloss[c]
                out.append('  %s' % c)
                out.append('      %s' % g['description'])
                src = ('vendor specification' if g.get('source') == 'vendor'
                       else 'summarized from the vendor specification')
                out.append('      reference: %s (%s)' % (g.get('spec_ref', ''), src))
                if g.get('doc_url'):
                    out.append('      vendor documentation: %s' % g['doc_url'])
            out.append('')
    present = [r for r in rows if r.get('found') == 'present']
    absent = [r for r in rows if r.get('found') == 'absent']
    other = [r for r in rows if r.get('found') not in ('present', 'absent')]

    if present:
        out.append('SETTINGS IN EFFECT (%d)' % len(present))
        for r in present:
            stanza = ('[%s] ' % r['stanza']) if r['stanza'] else ''
            out.append('  %s %s%s = %s' % (r['conf'], stanza, r['key'], r['value']))
            out.append('      supplied by : %s' % (r['source'] or 'unknown'))
            lay = r['precedence'] or 'unknown'
            out.append('      layer       : %s' % lay)
            if lay in LAYER_PLAIN:
                out.append('                    (%s)' % LAYER_PLAIN[lay])
            if r.get('observed_line'):
                out.append('      btool output: %s' % r['observed_line'].strip())
        out.append('')
    if absent:
        out.append('SETTINGS NOT PRESENT IN THE MERGED CONFIGURATION (%d)' % len(absent))
        for r in absent:
            stanza = ('[%s] ' % r['stanza']) if r['stanza'] else ''
            out.append('  %s %s%s  - not set, so Splunk uses the value it ships with'
                       % (r['conf'], stanza, r['key']))
        out.append('')
    if other:
        out.append('NOT OBSERVABLE (%d)' % len(other))
        for r in other:
            out.append('  %s %s  - %s' % (r['conf'], r['key'] or '(whole stanza)', r['found']))
        out.append('')
    return '\n'.join(out).rstrip()


def comments(det, meta, verdict=None, facts=None, vendor=None):
    """Applicability determination and the chain of custody for this assessment."""
    out = []
    if det:
        out.append('APPLICABILITY: %s (evidence grade %s)'
                   % (det.get('determination', 'unknown'), det.get('evidence_grade', '-')))
        if det.get('basis'):
            out.append('')
            out.append('BASIS: %s' % det['basis'])
        if det.get('mechanism'):
            out.append('')
            out.append('MECHANISM: %s' % det['mechanism'])
        if det.get('assessment_method'):
            out.append('')
            out.append('ASSESSMENT METHOD: %s' % det['assessment_method'])
        if det.get('organizational_artifact'):
            out.append('')
            out.append('ARTIFACT REQUIRED: %s' % det['organizational_artifact'])
    if vendor:
        out.append('')
        out.extend(vendor)
    out.append('')
    if verdict:
        st = verdict.get('status', 'not_reviewed')
        why = verdict.get('reason', '')
        if st == 'not_a_finding':
            out.append('STATUS: Not a Finding. Every condition of the pass criterion was '
                       'met by the configuration observed above.')
        elif st == 'open':
            out.append('STATUS: Open. The following condition of the pass criterion was not '
                       'met:')
            out.append('')
            for part in why.split('; '):
                out.append('  %s' % part)
        else:
            out.append('STATUS: Not Reviewed. %s' % (why or 'no basis for a determination'))
            out.append('')
            out.append('WHAT THIS ASSESSMENT ESTABLISHED, so the remaining determination is '
                       'the only part left to a person:')
            out.append('')
            for k, v in (facts or []):
                out.append('  %-18s %s' % (k, v))
            out.append('')
            out.append('These were read from the product itself. A determination that '
                       'depends on information outside the instance - a vendor support '
                       'lifecycle, an entitlement, an organizational procedure - changes '
                       'over time and is deliberately not asserted here: a tool that '
                       'hardcoded it would state something stale with confidence years '
                       'later. The fact is reported; the currency is the assessor\'s.')
        out.append('')
        # NO CRITERION HAS BEEN VERIFIED AGAINST VENDOR DOCUMENTATION OR TESTED
        # ON A RUNNING INSTANCE. Some were reviewed by a second reader working
        # from the same documents, which catches internal inconsistency and
        # nothing else - it cannot catch a specification that disagrees with the
        # product, which is where the real defects have been found. Saying a
        # status is "verified" on that basis would overstate it.
        conf_level = (verdict or {}).get('confidence', 'derived')
        if conf_level == 'tested':
            out.append('BASIS OF THIS STATUS: every setting this criterion tests was '
                       'confirmed against the vendor\'s published documentation, and its '
                       'behavior was exercised on a running instance. The sources are '
                       'listed above so the determination can be checked independently.')
        elif conf_level == 'documented':
            out.append('BASIS OF THIS STATUS: every setting this criterion tests was '
                       'confirmed against the vendor\'s published documentation, cited '
                       'above. The settings were read from this instance but their '
                       'behavior was not exercised on it.')
        else:
            out.append('BASIS OF THIS STATUS: the criterion was derived from the benchmark '
                       'check text and the vendor configuration specification shipped with '
                       'this version. At least one setting it tests has NOT been confirmed '
                       'against the vendor\'s published documentation. Treat it as a first '
                       'reading. Where sources are listed above, they cover only part of '
                       'the criterion.')
        out.append('')
        out.append('This status is the application layer only. Anything the application '
                   'cannot reach is listed above as an external dependency and is not '
                   'counted against it.')
    else:
        out.append('STATUS IS Not_Reviewed BECAUSE no pass criterion was applied.')
    if meta:
        out.append('')
        out.append('CHAIN OF CUSTODY')
        for k, label in (('collected_utc', 'collected'), ('collected_by', 'by'),
                         ('host', 'host'), ('splunk_version', 'version'),
                         ('results_sha256', 'results sha256')):
            if meta.get(k):
                out.append('  %-16s %s' % (label, meta[k]))
        if meta.get('manifest_sha256'):
            out.append('  %-16s %s' % ('manifest sha256', meta['manifest_sha256']))
        out.append('  Evidence is attributable, reproducible and tamper-evident. It is not')
        out.append('  non-repudiable unless the manifest was signed with a key held outside')
        out.append('  the collecting process.')
    return '\n'.join(out).strip()


def build_ckl(rules_by_bench, obs, dets, meta, asset, bench, gloss, verdicts, facts,
              cites=None, vstore=None):
    root = ET.Element('CHECKLIST')
    a = ET.SubElement(root, 'ASSET')
    for tag, val in (('ROLE', asset['role']), ('ASSET_TYPE', 'Computing'),
                     ('HOST_NAME', asset['host']), ('HOST_IP', asset['ip']),
                     ('HOST_MAC', ''), ('HOST_FQDN', asset['fqdn']),
                     ('TARGET_COMMENT', asset['comment']), ('TECH_AREA', ''),
                     ('TARGET_KEY', ''), ('WEB_OR_DATABASE', 'true'),
                     ('WEB_DB_SITE', asset['fqdn']), ('WEB_DB_INSTANCE', '')):
        ET.SubElement(a, tag).text = val or None
    stigs = ET.SubElement(root, 'STIGS')

    for src, rules in rules_by_bench.items():
        b = bench[src]
        suuid = stable_uuid('bench', b['stigid'], b['release'])
        istig = ET.SubElement(stigs, 'iSTIG')
        info = ET.SubElement(istig, 'STIG_INFO')
        for name, data in (('version', b['version']), ('classification', 'UNCLASSIFIED'),
                           ('customname', ''), ('stigid', b['stigid']),
                           ('description', b['title']), ('filename', src),
                           ('releaseinfo', b['release']), ('title', b['title']),
                           ('uuid', suuid), ('notice', 'terms-of-use'), ('source', '')):
            sd = ET.SubElement(info, 'SI_DATA')
            ET.SubElement(sd, 'SID_NAME').text = name
            if data:
                ET.SubElement(sd, 'SID_DATA').text = data

        for r in rules:
            v = ET.SubElement(istig, 'VULN')
            det = dets.get(r['srg_id'], {})
            vals = {
                'Vuln_Num': r['group_id'], 'Severity': r['severity'],
                'Group_Title': r['group_title'], 'Rule_ID': r['rule_id'],
                'Rule_Ver': r['srg_id'], 'Rule_Title': r['title'],
                'Vuln_Discuss': r['discussion'], 'IA_Controls': r['ia_controls'],
                'Check_Content': r['check'], 'Fix_Text': r['fix'],
                'False_Positives': r['false_positives'],
                'False_Negatives': r['false_negatives'],
                'Documentable': r['documentable'],
                'Mitigations': r['mitigations'],
                'Potential_Impact': r['potential_impacts'],
                'Third_Party_Tools': r['third_party_tools'],
                'Mitigation_Control': r['mitigation_control'],
                'Responsibility': r['responsibility'],
                'Security_Override_Guidance': r['security_override_guidance'],
                'Check_Content_Ref': 'M',
                'Weight': '10.0', 'Class': 'Unclass',
                'STIGRef': '%s :: Version %s, %s' % (b['title'], b['version'], b['release']),
                'TargetKey': '', 'STIG_UUID': suuid,
            }
            for name in VULN_FIELDS:
                sd = ET.SubElement(v, 'STIG_DATA')
                ET.SubElement(sd, 'VULN_ATTRIBUTE').text = name
                if vals.get(name):
                    ET.SubElement(sd, 'ATTRIBUTE_DATA').text = vals[name]
            for c in r['cci']:
                sd = ET.SubElement(v, 'STIG_DATA')
                ET.SubElement(sd, 'VULN_ATTRIBUTE').text = 'CCI_REF'
                ET.SubElement(sd, 'ATTRIBUTE_DATA').text = c
            vd = verdicts.get(r['srg_id'], {})
            ET.SubElement(v, 'STATUS').text = CKL_STATUS.get(vd.get('status', 'not_reviewed'),
                                                             CKL_STATUS['not_reviewed'])
            ET.SubElement(v, 'FINDING_DETAILS').text = finding_details(obs.get(r['srg_id'], []), meta, gloss, facts)
            ET.SubElement(v, 'COMMENTS').text = comments(
                det, meta, verdicts.get(r['srg_id']), facts,
                vendor_block(r['srg_id'], cites or {}, vstore or {}))
            ET.SubElement(v, 'SEVERITY_OVERRIDE').text = None
            ET.SubElement(v, 'SEVERITY_JUSTIFICATION').text = None
    return root


def build_cklb(rules_by_bench, obs, dets, meta, asset, totals, bench, gloss, verdicts,
               facts, cites=None, vstore=None):
    doc = {
        'title': 'Splunk Enterprise application configuration',
        'cklb_version': '1.0',
        'id': stable_uuid('checklist', asset['host'], meta.get('collected_utc', '')),
        'active': False,
        'mode': 2,
        'has_path': True,
        'target_data': {
            'target_type': 'Computing', 'host_name': asset['host'],
            'ip_address': asset['ip'], 'mac_address': '', 'fqdn': asset['fqdn'],
            'comments': asset['comment'], 'role': asset['role'],
            'is_web_database': False, 'technology_area': '',
            'web_db_site': '', 'web_db_instance': '',
        },
        'stigs': [],
    }
    for src, rules in rules_by_bench.items():
        b = bench[src]
        suuid = stable_uuid('bench', b['stigid'], b['release'])
        entry = {
            'stig_name': b['title'], 'display_name': b['display'],
            'stig_id': b['stigid'], 'release_info': b['release'], 'uuid': suuid,
            'reference_identifier': None,
            # The origin benchmark's TOTAL rule count, so a reader comparing it to
            # len(rules) can see whether the checklist covers the benchmark.
            'size': totals[src],
            'rules': [],
        }
        for r in rules:
            det = dets.get(r['srg_id'], {})
            entry['rules'].append({
                'uuid': stable_uuid('rule', r['rule_id'], asset['host']),
                'stig_uuid': suuid,
                'group_id': r['group_id'], 'group_id_src': r['group_id'],
                'rule_id': r['rule_id'], 'rule_id_src': r['rule_id'],
                'target_key': None, 'stig_ref': None,
                'weight': '10.0', 'classification': 'Unclass',
                'severity': r['severity'] if r['severity'] in
                            ('low', 'medium', 'high') else 'unknown',
                'rule_version': r['srg_id'], 'rule_title': r['title'],
                'fix_text': r['fix'], 'reference_identifier': None,
                'group_title': r['group_title'],
                'false_positives': r['false_positives'],
                'false_negatives': r['false_negatives'],
                'discussion': r['discussion'], 'check_content': r['check'],
                'documentable': r['documentable'],
                'mitigations': r['mitigations'],
                'potential_impacts': r['potential_impacts'],
                'third_party_tools': r['third_party_tools'],
                'mitigation_control': r['mitigation_control'],
                'responsibility': r['responsibility'],
                'security_override_guidance': r['security_override_guidance'],
                'ia_controls': r['ia_controls'],
                'check_content_ref': {'name': 'M', 'href': ''},
                'legacy_ids': r['legacy_ids'], 'ccis': r['cci'],
                'group_tree': [{'id': r['group_id'], 'title': r['group_title'],
                                'description': ''}],
                'createdAt': '', 'updatedAt': '',
                'status': (verdicts.get(r['srg_id'], {}).get('status') or 'not_reviewed'),
                'overrides': {},
                'comments': comments(det, meta, verdicts.get(r['srg_id']), facts,
                                     vendor_block(r['srg_id'], cites or {}, vstore or {})),
                'finding_details': finding_details(obs.get(r['srg_id'], []), meta, gloss, facts),
            })
        doc['stigs'].append(entry)
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results', required=True, help='assessment-*.tsv from bin/assess.sh')
    ap.add_argument('--manifest', help='MANIFEST.txt from the evidence bundle')
    ap.add_argument('--verdicts', help='verdicts-*.tsv from bin/evaluate.sh; without it '
                                       'every requirement is reported Not_Reviewed')
    ap.add_argument('--out', help='output directory (default: beside the results)')
    ap.add_argument('--benchmarks', help='directory holding the XCCDF documents '
                                        '(default: ../srg beside this tool)')
    ap.add_argument('--rules', help='rule directory holding the vendor citations '
                                    '(default: assess/rules)')
    ap.add_argument('--host', help='override the host name recorded in the asset')
    ap.add_argument('--fqdn', default='')
    ap.add_argument('--ip', default='')
    ap.add_argument('--role', default='None')
    ap.add_argument('--comment', default='Splunk Enterprise, application configuration only. '
                                         'Operating system requirements are outside this boundary.')
    args = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    inv = lambda n: json.load(open(os.path.join(root, 'inventory', n), encoding='utf-8'))
    rules = inv('srg-rules.json')
    dets = {d['srg_id']: d for d in inv('sca-determinations.json')}
    obs = load_results(args.results)
    gloss = load_glossary(root)
    verdicts = load_verdicts(args.verdicts)
    cites, vstore = load_vendor(root, args.rules or os.path.join(root, 'rules'))
    facts = instance_facts(obs)
    meta = read_manifest(args.manifest)
    if args.manifest:
        sha = args.manifest + '.sha256'
        if os.path.isfile(sha):
            meta['manifest_sha256'] = open(sha, encoding='utf-8').read().split()[0]

    out_dir = args.out or os.path.dirname(os.path.abspath(args.results))
    os.makedirs(out_dir, exist_ok=True)
    host = args.host or meta.get('host') or 'unknown'
    asset = {'host': host, 'fqdn': args.fqdn or host, 'ip': args.ip,
             'role': args.role, 'comment': args.comment}

    # Group the governing SRG requirements by benchmark. The product STIG is a
    # reference, not a checklist of its own, so it is not emitted as one.
    xccdf_dir = args.benchmarks or os.path.join(os.path.dirname(root), 'benchmarks')
    # Which benchmarks to emit: the governing documents. A product STIG used as a
    # reference is not itself a checklist, so it is identified by its own title
    # rather than by a hardcoded file name.
    by_bench, totals = collections.OrderedDict(), collections.Counter()
    for r in rules:
        src = r['source_file']
        m = benchmark_meta(xccdf_dir, src)
        if 'Requirements Guide' not in m['title']:
            continue
        totals[src] += 1
        by_bench.setdefault(src, []).append({
            'srg_id': r['srg_id'], 'group_id': r['group_id'], 'rule_id': r['rule_id'],
            'severity': r['severity'], 'title': r['title'],
            'group_title': r['srg_id'].rsplit('-', 1)[0] if '-' in r['srg_id'] else r['srg_id'],
            'discussion': r['discussion'], 'check': r['check'], 'fix': r['fix'],
            'cci': r['cci'], 'legacy_ids': r['legacy_ids'],
            # Split out of the description blob by bin/extract-srg.py. Carried
            # through whole, it renders as unreadable markup in a viewer and
            # leaves these fields empty.
            'false_positives': r.get('false_positives', ''),
            'false_negatives': r.get('false_negatives', ''),
            'documentable': r.get('documentable', '') or 'false',
            'mitigations': r.get('mitigations', ''),
            'security_override_guidance': r.get('security_override_guidance', ''),
            'potential_impacts': r.get('potential_impacts', ''),
            'third_party_tools': r.get('third_party_tools', ''),
            'mitigation_control': r.get('mitigation_control', ''),
            'responsibility': r.get('responsibility', ''),
            'ia_controls': r.get('ia_controls', ''),
        })
    for src in by_bench:
        by_bench[src].sort(key=lambda x: x['group_id'])
    bench = {src: benchmark_meta(xccdf_dir, src) for src in by_bench}
    # size is the benchmark's own rule count, read from the document, so a reader
    # comparing it to the rules present sees real coverage.
    for src in by_bench:
        totals[src] = bench[src]['total'] or totals[src]

    stem = 'splunk-%s' % re.sub(r'[^A-Za-z0-9._-]', '_', host)

    # ---- .ckl
    tree = ET.ElementTree(build_ckl(by_bench, obs, dets, meta, asset, bench, gloss, verdicts,
                                    facts, cites, vstore))
    try:
        ET.indent(tree, space='\t')
    except AttributeError:
        pass
    ckl = os.path.join(out_dir, stem + '.ckl')
    with open(ckl, 'wb') as fh:
        fh.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        fh.write(('<!--%s-->\n' % PRODUCER).encode('utf-8'))
        tree.write(fh, encoding='utf-8', xml_declaration=False)
        fh.write(b'\n')

    # ---- .cklb
    cklb = os.path.join(out_dir, stem + '.cklb')
    doc = build_cklb(by_bench, obs, dets, meta, asset, totals, bench, gloss, verdicts,
                     facts, cites, vstore)
    with open(cklb, 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, indent=2)
        fh.write('\n')

    nrules = sum(len(v) for v in by_bench.values())
    print('%d requirement(s) across %d benchmark(s)' % (nrules, len(by_bench)))
    for src in by_bench:
        print('  %-34s %d of %d  [%s]' % (bench[src]['display'][:34],
              len(by_bench[src]), totals[src], bench[src]['release']))
    print('-> %s  (%d bytes)' % (os.path.relpath(ckl, root), os.path.getsize(ckl)))
    print('-> %s  (%d bytes)' % (os.path.relpath(cklb, root), os.path.getsize(cklb)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
