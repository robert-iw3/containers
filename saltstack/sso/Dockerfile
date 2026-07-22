# Salt 3008 master / api / minion image, built from the Salt Project package
# repository. A single image serves every role; the entrypoint selects one
# from SALT_ROLE.
FROM docker.io/debian:12-slim

ARG SALT_VERSION=3008

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg python3 tini \
 && install -d -m 0755 /etc/apt/keyrings \
 && curl -fsSL https://packages.broadcom.com/artifactory/api/security/keypair/SaltProjectKey/public \
        -o /etc/apt/keyrings/salt-archive-keyring.pgp \
 && curl -fsSL https://github.com/saltstack/salt-install-guide/releases/latest/download/salt.sources \
        -o /etc/apt/sources.list.d/salt.sources \
 && printf 'Package: salt-*\nPin: version %s.*\nPin-Priority: 1001\n' "$SALT_VERSION" \
        > /etc/apt/preferences.d/salt-pin-1001 \
 && apt-get update \
 && apt-get install -y --no-install-recommends salt-master salt-api salt-minion \
 && apt-get purge -y gnupg \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
