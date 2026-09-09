# syntax=docker/dockerfile:1
# The harness image: the connectors' dependencies plus curl for the checks.
#
# The shipped per-format Dockerfiles are separate images and are not tested by
# running this one. A connector that works here but cannot be built into its
# own image is still broken.

FROM docker.io/library/python:3.13-alpine

LABEL org.opencontainers.image.name='connector-uat' \
      org.opencontainers.image.description='Test harness for the Splunk connectors'

# libxml2/libxslt back lxml; curl drives the mock HEC control endpoints.
RUN apk add --no-cache libxml2 libxslt curl

# pyarrow for the Parquet source and its fixture. SQLite is in the standard
# library, so the SQL source needs no driver package to be exercised.
RUN pip install --no-cache-dir \
        aiohttp==3.14.3 \
        pyyaml==6.0.3 \
        lxml==6.0.2 \
        pyarrow==25.0.1

WORKDIR /uat
ENTRYPOINT ["/bin/sh"]
