FROM docker.io/debian:13

ENV DEBIAN_FRONTEND=noninteractive
ENV HBASE_VERSION 2.6.6
ENV HBASE_URL https://dlcdn.apache.org/hbase/${HBASE_VERSION}/hbase-${HBASE_VERSION}-bin.tar.gz
ENV HBASE_PREFIX=/opt/hbase
ENV HBASE_CONF_DIR=/etc/hbase
ENV USER=root
ENV PATH=$HBASE_PREFIX/bin:/usr/local/bin:/usr/bin:$PATH
ENV HBASE_HOME=$HBASE_PREFIX
ENV HBASE_MANAGES_ZK=false
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64/

RUN \
    apt-get update; \
    apt-get install -y \
        openjdk-11-jdk \
        openssl \
        netcat-traditional \
        net-tools \
        curl \
        tar; \
    \
    curl -fSL "$HBASE_URL" -o /tmp/hbase.tar.gz; \
    tar -zxvf /tmp/hbase.tar.gz -C /opt/hbase --strip-components=1 ; \
    mv /opt/hbase-${HBASE_VERSION} /opt/hbase; \
    rm /tmp/hbase.tar.gz*; \
    \
    mkdir ${HBASE_CONF_DIR}; \
    ln -s ${HBASE_PREFIX}/conf/ ${HBASE_CONF_DIR}; \
    echo 'export HBASE_MANAGES_ZK=false' >> ${HBASE_PREFIX}/conf/hbase-env.sh; \
    echo 'export HBASE_MASTER_OPTS="$HBASE_MASTER_OPTS -Dhbase.master.manage.zookeeper=false"' >> ${HBASE_PREFIX}/conf/hbase-env.sh; \
    mkdir ${HBASE_PREFIX}/logs; \
    chown -R root:root $HBASE_HOME/logs; \
    mkdir /hadoop-data

COPY hbase-site.xml ${HBASE_PREFIX}/conf/hbase-site.xml
ADD docker-entrypoint.sh /entrypoint.sh
RUN chmod a+x /entrypoint.sh
EXPOSE 9000 50070
EXPOSE 16010
EXPOSE 16030
EXPOSE 2182
EXPOSE 9090
EXPOSE 10000
ENTRYPOINT ["/entrypoint.sh"]