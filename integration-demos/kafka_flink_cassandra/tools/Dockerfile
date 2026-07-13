# Tools image for the producer and the Cassandra sink (kafka-python + cassandra-driver).
FROM docker.io/python:3.12-slim
RUN pip install --no-cache-dir kafka-python==2.0.6 pyyaml==6.0.3 cassandra-driver==3.29.2
WORKDIR /work
