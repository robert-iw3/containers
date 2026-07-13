# Stack add-ons

Optional components that attach to a **running** Elastic stack (the one brought
up from this directory via `docker-compose.yml` / `docker-compose-multi-node.yml`
or the generated `gen_stack.py` compose). Each add-on is its own Compose project
that joins the stack's network and reuses its TLS CA — nothing is duplicated.

| Add-on | Directory | Purpose |
| --- | --- | --- |
| APM Server | `apm-server/` | Application performance monitoring ingest (`:8200`) |
| Metricbeat | `beats/metric/` | Host/stack metrics + stack monitoring |
| Filebeat | `beats/file/` | Container log shipping |
| Heartbeat | `beats/heart/` | Uptime/synthetic monitoring |
| Curator | `curator/` | Scheduled index maintenance/retention |
| Fleet Server | `fleet/` | Standalone Fleet Server (if not run inside the stack) |
| Logstash | `data-pipeline/logstash/` | Rich parsing/enrichment ingest (grok, geoip, dissect) |
| Fluentd | `data-pipeline/fluentd/` | Lightweight forwarding ingest |

## How attachment works

Every add-on's `docker-compose.yml` declares the stack's network and cert volume
as **external**:

```yaml
networks:
  elastic:
    external: true
    name: ${STACK_NETWORK:-elastic_elastic}
volumes:
  certs:
    external: true
    name: ${STACK_CERTS:-elastic_certs}
```

- `STACK_NETWORK` / `STACK_CERTS` default to the names Compose creates when the
  stack is started from this directory (project name `elastic` →
  `elastic_elastic`, `elastic_certs`). If you started the stack under a different
  `COMPOSE_PROJECT_NAME`, set these in the stack `.env`. Confirm the real names
  with `docker network ls` / `docker volume ls`.
- The CA is mounted read-only at `/certs`; every add-on config trusts
  `/certs/ca/ca.crt` and talks to `https://elasticsearch:9200` /
  `https://kibana:5601`.
- Credentials come from the **stack** `.env` (`env_file: ../.env`, or `../../.env`
  for the beats), so there is a single source of truth. Copy `.env.example` to
  `.env` and fill it in before starting the stack.

## Bring one up

```bash
# 1. stack is already running (docker compose up -d from this dir)
# 2. start an add-on:
cd apm-server        # or beats/metric, curator, fleet, ...
docker compose up -d --build
```

Tear down with `docker compose down` in the add-on directory; the stack keeps
running.

## Removed

- **Enterprise Search** was discontinued in Elastic 9.x (last release `8.18.6`)
  and is archived under `archive/enterprise-search/`. Its capabilities are now
  native: **Search Applications** (App Search replacement) and **Elastic
  Connectors** under `elastic__connectors/` (Workplace Search replacement).
