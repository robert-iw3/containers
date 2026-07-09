# syntax=docker/dockerfile:1.4

ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash}

ENV PATH="${PATH}:/elasticsearch-curator/bin"
#ENV SNYK_API=" "

RUN \
    apk add --no-cache -t .curator-deps \
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
  apk add --no-cache bash python3 py3-pip; \
  python3 -m venv elasticsearch-curator; \
  . elasticsearch-curator/bin/activate; \
  python3 -m pip install --upgrade pip; \
  python3 -m pip install --upgrade elasticsearch-curator; \
  # curator user
  addgroup -g 65535 curator; \
  adduser --shell /sbin/nologin --disabled-password -h /home/curator --uid 65535 --ingroup curator curator; \
  # malware scan
  freshclam; \
  clamscan -rvi -l /home/curator/last_scan.log --exclude-dir="^/sys" /; \
  chown curator:curator /home/curator/last_scan.log; \
  grep -Hrn " FOUND" /home/curator/last_scan.log; \
  # cleanup
  apk del --no-network --purge .curator-deps; \
  rm -rf /var/cache/apk/* /root/.cache/* /tmp/* /var/tmp/*; \
  # perms
  chown -R curator:curator /elasticsearch-curator; \
  chmod -R a+rwx,o-rwx /elasticsearch-curator; \
  # bin check
  curator --version

USER curator
CMD [ "bash" ]
