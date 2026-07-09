#!/bin/sh

# scap scan and clamav malware scan

set -e
export LANG=en_US.utf8

SCAP_PROFILE=xccdf_org.ssgproject.content_profile_stig
SCAP_SNAME=STIG
BENCHMARK=ssg-rhel9-ds.xml

mkdir /home/splunk/artifacts; cd /home/splunk/artifacts

subscription-manager repos --enable codeready-builder-for-rhel-9-$(arch)-rpms
microdnf install https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm
microdnf install -y yum-utils
microdnf update -y

microdnf install -y \
    bash \
    clamav \
    clamav-update \
    java-17-openjdk \
    openscap \
    scap-security-guide \
    wget \
    bzip2

wget  https://www.redhat.com/security/data/oval/v2/RHEL9/rhel-9.oval.xml.bz2
bzip2 -d rhel-9.oval.xml.bz2
oscap oval eval --report splunk-rhel9-cve-report.html rhel-9.oval.xml || :
oscap xccdf eval --profile ${SCAP_PROFILE} --results splunk_rhel9-${SCAP_SNAME}-scap-report.xml \
--report splunk_rhel9-${SCAP_SNAME}-scap-report.html /usr/share/xml/scap/ssg/content/${BENCHMARK} || :

freshclam
clamscan -rvi -l AV_scan.log --exclude-dir="^/sys|^/dev" / || :
chown -R splunk:splunk /home/splunk
grep -Hrn FOUND AV_scan.log

microdnf remove -y \
    clamav \
    clamav-update \
    openscap \
    scap-security-guide \
    wget \
    bzip2

microdnf clean all
rm -rf /var/cache/dnf /var/cache/yum /tmp/* /var/tmp/*
truncate -s 0 /var/log/*log