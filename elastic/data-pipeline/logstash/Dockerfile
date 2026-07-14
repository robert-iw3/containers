ARG ELASTIC_VERSION=9.4.3

FROM docker.elastic.co/logstash/logstash:${ELASTIC_VERSION}

COPY config/logstash.yml /usr/share/logstash/config/logstash.yml
COPY config/pipelines.yml /usr/share/logstash/config/pipelines.yml
COPY config/log4j2.properties /usr/share/logstash/config/log4j2.properties
COPY pipeline/ /usr/share/logstash/pipeline/

EXPOSE 5044 50000 9600
