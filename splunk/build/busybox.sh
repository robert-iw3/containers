#!/bin/sh

# install latest busybox

set -e
export LANG=en_US.utf8

BUSYBOX_URL=https://busybox.net/downloads/busybox-1.36.1.tar.bz2

cd ~
wget --progress=bar:force -O busybox.tar.bz2 ${BUSYBOX_URL}
bzip2 -d busybox.tar.bz2
tar xf busybox.tar
cd busybox-1.36.1
make defconfig
make
cp busybox /bin/busybox
cd ~
rm -rf busybox.tar busybox-1.36.1/