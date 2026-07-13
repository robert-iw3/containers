# Data ingestion with Apache Kafka and Elasticsearch

A self-contained demo of a Kafka → Elasticsearch ingestion pipeline, visualized
in Kibana. It offers two interchangeable paths from Kafka to Elasticsearch:

1. **Kafka Connect** with the Elasticsearch sink connector (no code).
2. **Python consumer** that reads the topic and bulk-indexes (`kafka_consumer.py`).

## Services

Managed with Docker Compose:

- **Kafka** — single node in KRaft mode (no ZooKeeper), `apache/kafka`.
- **Kafka Connect** — hosts the Elasticsearch sink connector.
- **Elasticsearch** — stores and indexes messages (single node, security off for
  the demo).
- **Kibana** — visualization at http://localhost:5601.

Versions come from the environment: `ELASTIC_VERSION` (default `9.4.3`),
`KAFKA_IMAGE`, `CONNECT_IMAGE`, `ES_SINK_VERSION`.

## Prerequisites

- Docker and Docker Compose.
- Python 3.x for the producer/consumer scripts (`pip install -r requirements.txt`).

## Bring up the stack

```bash
docker compose up -d
```

Kafka is on `localhost:9092` (host) / `kafka:29092` (in-network), Connect on
`:8083`, Elasticsearch on `:9200`, Kibana on `:5601`.

## Path 1 — Kafka Connect sink

Register the Elasticsearch sink once Connect is healthy:

```bash
curl -X POST -H "Content-Type: application/json" \
  --data @kafka-connect/es-sink.json \
  http://localhost:8083/connectors
```

It consumes the `logs` topic and indexes into the `logs` index.

## Path 2 — Python consumer

```bash
python kafka_consumer.py
```

Reads the `logs` topic in batches and bulk-indexes into Elasticsearch.

## Produce sample data

```bash
python kafka_producer.py
```

Sends batches of synthetic log messages to the `logs` topic.

## Verify in Kibana

Open http://localhost:5601, create a data view on the `logs` index, and explore
the messages in Discover.
