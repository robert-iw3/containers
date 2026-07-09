#!/bin/sh

# splunk user creation

set -e
export LANG=en_US.utf8

UID=41812
GID=41812

SPLUNK_GROUP=splunk
SPLUNK_USER=splunk

groupadd -r -g ${GID} ${SPLUNK_GROUP}
useradd -r -m -u ${UID} -g ${GID} -s /bin/bash ${SPLUNK_USER}