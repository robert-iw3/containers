#!/bin/bash

##### Install and start Cribl Stream #####
mkdir -p /criblworkerhome/local/cribl/auth
cat << EOF > /criblworkerhome/local/cribl/auth/676f6174733432.dat
{"it":$(date +%s),"phf":0,"guid":"$(uuidgen)","email":"demo@cribl.io"}
EOF
cat << EOF > /criblworkerhome/local/cribl/auth/users.json
{"username":"admin","first":"admin","last":"admin","email":"admin","roles":["admin"],"password":"cribldemo"}
EOF

/cribl/bin/cribl start