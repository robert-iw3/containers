#!/bin/bash

# script to move certs to directory declared in either .hcl or .json configs

<<comment

  "tls": {
    "defaults": {
      "verify_incoming": true,
      "verify_outgoing": true,
      "ca_file": "/consul/certs/consul-agent-ca.pem",
      "cert_file": "/consul/certs/dc1-server-consul-0.pem",
      "key_file": "/consul/certs/dc1-server-consul-0-key.pem"
    },

comment

ca_name="consul-agent-ca.pem"
server_name="dc1-server-consul-0.pem"
key_name="dc1-server-consul-0-key.pem"
# cert and user
target_dir="/consul/certs/"
user="consul"

if [ -z "$ca_name" ] || [ -z "$target_dir" ]; then
  echo "Usage: $0 <ca_name> <target_directory>"
  exit 1
fi

if [ -z "$server_name" ] || [ -z "$target_dir" ]; then
  echo "Usage: $0 <server_name> <target_directory>"
  exit 1
fi

if [ -z "$key_name" ] || [ -z "$target_dir" ]; then
  echo "Usage: $0 <key_name> <target_directory>"
  exit 1
fi

if [ ! -d "$target_dir" ]; then
  mkdir -p "$target_dir"
  echo "Directory '$target_dir' created."
fi

if find . -name "$ca_name" -print -quit | xargs -I {} mv {} "$target_dir"; then
  echo "File '$ca_name' moved to '$target_dir'."
else
  echo "File '$ca_name' not found."
fi

if find . -name "$server_name" -print -quit | xargs -I {} mv {} "$target_dir"; then
  echo "File '$server_name' moved to '$target_dir'."
else
  echo "File '$server_name' not found."
fi

if find . -name "$key_name" -print -quit | xargs -I {} mv {} "$target_dir"; then
  echo "File '$key_name' moved to '$target_dir'."
else
  echo "File '$key_name' not found."
fi

chown -R $user:$user $target_dir