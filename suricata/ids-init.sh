#!/bin/bash

set -e

#if using debian/ubuntu/suse/arch/alpine replace with appropriate package manager
dnf install -y podman

#location to offload events/alerts logs ( e.g. /home/someuser/suricata/logs )
DIRECTORY=
#interface to monitor network traffic ( e.g. wlo1 )
INT=

#make output dir in case it's not there
mkdir -p ${DIRECTORY}

#build Dockerfile
podman build -t suricata .

#blow away build environment
podman image prune -f; podman rmi 9-minimal -f

#run the meerkat sentry
podman run --rm -it --name suricata --net=host --cap-add=net_admin --cap-add=net_raw \
           --cap-add=sys_nice -v ${DIRECTORY}:/var/log/suricata:Z \
           -d suricata -i ${INT}

#offload build artifacts (CVE's, STIG Compliance Results, clamav scan results)
podman cp suricata:/home/suricata/artifacts ${DIRECTORY}

#monitor alerts
tail -f ${DIRECTORY}/fast.log
