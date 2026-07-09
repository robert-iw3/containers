#!/bin/sh

# download splunk

set -e
export LANG=en_US.utf8

python /tmp/make-minimal-exclude.py ${SPLUNK_BUILD_URL} > /tmp/splunk-minimal-exclude.list
wget --progress=bar:force -O /tmp/`basename ${SPLUNK_BUILD_URL}` ${SPLUNK_BUILD_URL}
wget --progress=bar:force -O /tmp/splunk.tgz.sha512 ${SPLUNK_BUILD_URL}.sha512
cd /tmp
echo "$(cat /tmp/splunk.tgz.sha512)" | sha512sum --check  --status
rm /tmp/splunk.tgz.sha512
mkdir -p /minimal/splunk/var /extras/splunk/var
tar -C /minimal/splunk --strip 1 --exclude-from=/tmp/splunk-minimal-exclude.list -zxf /tmp/`basename ${SPLUNK_BUILD_URL}`
tar -C /extras/splunk --strip 1 --wildcards --files-from=/tmp/splunk-minimal-exclude.list -zxf /tmp/`basename ${SPLUNK_BUILD_URL}`
mv /minimal/splunk/etc /minimal/splunk-etc
mv /extras/splunk/etc /extras/splunk-etc
mkdir -p /minimal/splunk/etc /minimal/splunk/share/splunk/search_mrsparkle/modules.new