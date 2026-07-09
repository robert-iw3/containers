FROM cgr.dev/chainguard/wolfi-base

LABEL usage="docker run -i -t --privileged -v /var/run/docker.sock:/host/var/run/docker.sock -v /proc:/host/proc:ro  -v /etc:/host/etc:ro falcosecurity/falco:latest"
# NOTE: for the "least privileged" use case, please refer to the official documentation

ARG FALCO_VERSION=0.41.2
ARG VERSION_BUCKET=bin

ENV FALCO_VERSION=${FALCO_VERSION}
ENV VERSION_BUCKET=${VERSION_BUCKET}
ENV HOST_ROOT /host
ENV HOME /root

RUN \
    apk update ; \
    apk add --no-cache \
        curl \
        ca-certificates \
        jq \
        libstdc++

WORKDIR /

RUN \
    FALCO_VERSION_URLENCODED=$(echo -n ${FALCO_VERSION}|jq -sRr @uri) ; \
    curl -L -o falco.tar.gz \
    https://download.falco.org/packages/${VERSION_BUCKET}/$(uname -m)/falco-${FALCO_VERSION_URLENCODED}-$(uname -m).tar.gz ; \
    tar -xvf falco.tar.gz ; \
    rm -f falco.tar.gz ; \
    mv falco-${FALCO_VERSION}-$(uname -m) falco ; \
    rm -rf /falco/usr/src/falco-* ; \
    cp -r /falco/* / ; \
    rm -rf /falco

# Change the falco config within the container to enable ISO 8601 output.
ADD ../config/falco.iso8601_timeformat.yaml /etc/falco/config.d/

# Falcoctl is not included here.
RUN rm -rf /usr/bin/falcoctl /etc/falcoctl/

CMD ["/usr/bin/falco"]
