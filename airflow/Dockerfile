ARG AIRFLOW_VERSION=3.3.0
FROM docker.io/apache/airflow:${AIRFLOW_VERSION}

USER root
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

USER airflow
ARG AIRFLOW_VERSION
COPY --chown=airflow:0 ./requirements.txt /opt/airflow/requirements.txt
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /opt/airflow/requirements.txt