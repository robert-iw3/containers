FROM docker.io/debian:12

ENV DEBIAN_FRONTEND=noninteractive
ENV HADOOP_VERSION=3.5.0
ENV HADOOP_URL=https://dlcdn.apache.org/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz
ENV HADOOP_HOME=/opt/hadoop-${HADOOP_VERSION}
ENV HADOOP_CONF_DIR=/etc/hadoop
ENV MULTIHOMED_NETWORK=1
ENV USER=root
ENV PATH=${HADOOP_HOME}/bin/:$PATH
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64/

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      openjdk-17-jdk-headless \
      net-tools \
      curl \
      gnupg \
      tar \
      openssl \
      netcat-traditional \
      libsnappy-dev; \
    rm -rf /var/lib/apt/lists/*; \
    curl -fSL -o /tmp/KEYS https://dist.apache.org/repos/dist/release/hadoop/common/KEYS; \
    gpg --import /tmp/KEYS; \
    curl -fSL "$HADOOP_URL" -o /tmp/hadoop.tar.gz; \
    curl -fSL "https://downloads.apache.org/hadoop/common/hadoop-$HADOOP_VERSION/hadoop-$HADOOP_VERSION.tar.gz.asc" -o /tmp/hadoop.tar.gz.asc; \
    gpg --verify /tmp/hadoop.tar.gz.asc /tmp/hadoop.tar.gz; \
    tar -xf /tmp/hadoop.tar.gz -C /opt/; \
    rm /tmp/hadoop.tar.gz* /tmp/KEYS; \
    ln -s /opt/hadoop-$HADOOP_VERSION/etc/hadoop /etc/hadoop; \
    mkdir /opt/hadoop-$HADOOP_VERSION/logs; \
    mkdir /hadoop-data

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 && \
    ln -sf /usr/bin/python3 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

ADD entrypoint.sh /entrypoint.sh

RUN chmod a+x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
