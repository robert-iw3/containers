## base #############################################################################################
FROM otel/opentelemetry-collector-contrib:0.156.0 AS col
FROM otel/opentelemetry-collector-opampsupervisor:0.156.0 AS supervisor
FROM hairyhenderson/gomplate:v5.1.0-alpine AS gomplate

FROM alpine:latest@sha256:79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f AS base

ARG USER_UID=10001
ARG USER_GID=10001

# Install certs, create user/group, and make the writable data dir
RUN apk add --no-cache ca-certificates && \
  addgroup -S -g ${USER_GID} otel && \
  adduser  -S -u ${USER_UID} -G otel otel && \
  install -d -m 0777 -o ${USER_UID} -g ${USER_GID} /etc/otel/supervisor-data

# Copy gomplate binary from the gomplate image
COPY --from=gomplate /bin/gomplate /usr/local/bin/gomplate

USER ${USER_UID}:${USER_GID}

COPY --from=supervisor --chmod=755 /usr/local/bin/opampsupervisor /opampsupervisor
COPY --from=col --chmod=755 /otelcol-contrib /otelcontribcol

# Copy entrypoint and log rotation scripts
COPY --chmod=755 ./entrypoint.sh /entrypoint.sh
COPY --chmod=755 ./log-rotator.sh /log-rotator.sh

## dev ##############################################################################################
FROM base AS dev

COPY ./config.yaml /etc/otelcol-contrib/config.yaml
COPY ./supervisor_docker.yaml.tmpl /etc/otel/supervisor.yaml.tmpl

EXPOSE 4317 4318 13133

ENTRYPOINT ["/entrypoint.sh", "/opampsupervisor"]

## prod #############################################################################################
FROM base AS prod

COPY ./config.yaml /etc/otelcol-contrib/config.yaml
COPY ./supervisor_docker.yaml.tmpl /etc/otel/supervisor.yaml.tmpl

EXPOSE 4317 4318 13133

ENTRYPOINT ["/entrypoint.sh", "/opampsupervisor"]
