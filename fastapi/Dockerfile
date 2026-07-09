# syntax=docker/dockerfile:1
# fastapi: a modern, fast (high-performance), web framework for building APIs with Python 3.8+ based on standard Python type hints.

ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash}

ENV PATH="${PATH}:/fastapi/bin"
#ENV SNYK_API=" "

RUN \
    apk add --no-cache -t .fastapi-deps \
      ca-certificates \
      rust \
      cargo \
      gcc \
      g++ \
      musl-dev \
      linux-headers \
      python3-dev \
      npm \
      git \
      clamav \
      freshclam; \
  apk add --no-cache python3 py3-pip; \
  python3 -m venv fastapi; \
  . fastapi/bin/activate; \
  python3 -m pip install --upgrade pip; \
  python3 -m pip install --upgrade fastapi; \
  python3 -m pip install --upgrade "uvicorn[standard]"; \
  addgroup -g 65535 fastapi; \
  adduser --shell /sbin/sh --disabled-password -h /home/fastapi --uid 65535 --ingroup fastapi fastapi; \
  freshclam; \
  clamscan -rvi -l /home/fastapi/last_scan.log --exclude-dir="^/sys" /; \
  chown fastapi:fastapi /home/fastapi/last_scan.log; \
  grep -Hrn " FOUND" /home/fastapi/last_scan.log; \
  apk del --no-network --purge .fastapi-deps; \
  rm -rf /var/cache/apk/* /root/.cache/*

ADD /api-example/ /fastapi/
RUN chown -R fastapi:fastapi /fastapi

WORKDIR /fastapi/api-example
RUN python3 -m pip install -r requirements.txt
USER fastapi
EXPOSE 8000
ENTRYPOINT [ "uvicorn" ]
CMD [ "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload" ]