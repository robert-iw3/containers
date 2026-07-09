# syntax=docker/dockerfile:1
# LiteLLM: Call all LLM APIs using the OpenAI format [Anthropic, Huggingface, Cohere, TogetherAI, Azure, OpenAI, etc.]
ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash}

ENV OPENAI_API_KEY="" \
    COHERE_API_KEY="" \
    PATH="${PATH}:/litellm/bin"

RUN \
    apk add --no-cache -t .litellm-build \
        ca-certificates \
        python3-dev \
        py3-pip \
        build-base \
        git \
        curl; \
    \
    python3 -m venv /litellm; \
    . /litellm/bin/activate; \
    pip install --no-cache-dir --upgrade pip; \
    pip install --no-cache-dir litellm[proxy]; \
    \
    addgroup -g 65535 litellm; \
    adduser --shell /sbin/nologin --disabled-password -h /home/litellm --uid 65535 --ingroup litellm litellm; \
    \
    apk add --no-cache -t .litellm-security \
        clamav \
        freshclam; \
    freshclam; \
    clamscan -rvi -l /home/litellm/last_scan.log --exclude-dir="^/sys" /; \
    chown litellm:litellm /home/litellm/last_scan.log; \
    \
    apk del --purge .litellm-build .litellm-security; \
    rm -rf /var/cache/apk/* /root/.cache/*; \
    \
    chown -R litellm:litellm /litellm

USER litellm
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD curl -f http://localhost:4000/health || exit 1
CMD ["sh", "-c", "litellm --config /app/litellm_config.yaml --port 4000"]