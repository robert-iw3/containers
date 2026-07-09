# syntax=docker/dockerfile:1
# curator-opensearch: This project is a fork of https://github.com/elastic/curator.
# The main motivation behind its creation was the lack of compatibility between elastic/curator and OpenSearch.

ARG repo="docker.io" \
    base_image="alpine:3.23" \
    image_hash="4d889c14e7d5a73929ab00be2ef8ff22437e7cbc545931e52554a7b00e123d8b"

FROM ${repo}/${base_image}@sha256:${image_hash}

ENV PATH="${PATH}:/curator-opensearch/bin"
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
  # snyk souce code/deps scans
  # mkdir /src; cd /src; \
  # git clone https://github.com/flant/curator-opensearch.git; cd curator-opensearch; \
  # npm install -g snyk; \
  # npm install -g snyk-to-html; \
  # snyk config set api=${SNYK_API}; \
  # snyk code test --json | snyk-to-html -o /curator-opensearch-code-review.html; \
  # snyk test --json | snyk-to-html -o /curator-opensearch-deps.html; \
  # snyk monitor; \
  # npm uninstall -g snyk; \
  # npm uninstall -g snyk-to-html; \
  # cd ../..; rm -rf /src/curator-opensearch; \
  # curator-opensearch install via pip
  apk add --no-cache bash python3 py3-pip; \
  python3 -m venv curator-opensearch; \
  . curator-opensearch/bin/activate; \
  python3 -m pip install --upgrade pip; \
  python3 -m pip install --upgrade curator-opensearch; \
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
  chown -R curator:curator /curator-opensearch; \
  chmod -R a+rwx,o-rwx /curator-opensearch; \
  # bin check
  curator --version

USER curator
CMD [ "bash" ]
