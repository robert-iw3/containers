# demo-api: minimal backend that fetches short-lived DB credentials from
# Vault on every request and reaches PostgreSQL through its Consul Connect
# sidecar (mTLS). Debian-slim base: psycopg binary wheels don't cover musl.
FROM docker.io/library/python:3.13-slim

RUN pip install --no-cache-dir "psycopg[binary]==3.2.*" && \
    useradd --system --uid 65535 --shell /usr/sbin/nologin demo

COPY --chown=demo:demo app.py /app/app.py

USER demo
EXPOSE 8080
CMD ["python", "/app/app.py"]
