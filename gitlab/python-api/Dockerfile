# syntax=docker/dockerfile:1
# py-gitlab: A python wrapper for the GitLab API.
# https://python-gitlab.readthedocs.io/en/stable/

ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash}

LABEL org.opencontainers.image.source="https://github.com/python-gitlab/python-gitlab"

ENV PATH="${PATH}:/python-gitlab/bin"

RUN \
    apk add --no-cache -t .build-deps \
        rust \
        cargo \
        gcc \
        g++ \
        musl-dev \
        linux-headers \
        python3-dev \
        npm \
        git; \
    \
    addgroup -g 65535 py-gitlab; \
    adduser --shell /sbin/nologin --disabled-password -h /home/py-gitlab --uid 65535 --ingroup py-gitlab py-gitlab; \
    \
    python3 -m venv python-gitlab; \
    . python-gitlab/bin/activate; \
    python3 -m pip install --upgrade pip; \
    python3 -m pip install --upgrade PyYaml; \
    python3 -m pip install --upgrade python-gitlab; \
    \
    apk del --no-network --purge .build-deps; \
    rm -rf /var/cache/apk/* /root/.cache/*; \
    \
    apk add --no-cache \
        bash \
        ca-certificates \
        tzdata \
        python3 \
        py3-pip; \
    chown -R py-gitlab:py-gitlab /python-gitlab; \
    gitlab --version

USER py-gitlab
CMD ["bash"]