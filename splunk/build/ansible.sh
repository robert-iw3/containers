#!/bin/sh

# ansible/user setup

set -e
export LANG=en_US.utf8

SPLUNK_ANSIBLE_HOME=/opt/ansible
ANSIBLE_USER=ansible
ANSIBLE_GROUP=ansible
CONTAINER_ARTIFACT_DIR=/opt/container_artifact

mkdir -p ${SPLUNK_ANSIBLE_HOME}
wget --progress=bar:force -O splunk-playbooks.zip \
    https://github.com/splunk/splunk-ansible/archive/refs/heads/develop.zip
unzip splunk-playbooks.zip -d ${SPLUNK_ANSIBLE_HOME}
mv ${SPLUNK_ANSIBLE_HOME}/splunk-ansible-develop/* ${SPLUNK_ANSIBLE_HOME}
sed -i -e 's/%sudo\s\+ALL=(ALL\(:ALL\)\?)\s\+ALL/%sudo ALL=NOPASSWD:ALL\nansible ALL=(splunk)NOPASSWD:ALL/g' /etc/sudoers
groupadd -r ${ANSIBLE_GROUP}
useradd -r -m -g ${ANSIBLE_GROUP} -s /bin/bash ${ANSIBLE_USER}
usermod -aG sudo ${ANSIBLE_USER}
usermod -aG ${ANSIBLE_GROUP} ${SPLUNK_USER}
mkdir ${CONTAINER_ARTIFACT_DIR}
chown -R ${ANSIBLE_USER}:${ANSIBLE_GROUP} ${CONTAINER_ARTIFACT_DIR}
chmod -R 775 ${CONTAINER_ARTIFACT_DIR}
chmod -R 555 ${SPLUNK_ANSIBLE_HOME}
chgrp ${ANSIBLE_GROUP} ${SPLUNK_ANSIBLE_HOME} ${SPLUNK_ANSIBLE_HOME}/ansible.cfg
chmod 775 ${SPLUNK_ANSIBLE_HOME}
chmod 664 ${SPLUNK_ANSIBLE_HOME}/ansible.cfg
sed -i '/^\[defaults\]/a\interpreter_python = /usr/bin/python3' ${SPLUNK_ANSIBLE_HOME}/ansible.cfg
chmod 755 /sbin/entrypoint.sh /sbin/createdefaults.py /sbin/checkstate.sh