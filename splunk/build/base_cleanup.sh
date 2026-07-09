#!/bin/sh

# base layer cleanup

set -e
export LANG=en_US.utf8

microdnf remove -y \
    make \
    gcc \
    openssl-devel \
    bzip2-devel \
    findutils \
    glibc-devel \
    cpp \
    binutils \
    keyutils-libs-devel \
    krb5-devel \
    libcom_err-devel \
    libffi-devel \
    libcurl-devel \
    libselinux-devel \
    libsepol-devel \
    libssh-devel \
    libverto-devel \
    libxcrypt-devel \
    ncurses-devel \
    pcre2-devel \
    zlib-devel \
    diffutils \
    bzip2

microdnf clean all

cd /bin

BBOX_LINKS=( clear find diff hostname killall netstat nslookup ping ping6 readline route syslogd tail traceroute vi )

for item in "${BBOX_LINKS[@]}"; do
ln -s busybox $item || true;
done

chmod u+s /bin/ping

groupadd sudo

echo " \
## Allows people in group sudo to run all commands \
%sudo  ALL=(ALL)   ALL" >> /etc/sudoers

microdnf clean all

rm -rf /anaconda-post.log /var/log/anaconda/*