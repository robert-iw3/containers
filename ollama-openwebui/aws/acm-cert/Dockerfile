FROM hashicorp/terraform:1.12.0

RUN apk add make

WORKDIR /tmp
COPY . /tmp

ENTRYPOINT [ "/usr/bin/make" ]
