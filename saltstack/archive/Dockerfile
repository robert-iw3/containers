# syntax=docker/dockerfile:1
# saltstack: Built on Python, Salt is an event-driven automation tool and framework to deploy, configure, and manage complex IT systems.

ARG repo="docker.io" \
    base_image="alpine:3.23" \
    image_hash="4d889c14e7d5a73929ab00be2ef8ff22437e7cbc545931e52554a7b00e123d8b"

FROM ${repo}/${base_image}@sha256:${image_hash}

ARG BUILD_DATE
ARG VCS_REF
ARG SALT_VIRTUAL_ENV="salt"

ENV SALT_USER="salt" \
    SALT_HOME="/home/salt"

ENV PATH="${PATH}:/${SALT_VIRTUAL_ENV}/bin"
#ENV SNYK_API=

ENV SALT_DOCKER_DIR="/etc/docker-salt" \
    SALT_ROOT_DIR="/etc/salt" \
    SALT_CACHE_DIR='/var/cache/salt'

ENV SALT_RUNTIME_DIR="${SALT_DOCKER_DIR}/runtime" \
    SALT_DATA_DIR="${SALT_HOME}/data"

ENV SALT_CONFS_DIR="${SALT_DATA_DIR}/config" \
    SALT_KEYS_DIR="${SALT_DATA_DIR}/keys" \
    SALT_BASE_DIR="${SALT_DATA_DIR}/srv" \
    SALT_LOGS_DIR="${SALT_DATA_DIR}/logs" \
    SALT_FORMULAS_DIR="${SALT_DATA_DIR}/3pfs"

RUN \
    set -e; \
    addgroup -g 65535 "${SALT_USER}"; \
    adduser --shell /sbin/nologin --disabled-password -h "${SALT_HOME}" --uid 65535 --ingroup "${SALT_USER}" "${SALT_USER}"; \
    apk add --no-cache \
        bash \
        ca-certificates \
        curl \
        git \
        gpg \
        gpg-agent \
        inotify-tools \
        openssh \
        openssl \
        logrotate \
        musl-locales \
        procps-ng \
        psmisc \
        python3 \
        py3-pip \
        py3-dateutil \
        py3-distro \
        py3-jinja2 \
        py3-jmespath \
        py3-looseversion \
        py3-markupsafe \
        py3-msgpack \
        py3-packaging \
        py3-psutil \
        py3-pycryptodomex \
        py3-pygit2 \
        py3-pyzmq \
        py3-requests \
        py3-yaml \
        supervisor \
        wget \
        tzdata; \
    apk add --no-cache -t .commonlib-deps \
       rust \
       cargo \
       gcc \
       g++ \
       musl-dev \
       linux-headers \
       python3-dev; \
    apk add --no-cache -t .scan \
       npm \
       clamav \
       freshclam; \
# source code scan
    # mkdir src; cd src; \
    # git clone https://github.com/saltstack/salt.git; cd salt; \
    # npm install -g snyk; \
    # npm install -g snyk-to-html; \
    # snyk config set api=${SNYK_API}; \
    # snyk code test --json | snyk-to-html -o ${SALT_HOME}/salt-code-review.html; \
    # snyk test --json | snyk-to-html -o ${SALT_HOME}/salt-deps.html; \
    # snyk monitor; \
    # npm uninstall -g snyk; \
    # npm uninstall -g snyk-to-html; \
    # cd ../..; rm -rf /src/salt; \
    # chown -R "${SALT_USER}":"${SALT_USER}" "${SALT_HOME}"; \
    python3 -m venv "${SALT_VIRTUAL_ENV}"; \
    . "${SALT_VIRTUAL_ENV}"/bin/activate; \
    python3 -m pip --no-cache-dir install --upgrade pip; \
    python3 -m pip --no-cache-dir install --upgrade salt; \
    apk del --no-network --purge .commonlib-deps; \
    mkdir -p "${SALT_ROOT_DIR}"/{master.d,cloud.profiles.d,minion.d,proxy.d}; \
    chmod -R 755 "${SALT_ROOT_DIR}"; \
    mkdir -p "${SALT_CACHE_DIR}"/salt/master/jobs; \
    mkdir -p /var/run/salt/master; \
    chmod -R 755 "${SALT_CACHE_DIR}" /var/run/salt; \
    chown -R "${SALT_USER}":"${SALT_USER}" "${SALT_ROOT_DIR}" "${SALT_CACHE_DIR}" /var/run/salt/

# modify config files to your environment, examples are in $(pwd)
COPY --chown="${SALT_USER}":"${SALT_USER}" master "${SALT_ROOT_DIR}"
COPY --chown="${SALT_USER}":"${SALT_USER}" cloud.profiles "${SALT_ROOT_DIR}"/cloud.profiles.d/
COPY --chown="${SALT_USER}":"${SALT_USER}" cloud.providers "${SALT_ROOT_DIR}"/cloud.providers.d/
COPY --chown="${SALT_USER}":"${SALT_USER}" proxy "${SALT_ROOT_DIR}"/proxy.d/
COPY --chmod=755 entrypoint.sh /sbin/entrypoint.sh
COPY --chmod=755 config/ "${SALT_RUNTIME_DIR}"
COPY --chmod=755 config/reloader /usr/local/sbin/

RUN \
    bash -c "${SALT_RUNTIME_DIR}/setup.sh"; \
    freshclam; \
    clamscan -rvi -l "${SALT_HOME}"/clamav_scan.log --exclude-dir="^/sys|^/dev" /; \
    chown "${SALT_USER}":"${SALT_USER}" "${SALT_HOME}"/clamav_scan.log; \
    grep -Hrn " FOUND" "${SALT_HOME}"/clamav_scan.log; \
    apk del --no-network --purge .scan; \
    rm -rf /var/cache/apk/* /root/.cache/*; \
    chown -R "${SALT_USER}":"${SALT_USER}" /"${SALT_VIRTUAL_ENV}"; \
    mkdir -p "${SALT_BASE_DIR}" "${SALT_FORMULAS_DIR}" "${SALT_KEYS_DIR}" "${SALT_CONFS_DIR}" "${SALT_LOGS_DIR}"

VOLUME [ "${SALT_KEYS_DIR}", "${SALT_LOGS_DIR}" ]
EXPOSE 4505 4506 8000

# smoke test
#RUN \
#    salt '*' test.version; \

HEALTHCHECK --interval=10m --timeout=10s \
    CMD salt-call --local status.ping_master 127.0.0.1 || exit 1

WORKDIR "${SALT_HOME}"
USER "${SALT_USER}"
ENTRYPOINT [ "/sbin/entrypoint.sh" ]
CMD [ "app:start" ]
