# syntax=docker/dockerfile:1
# truss: The simplest way to serve AI/ML models into production.
ARG repo="docker.io" \
    base_image="alpine:3.23" \
    image_hash="4d889c14e7d5a73929ab00be2ef8ff22437e7cbc545931e52554a7b00e123d8b"

FROM ${repo}/${base_image}@sha256:${image_hash}

ENV PATH="${PATH}:/truss/bin" \
    SNYK_API=" "

RUN \
    apk add --no-cache -t .truss-deps \
        ca-certificates \
        rust \
        cargo \
        gcc \
        g++ \
        musl-dev \
        linux-headers \
        python3-dev \
        git \
        npm \
        clamav \
        freshclam; \
    \
    # git clone https://github.com/basetenlabs/truss.git; cd truss; \
    # npm install -g snyk; \
    # npm install -g snyk-to-html; \
    # snyk config set api=${SNYK_API}; \
    # snyk code test --json | snyk-to-html -o /truss-code-review.html; \
    # snyk test --json | snyk-to-html -o /truss-deps.html; \
    # snyk monitor; \
    # npm uninstall -g snyk; \
    # npm uninstall -g snyk-to-html; \
    # cd ..; rm -rf ./truss; \
    \
    apk add --no-cache python3 py3-pip; \
    python3 -m venv truss; \
    . truss/bin/activate; \
    python3 -m pip install --upgrade pip; \
    python3 -m pip install --upgrade truss; \
    \
    addgroup -g 65535 truss; \
    adduser --shell /sbin/sh --disabled-password -h /home/truss --uid 65535 --ingroup truss truss; \
    \
    freshclam; \
    clamscan -rvi -l /home/truss/last_scan.log --exclude-dir="^/sys" /; \
    chown truss:truss /home/truss/last_scan.log; \
    grep -Hrn " FOUND" /home/truss/last_scan.log; \
    \
    apk del --purge .truss-deps; \
    rm -rf /var/cache/apk/* /root/.cache/*; \
    mkdir /truss/model

COPY model.py __init__.py /truss/model
COPY config.yaml .
RUN chown -R truss:truss /truss
USER truss
CMD [ "sh" ]
