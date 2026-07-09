FROM docker.io/debian:13

ENV DEBIAN_FRONTEND=noninteractive \
    HADOOP_VERSION=3.5.0 \
    HADOOP_URL=https://dlcdn.apache.org/hadoop/common/hadoop-3.5.0/hadoop-3.5.0.tar.gz \
    HADOOP_HOME=/opt/hadoop-$HADOOP_VERSION \
    HADOOP_CONF_DIR=/etc/hadoop \
    MULTIHOMED_NETWORK=1 \
    USER=root \
    PATH=$HADOOP_HOME/bin/:$PATH \
    JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64/

RUN \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      openjdk-11-jdk \
      net-tools \
      curl \
      gnupg \
      tar \
      openssl \
      netcat-traditional \
      libsnappy-dev; \
    rm -rf /var/lib/apt/lists/*; \
    curl -O https://dist.apache.org/repos/dist/release/hadoop/common/KEYS; \
    gpg --import KEYS; \
    curl -fSL "$HADOOP_URL" -o /tmp/hadoop.tar.gz; \
    curl -fSL "https://downloads.apache.org/hadoop/common/hadoop-$HADOOP_VERSION/hadoop-$HADOOP_VERSION.tar.gz.asc" -o /tmp/hadoop.tar.gz.asc; \
    gpg --verify /tmp/hadoop.tar.gz.asc; \
    tar -xvf /tmp/hadoop.tar.gz -C /opt/; \
    rm /tmp/hadoop.tar.gz*; \
    ln -s /opt/hadoop-$HADOOP_VERSION/etc/hadoop /etc/hadoop; \
    mkdir /opt/hadoop-$HADOOP_VERSION/logs; \
    mkdir /hadoop-data

ADD entrypoint.sh /entrypoint.sh

RUN chmod a+x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
