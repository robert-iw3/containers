# syntax=docker/dockerfile:1
# openCTI python client: Helps developers to use the OpenCTI API by providing easy to use methods and utils.
ARG repo="docker.io" \
    base_image="alpine:3.23" \
    image_hash="4d889c14e7d5a73929ab00be2ef8ff22437e7cbc545931e52554a7b00e123d8b"

FROM ${repo}/${base_image}@sha256:${image_hash}

ENV PATH=/pycti/bin:/usr/local/bin:/usr/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    TZ=UTC

RUN \
    apk add --no-cache \
        bash \
        curl \
        sudo \
        tzdata \
        coreutils \
        findutils \
        grep \
        ca-certificates \
        libgcc \
        libstdc++ \
        git \
        musl-dev \
        linux-headers \
        python3 \
        py3-pip; \
    \
    python3 -m venv pycti; \
    . pycti/bin/activate; \
    python3 -m pip install --upgrade --no-cache-dir pip; \
    python3 -m pip install --upgrade --no-cache-dir pycti; \
    \
    rm -rf /var/cache/apk/* /root/.cache/*

CMD [ "sh" ]