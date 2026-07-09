FROM docker.io/debian:13

ENV MAX_HEAP_SIZE 4G
ENV HEAP_NEWSIZE 800M

ARG CASSANDRA_VERSION=5.0.8

RUN set -e; \
    apt-get update; \
    apt-get install -y \
        curl \
        wget \
        bash \
        openjdk-17-jdk \
        libnss3 \
        libc6 \
        coreutils \
        procps\
        gnupg2 \
        python3 \
        python3-pip; \
    apt-get clean; \
    mkdir /opt/cassandra; \
    cd /tmp/; \
    curl -O https://downloads.apache.org/cassandra/KEYS; \
    gpg --import KEYS; \
    wget --progress=bar:force -O apache-cassandra-${CASSANDRA_VERSION}-bin.tar.gz \
        https://dlcdn.apache.org/cassandra/${CASSANDRA_VERSION}/apache-cassandra-${CASSANDRA_VERSION}-bin.tar.gz; \
    wget https://downloads.apache.org/cassandra/${CASSANDRA_VERSION}/apache-cassandra-${CASSANDRA_VERSION}-bin.tar.gz.asc; \
    gpg --verify apache-cassandra-${CASSANDRA_VERSION}-bin.tar.gz.asc apache-cassandra-${CASSANDRA_VERSION}-bin.tar.gz; \
    tar xzf apache-cassandra-${CASSANDRA_VERSION}-bin.tar.gz --strip-components=1 -C "/opt/cassandra"; \
    rm apache-cassandra-${CASSANDRA_VERSION}-bin.tar.gz*; \
    ln -s /opt/cassandra/bin/cqlsh /usr/local/bin/cqlsh; \
    mkdir /opt/cassandra/conf

COPY cassandra.yaml /opt/cassandra/conf/
COPY --chmod=755 cassandra-env.sh /opt/cassandra/conf/
COPY --chmod=755 start-cassandra /usr/local/bin/

EXPOSE 7000 7001 7199 9160 9042

CMD ["/usr/local/bin/start-cassandra"]