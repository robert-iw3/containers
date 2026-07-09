FROM docker.io/library/alpine:3.24@sha256:79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f

ARG TOFU_VERSION=1.12.3
ARG TFLINT_VERSION=0.63.1
ARG PACKER_VERSION=1.15.4
ARG TARGETARCH

RUN apk add --no-cache bash curl unzip git

RUN set -euo pipefail; \
    cd /tmp && \
    curl -fsSLO "https://github.com/opentofu/opentofu/releases/download/v${TOFU_VERSION}/tofu_${TOFU_VERSION}_linux_${TARGETARCH}.zip"; \
    curl -fsSLO "https://github.com/opentofu/opentofu/releases/download/v${TOFU_VERSION}/tofu_${TOFU_VERSION}_SHA256SUMS"; \
    grep "tofu_${TOFU_VERSION}_linux_${TARGETARCH}.zip" tofu_${TOFU_VERSION}_SHA256SUMS | sha256sum -c -; \
    unzip -o "tofu_${TOFU_VERSION}_linux_${TARGETARCH}.zip" -d /usr/local/bin tofu; \
    chmod +x /usr/local/bin/tofu; \
    rm -f tofu_${TOFU_VERSION}_linux_${TARGETARCH}.zip tofu_${TOFU_VERSION}_SHA256SUMS

RUN set -euo pipefail; \
    cd /tmp && \
    curl -fsSLO "https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/tflint_linux_${TARGETARCH}.zip"; \
    curl -fsSLO "https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/checksums.txt"; \
    grep "tflint_linux_${TARGETARCH}.zip" checksums.txt | sha256sum -c -; \
    unzip -o "tflint_linux_${TARGETARCH}.zip" -d /usr/local/bin tflint; \
    chmod +x /usr/local/bin/tflint; \
    rm -f tflint_linux_${TARGETARCH}.zip checksums.txt

RUN set -euo pipefail; \
    cd /tmp && \
    curl -fsSLO "https://releases.hashicorp.com/packer/${PACKER_VERSION}/packer_${PACKER_VERSION}_linux_${TARGETARCH}.zip"; \
    curl -fsSLO "https://releases.hashicorp.com/packer/${PACKER_VERSION}/packer_${PACKER_VERSION}_SHA256SUMS"; \
    grep "packer_${PACKER_VERSION}_linux_${TARGETARCH}.zip" packer_${PACKER_VERSION}_SHA256SUMS | sha256sum -c -; \
    unzip -o "packer_${PACKER_VERSION}_linux_${TARGETARCH}.zip" -d /usr/local/bin packer; \
    chmod +x /usr/local/bin/packer; \
    rm -f packer_${PACKER_VERSION}_linux_${TARGETARCH}.zip packer_${PACKER_VERSION}_SHA256SUMS

WORKDIR /workspace
COPY . /workspace

ENTRYPOINT ["/bin/bash", "/workspace/tests/run-tofu-checks.sh"]
