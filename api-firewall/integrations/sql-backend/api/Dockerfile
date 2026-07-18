# Record-store API: FastAPI + pymssql over sharded SQL Server, designed to
# run behind the Wallarm API Firewall (../../..). Stateless — scale with
# `docker compose up -d --scale api=N`.
ARG repo="docker.io" \
    base_image="library/python" \
    image_hash="28255a3ace7eb4c48bc1b57b90af29e1bc82b4fd6c60614a8e3dce61b87ff941"

FROM ${repo}/${base_image}@sha256:${image_hash}

RUN groupadd -g 65535 api && \
    useradd -m -u 65535 -g api -s /usr/sbin/nologin api

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py db.py export_spec.py healthcheck.py ./

USER api
EXPOSE 8000
CMD [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" ]
