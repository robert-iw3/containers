# syntax=docker/dockerfile:1
# owncloud: open-source file sync, share and content collaboration server (classic 10.x line).
# For the Go-based next generation server see ocis/ in this directory.
#
# The upstream image manages its own PHP/apache configuration from templates at
# start time; tuning (upload size, memory) is exposed through OWNCLOUD_* env
# vars in docker-compose.yml rather than baked-in ini files.
ARG repo="docker.io" \
    owncloud_version="10.15.0"

FROM ${repo}/owncloud/server:${owncloud_version}

LABEL org.opencontainers.image.name='ownCloud' \
    org.opencontainers.image.description='Open-source file sync, share and content collaboration platform.' \
    org.opencontainers.image.usage='https://doc.owncloud.com/server/next/admin_manual/' \
    org.opencontainers.image.source='https://github.com/owncloud/core'

# The base image ships /usr/bin/healthcheck (probes the internal web server).
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=120s \
    CMD ["/usr/bin/healthcheck"]

EXPOSE 8080
