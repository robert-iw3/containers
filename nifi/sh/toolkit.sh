#!/bin/sh -e

cat <<EOT > ${nifi_toolkit_props_file}
baseUrl=
keystore=
keystoreType=
keystorePasswd=
keyPasswd=
truststore=
truststoreType=
truststorePasswd=
proxiedEntity=
EOT

cat <<EOT > ${HOME}/.nifi-cli.config
nifi.props=${nifi_toolkit_props_file}
EOT