# syntax=docker/dockerfile:1
ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash}

ENV PATH=/venv/bin:/usr/local/bin:/usr/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    TZ=UTC

RUN \
    addgroup -g 65535 guarddog; \
    adduser --shell /sbin/nologin --disabled-password -h /home/guarddog --uid 65535 --ingroup guarddog guarddog; \
    apk add --no-cache \
        bash \
        curl \
        wget \
        tzdata \
        ca-certificates \
        musl-dev \
        gcc \
        linux-headers \
        psutils \
        python3-dev \
        py3-pip; \
    python -m venv /venv; \
    . venv/bin/activate; \
    /venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel guarddog; \
    rm -rf /var/cache/apk/* /root/.cache/*; \
    apk cache clean

USER guarddog

CMD ["tail", "-f", "/dev/null"]