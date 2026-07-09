FROM docker.io/alpine:3.24

LABEL org.opencontainers.image.name='So Now You Know.' \
      org.opencontainers.image.description='Scan code directories for code quality and security checks.' \
      org.opencontainers.image.usage='https://snyk.io/' \
      MAINTAINER="@rw"

RUN apk add --no-cache -U \
      python3 \
      py3-pip \
      nodejs \
      npm \
      bash \
      wget \
      unzip \
      ca-certificates; \
    npm install -g snyk snyk-to-html; \
    pip install requests

RUN addgroup -g 65535 snyk ; \
    adduser -h /home/snyk -s /bin/bash -D -u 65535 -G snyk snyk ; \
    mkdir /reports && chown -R snyk:snyk /reports /home/snyk

WORKDIR /home/snyk

COPY main.py /home/snyk/main.py

USER snyk

ENTRYPOINT ["python3", "/home/snyk/main.py"]
