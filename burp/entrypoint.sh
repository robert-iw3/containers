#!/usr/bin/env sh
set -e

# Ensure non-root user has access to volumes
chown -R burp:burp /home/burp/.java /home/burp/config

# Validate BURP_KEY
if [ -z "${BURP_KEY}" ]; then
    echo "Error: BURP_KEY environment variable is not set."
    exit 1
fi

# Execute Burp Suite with license key
exec gosu burp java ${JAVA_OPTS} -jar /home/burp/burpsuite_pro.jar \
    --config-file=/home/burp/config/project_options.json \
    --user-config-file=/home/burp/config/user_options.json \
    <<EOF
y
${BURP_KEY}
o
EOF