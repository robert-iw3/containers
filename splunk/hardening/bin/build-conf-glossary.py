#!/usr/bin/env python3
"""Build a plain-language glossary of Splunk configuration files.

A finding that says "web.conf [settings] enableSplunkWebSSL" means nothing to a
reader who does not administer Splunk, and an assessment is read by people who do
not. Each finding therefore carries one sentence saying what the file governs.

The sentence comes from the vendor's own specification header wherever it is
useful. Where the vendor's sentence is circular - several read "configure server
options in server" - a plainer one is written here, and the file records which is
which so a reader can tell an authored sentence from a quoted one.
"""
import os
import re
import sys

# Written only where the vendor's own sentence does not tell a general reader
# what the file is for.
PLAIN = {
    'server.conf': 'Core server settings, including the certificates and protocols used to protect management and replication traffic.',
    'audit.conf': 'The audit trail Splunk keeps of its own activity, and how those records are signed.',
    'limits.conf': 'Limits on how much work searches and data processing may consume.',
    'alert_actions.conf': 'What Splunk does when an alert fires, such as sending email or calling a webhook.',
    'savedsearches.conf': 'Saved searches, scheduled reports and alerts.',
    'props.conf': 'How incoming data is recognized, parsed and timestamped.',
    'transforms.conf': 'Rules that rewrite or route data as it is processed.',
    'restmap.conf': 'The management interface endpoints, and which clients may reach them.',
    'splunk-launch.conf': 'Environment settings read before Splunk starts, including whether it starts in FIPS mode.',
    'distsearch.conf': 'How a search head reaches the indexers it searches.',
    'indexes.conf': 'The indexes data is stored in, how large they may grow and how long data is kept.',
    'outputs.conf': 'Where this instance forwards its data, and how that connection is protected.',
    'authentication.conf': 'How users sign in, and the password rules applied to local accounts.',
    'web-features.conf': 'Which features of the web interface are available.',
    'app.conf': 'Settings for an installed app: whether it is enabled, visible, and what it may do.',
    'health.conf': 'Thresholds for Splunk reporting on its own health.',
    'user-seed.conf': 'The initial administrator account created on a first start.',
    'serverclass.conf': 'Which configuration a deployment server sends to which hosts.',
    'datamodels.conf': 'Data models and their acceleration.',
    'macros.conf': 'Reusable fragments of search language.',
    'commands.conf': 'Custom search commands an app provides.',
    'times.conf': 'Named time ranges offered in the interface.',
    'workload_pools.conf': 'How search workload is divided between pools of resources.',
}

VENDOR = re.compile(r'This file contains[^.]*\.')
DOCURL = re.compile(r'https?://docs\.splunk\.com/[A-Za-z0-9./_#?=-]+')
# Every specification points at this topic for how configuration files and their
# precedence work. It is the right citation for the layering a finding describes.
PRECEDENCE_TOPIC = ('http://docs.splunk.com/Documentation/Splunk/latest/Admin/'
                    'Aboutconfigurationfiles')


def doc_url(path):
    """A vendor documentation URL the specification itself publishes.

    Never constructed. A topic-specific link is preferred over the generic
    configuration-files topic, which nearly every specification carries.
    """
    generic, specific = '', ''
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            for m in DOCURL.finditer(line):
                u = m.group(0).rstrip('.,)')
                if 'Aboutconfigurationfiles' in u:
                    generic = generic or u
                elif len(u) > 40:
                    specific = specific or u
    return specific or generic or PRECEDENCE_TOPIC


def vendor_line(path):
    """The line number the description was taken from, for citation."""
    with open(path, encoding='utf-8', errors='replace') as fh:
        for i, line in enumerate(fh, 1):
            if 'This file contains' in line:
                return i
            if i > 20:
                break
    return 1


def vendor_sentence(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        head = ' '.join(l.lstrip('#').strip() for l in [next(fh, '') for _ in range(14)])
    head = re.sub(r'\s+', ' ', head)
    m = VENDOR.search(head)
    if not m:
        return ''
    s = m.group(0).strip()
    # The boilerplate ends "... in <filename>." which reads as circular.
    s = re.sub(r'\s+in [a-z_-]+\.$', '.', s)
    s = s.replace('This file contains possible attributes and values you can use to configure',
                  'Configures')
    s = s.replace('This file contains possible settings you can use to configure', 'Configures')
    s = s.replace('This file contains settings and values to configure', 'Configures')
    s = s.replace('This file contains descriptions of the settings that you can use to',
                  'Used to')
    return s[:1].upper() + s[1:] if s else ''


def main(argv):
    root = argv[1] if len(argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # The specification set must match the version under assessment. The repo
    # carried a 10.0.0 set against a 10.4.2 instance, which is 268 undocumented
    # settings and several changed defaults - cookieSameSite and sslVersions
    # among them. Prefer a version-matched directory, and let the caller name one.
    spec_dir = os.environ.get('SPLUNK_SPEC_DIR') or ''
    if not spec_dir:
        base = os.path.dirname(root)
        cands = sorted((d for d in os.listdir(base)
                        if d.startswith('splunk-spec-files-')), reverse=True)
        spec_dir = os.path.join(base, cands[0]) if cands else \
                   os.path.join(base, 'splunk-spec-files')
    out = os.path.join(root, 'assess', 'inventory', 'conf-glossary.tsv')
    if not os.path.isdir(spec_dir):
        sys.exit('no specification directory at %s' % spec_dir)

    rows, authored, quoted = [], 0, 0
    for name in sorted(os.listdir(spec_dir)):
        if not name.endswith('.conf.spec'):
            continue
        conf = name[:-5]
        path = os.path.join(spec_dir, name)
        url = doc_url(path)
        ln = vendor_line(path)
        if conf in PLAIN:
            # Authored for a general reader, and marked as such. The citation is
            # still the vendor's: the specification is the authority on the file,
            # whoever wrote the sentence describing it.
            rows.append((conf, PLAIN[conf], 'authored', '%s:%d' % (name, ln), url))
            authored += 1
        else:
            t = vendor_sentence(path)
            if t:
                rows.append((conf, t, 'vendor', '%s:%d' % (name, ln), url))
                quoted += 1

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write('conf\tdescription\tsource\tspec_ref\tdoc_url\n')
        for r in rows:
            fh.write('\t'.join(r) + '\n')
    topic = sum(1 for r in rows if 'Aboutconfigurationfiles' not in r[4])
    print('%d conf file(s): %d authored for clarity, %d quoted from the vendor specification'
          % (len(rows), authored, quoted))
    print('%d carry a topic-specific vendor documentation link; the rest cite the '
          'configuration-files topic' % topic)
    print('-> %s' % os.path.relpath(out, root))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
