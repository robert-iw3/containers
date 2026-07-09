#!/bin/sh
set -e

# Variables
email="${PORTSWIGGER_EMAIL_ADDRESS}"
password="${PORTSWIGGER_PASSWORD}"
name="burpsuite_pro"
version="${BURP_SUITE_PRO_VERSION}"
file_name="/home/burp/${name}.jar"
cookie_jar="/tmp/cookies"
checksum="${BURP_SUITE_PRO_CHECKSUM}"

# Validate environment variables
if [ -z "${email}" ] || [ -z "${password}" ] || [ -z "${version}" ] || [ -z "${checksum}" ]; then
    echo "Error: Required environment variables are not set."
    exit 1
fi

# Ensure output directory exists
mkdir -p "$(dirname "${file_name}")"
chown burp:burp "$(dirname "${file_name}")"

# Fetch CSRF token
token=$(curl -s --cookie-jar "${cookie_jar}" "https://portswigger.net/users" | grep -oE "[A-Z0-9_-]{128}")
if [ -z "${token}" ]; then
    echo "Error: Failed to retrieve CSRF token."
    rm -f "${cookie_jar}"
    exit 1
fi

# Authenticate
curl -s -o /dev/null \
    -b "${cookie_jar}" \
    -c "${cookie_jar}" \
    -X POST \
    -F "EmailAddress=${email}" \
    -F "Password=${password}" \
    -F "__RequestVerificationToken=${token}" \
    "https://portswigger.net/users" || {
    echo "Error: Authentication failed."
    rm -f "${cookie_jar}"
    exit 1
}

# Download Burp Suite
curl -s -b "${cookie_jar}" \
    -o "${file_name}" \
    "https://portswigger.net/burp/releases/download?product=pro&version=${version}&type=Jar" || {
    echo "Error: Failed to download Burp Suite."
    rm -f "${cookie_jar}"
    exit 1
}

# Verify checksum
echo "${checksum} *${file_name}" | sha256sum -c || {
    echo "Error: Checksum verification failed."
    rm -f "${file_name}" "${cookie_jar}"
    exit 1
}

# Set permissions
chown burp:burp "${file_name}"
chmod 644 "${file_name}"

# Clean up
rm -f "${cookie_jar}"