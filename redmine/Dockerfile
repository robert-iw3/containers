# syntax=docker/dockerfile:1
FROM docker.io/redmine:6.1.2

RUN apk add --no-cache \
    bash \
    tzdata \
    curl \
    && rm -rf /var/cache/apk/*

ENV RAILS_ENV=production \
    RAILS_LOG_TO_STDOUT=true \
    HOME=/home/redmine

RUN mkdir -p /home/redmine \
    && chown -R redmine:redmine /home/redmine \
    && chmod -R 1777 /home/redmine

COPY docker-entrypoint.sh /
RUN chmod +x /docker-entrypoint.sh

EXPOSE 3000

# Volume for persistent data
VOLUME /usr/src/redmine/files

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["rails", "server", "-b", "0.0.0.0"]