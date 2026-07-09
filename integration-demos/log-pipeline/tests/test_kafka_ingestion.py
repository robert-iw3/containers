import json
import uuid

from confluent_kafka import Consumer, Producer


def test_topic_exists_with_expected_partitions(kafka_admin, kafka_topic):
    metadata = kafka_admin.list_topics(timeout=10)
    assert kafka_topic in metadata.topics
    partitions = metadata.topics[kafka_topic].partitions
    assert len(partitions) >= 1


def test_produce_and_consume_round_trip(kafka_bootstrap_servers, kafka_topic):
    producer = Producer({"bootstrap.servers": kafka_bootstrap_servers})
    marker = str(uuid.uuid4())
    payload = json.dumps({"marker": marker, "service": "test-harness", "level": "INFO"})

    producer.produce(kafka_topic, key=b"test-harness", value=payload.encode("utf-8"))
    producer.flush(timeout=10)

    consumer = Consumer(
        {
            "bootstrap.servers": kafka_bootstrap_servers,
            "group.id": f"pytest-{marker}",
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([kafka_topic])

    found = False
    for _ in range(200):
        message = consumer.poll(timeout=1.0)
        if message is None or message.error():
            continue
        body = json.loads(message.value())
        if body.get("marker") == marker:
            found = True
            break

    consumer.close()
    assert found, "produced message was never observed by a consumer"
