ARG ALPINE_VERSION=3.24
FROM docker.io/alpine:${ALPINE_VERSION}

ARG TSHARK_VERSION=4.6.6-r0

RUN \
    apk add --no-cache \
        coreutils \
        tshark=${TSHARK_VERSION}; \
    mkdir /data

COPY --chmod=755 capture.sh .

ENV FILTER="icmp"
ENV IFACE="any"
ENV DURATION="600"
ENV MAXFILESIZE="1000"
ENV MAXFILENUM="10"
ENV FILENAME="dump"
ENV FORMAT="pcapng"
ENV SNAPLENGTH=""

CMD [ "/bin/sh", "-c", "/capture.sh" ]
