ARG ELASTIC_VERSION

# https://www.docker.elastic.co/
FROM docker.elastic.co/logstash/logstash-wolfi:${ELASTIC_VERSION}
USER root
RUN apt-get update -y && apt-get autoremove -y
# Add your logstash plugins setup here
# Example: RUN logstash-plugin install logstash-filter-json
RUN logstash-plugin install logstash-filter-json
RUN logstash-plugin install logstash-filter-grok
RUN logstash-plugin install logstash-filter-csv
RUN logstash-plugin install logstash-filter-xml

USER logstash:root
