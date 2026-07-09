# Log Pipeline

An end-to-end streaming log/event pipeline built entirely from images already used elsewhere in this
repo: Kafka ingests synthetic application logs, a Spark Structured Streaming job enriches and aggregates
them in near real time, Elasticsearch stores both the raw events and the rolled-up metrics, Grafana
visualizes the result, and Airflow runs a daily batch job that summarizes each day and enforces
retention.

```
log-generator -> Kafka -> Spark Structured Streaming -> Elasticsearch -> Grafana
                                                              ^
                                                              |
                                                    Airflow (daily rollup + retention)
```

## Components

| Service        | Image                                              | Role                                             |
|----------------|-----------------------------------------------------|---------------------------------------------------|
| kafka          | `apache/kafka:4.3.1`                                | Single-node KRaft broker                          |
| log-generator  | built from `log-generator/`                         | Produces synthetic JSON log events                |
| spark-master / spark-worker / spark-submit | `apache/spark:4.1.2-python3` | Standalone Spark cluster running the streaming job |
| elasticsearch  | `docker.elastic.co/elasticsearch/elasticsearch:9.4.3` | Stores raw events, 1-minute metrics, daily summaries |
| grafana        | `grafana/grafana-oss:13.0.2`                        | Dashboards over the Elasticsearch data            |
| airflow        | built from `airflow/` (`apache/airflow:3.3.0`)      | Daily rollup + retention DAG                      |

## Running it

```
cp .env.example .env
docker compose up -d --build
```

Then:

- Grafana: http://localhost:3000 (`admin` / `admin` by default) — the "Log Pipeline Overview" dashboard
  is provisioned automatically.
- Spark master UI: http://localhost:8082
- Airflow: http://localhost:8081
- Elasticsearch: http://localhost:9200

It takes 30-60 seconds after `up` for Kafka, Elasticsearch, and the Spark cluster to become healthy
before the streaming job starts producing documents. `docker compose logs -f spark-submit` shows the
streaming job's progress.

## Scaling it up

This is deliberately foundational so each piece can be scaled independently:

- **More log volume**: `docker compose up -d --scale log-generator=5`, or raise `LOG_RATE_PER_SEC` in
  `.env`.
- **More Kafka throughput**: raise `KAFKA_PARTITIONS` in `.env` before the first `docker compose up`
  (topics are created once by `kafka-init`); add more `kafka` broker services and update
  `KAFKA_CONTROLLER_QUORUM_VOTERS`/`KAFKA_ADVERTISED_LISTENERS` for a real multi-broker cluster.
- **More stream processing capacity**: `docker compose up -d --scale spark-worker=5`.
- **Elasticsearch**: this demo runs single-node; a real deployment would run a multi-node cluster (see
  `elastic/` elsewhere in this repo) and split `logs-raw`/`logs-metrics-1m` across dedicated data tiers
  with ILM policies instead of the fixed `RETENTION_DAYS` delete-by-query approach used here.

## Data model

- `logs-raw` — every parsed log event (`timestamp`, `service`, `host`, `level`, `message`, `status_code`,
  `duration_ms`, `trace_id`).
- `logs-metrics-1m` — 1-minute tumbling-window aggregates per `service`/`level`: event count, error
  count, average duration, distinct host count.
- `logs-daily-summary` — one document per day, written by the Airflow DAG, with per-service rollups and
  an overall error rate.

## Notes on production-readiness

This demo intentionally keeps a few things simple that a real deployment would not:

- Elasticsearch security (`xpack.security.enabled`) is disabled and there's no TLS between services.
  Enable both and add authentication before running this anywhere reachable.
- Kafka runs as a single broker with replication factor 1 — no fault tolerance.
- Retention is enforced with `delete_by_query` from Airflow rather than Elasticsearch ILM, which is
  simpler to read here but less efficient at scale.
