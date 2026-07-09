#!/bin/sh

# install python 3.9

set -e
export LANG=en_US.utf8

PYTHON_VERSION=3.9.19
PYTHON_GPG_KEY_ID=E3FF2839C048B25C084DEBE9B26995E310250568
PY_SHORT=${PYTHON_VERSION%.*}

wget --progress=bar:force -O /tmp/python.tgz \
    https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz

wget --progress=bar:force -O /tmp/Python-gpg-sig-${PYTHON_VERSION}.tgz.asc \
    https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz.asc

gpg --keyserver keys.openpgp.org --recv-keys $PYTHON_GPG_KEY_ID \
|| gpg --keyserver pool.sks-keyservers.net --recv-keys $PYTHON_GPG_KEY_ID \
|| gpg --keyserver pgp.mit.edu --recv-keys $PYTHON_GPG_KEY_ID \
|| gpg --keyserver keyserver.pgp.com --recv-keys $PYTHON_GPG_KEY_ID

gpg --verify /tmp/Python-gpg-sig-${PYTHON_VERSION}.tgz.asc /tmp/python.tgz

rm /tmp/Python-gpg-sig-${PYTHON_VERSION}.tgz.asc

mkdir -p /tmp/pyinstall

tar -xzC /tmp/pyinstall/ --strip-components=1 -f /tmp/python.tgz

rm /tmp/python.tgz

cd /tmp/pyinstall

./configure \
    --enable-optimizations \
    --prefix=/usr \
    --with-ensurepip=install

make altinstall LDFLAGS="-Wl,--strip-all"

rm -rf /tmp/pyinstall
ln -sf /usr/bin/python${PY_SHORT} /usr/bin/python
ln -sf /usr/bin/pip${PY_SHORT} /usr/bin/pip
ln -sf /usr/bin/python${PY_SHORT} /usr/bin/python3
ln -sf /usr/bin/pip${PY_SHORT} /usr/bin/pip3

cd /

/usr/bin/python3.9 -m pip install --upgrade pip

pip -q --no-cache-dir install --upgrade \
    requests_unixsocket \
    requests \
    six \
    wheel \
    Mako \
    "urllib3<2.0.0" \
    certifi \
    jmespath \
    future \
    avro \
    cryptography \
    lxml \
    protobuf \
    setuptools \
    ansible

find /usr/lib/ -depth \( -type d -a -not -wholename '*/ansible/plugins/test' -a \( -name test -o -name tests -o -name idle_test \) \) -exec rm -rf '{}' \;
find /usr/lib/ -depth \( -type f -a -name '*.pyc' -o -name '*.pyo' -o -name '*.a' \) -exec rm -rf '{}' \;
find /usr/lib/ -depth \( -type f -a -name 'wininst-*.exe' \) -exec rm -rf '{}' \;

ldconfig