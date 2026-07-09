# Airflow

Apache **Airflow 3.3** on Docker/Podman Compose, Kubernetes, or multi-host Ansible,
with TLS on the login/API, a production IoT-telemetry ETL pipeline, and a set of
example DAGs. The stack uses the **CeleryExecutor** and the full Airflow 3.x plane:
api-server, scheduler, dag-processor, triggerer, and celery workers, backed by
Postgres and Redis.

## Layout

```
airflow/
├── docker-compose.yaml        # full 3.x stack (postgres, redis, api-server,
│                              #   scheduler, dag-processor, triggerer, worker, init)
├── k8s-deployment.yaml        # Kubernetes: all planes + worker HPA autoscaling + TLS
├── Dockerfile                 # optional custom image (extends apache/airflow:3.3.0)
├── requirements.txt           # extra libs baked into the custom image
├── deploy_airflow.py          # docker/podman/kubernetes deploy wrapper
├── telemetry_pipeline/        # production DAGs (own directory)
│   ├── telemetry_etl.py       #   extract → validate → rollup/anomaly → Postgres → Asset
│   ├── telemetry_report.py    #   Asset-triggered downstream summary (data-aware)
│   └── common.py              #   shared constants (non-DAG module)
├── example_dags/              # illustrative example DAGs (operators, sensors, taskflow…)
├── plugins/                   # custom operators / timetables / triggers
├── scripts/                   # gen_tls_cert.sh, users.sh, connections.sh, dbinit.sh
├── ansible/                   # multi-host deployment (control + worker groups) + molecule
├── certs/                     # TLS material (gitignored; created by gen_tls_cert.sh)
└── tests/                     # pytest: config invariants + DagBag integrity
```

## Quick start (Compose)

```bash
# 1. TLS cert for the api-server (self-signed; replace for production)
bash scripts/gen_tls_cert.sh

# 2. Secrets
cp .env.example .env
# edit .env: set a Fernet key, JWT secret, and passwords
#   FERNET: python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# 3. Bring it up
docker compose up -d          # or: podman-compose up -d
```

- **UI / login: https://localhost:8080** (TLS; the self-signed cert triggers a browser warning)
- Default credentials come from `.env` (`airflow` / `airflow` out of the box)
- Health: `curl -k https://localhost:8080/api/v2/monitor/health`
- Celery Flower (optional): `docker compose --profile flower up -d flower` → http://localhost:5555

> Under **rootless podman** the runtime services must be started together so the
> `service_completed_successfully` init dependency resolves; if `podman-compose up`
> leaves some containers `Created`, run
> `podman start $(podman ps -aq --filter name=airflow)` once.

## TLS

The api-server serves **HTTPS** for both the UI/login and the internal execution API
that the scheduler, dag-processor, triggerer, and workers use. `scripts/gen_tls_cert.sh`
generates a self-signed cert with SANs for `airflow-apiserver`, the k8s service DNS,
and `localhost`. Components trust it via `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`, and the
execution API URL is `https://…`. Plain HTTP is refused. Swap in a real cert
(`AIRFLOW__API__SSL_CERT`/`AIRFLOW__API__SSL_KEY`) for production.

## Telemetry pipeline (`telemetry_pipeline/`)

A production-shaped ETL pipeline modelling IoT sensor telemetry:

- **`telemetry_etl`** (`*/15 * * * *`) — `resolve_window → extract → validate →
  transform → load → publish_metrics`. Windowed per-`(sensor, metric)` rollups
  (count/avg/min/max/p95/stdev) with z-score anomaly flagging, a quality gate that
  fails the run on too many bad rows, and an **idempotent** delete-then-insert load
  into a Postgres warehouse. Deterministic per window, so backfills/retries are
  reproducible. On success it updates an **Asset**.
- **`telemetry_report`** — no schedule; **triggered by the Asset** `telemetry_etl`
  produces (data-aware scheduling). Summarises the freshly-loaded window.

The warehouse connection (`AIRFLOW_CONN_TELEMETRY_WAREHOUSE`) points at the bundled
Postgres out of the box so the pipeline runs end to end with no external setup; repoint
it at a real warehouse for production. Swap `extract_telemetry` for a real source
(Kafka/MQTT/ScyllaDB/S3) and keep the rest.

## Kubernetes

```bash
bash scripts/gen_tls_cert.sh
kubectl create secret tls airflow-tls -n airflow --cert=certs/tls.crt --key=certs/tls.key
# edit the Fernet/JWT/password values in the Secret in k8s-deployment.yaml, then:
kubectl apply -f k8s-deployment.yaml
```

`k8s-deployment.yaml` deploys every plane plus Postgres, Redis, and a one-shot
`airflow-db-init` Job. Shared config lives in a ConfigMap, secrets in a Secret, and
both are pulled via `envFrom`. The **worker pool autoscales** via a
`HorizontalPodAutoscaler` (CPU, 2–10 replicas, drain-aware scale-down). For
queue-aware scaling (on pending Celery tasks, and to zero), install **KEDA** and use a
`ScaledObject` instead of the HPA. The DAGs use a shared `ReadWriteMany` PVC for the
demo — prefer git-sync or a baked image, and remote logging (S3/GCS), in production.

## Multi-host (Ansible)

`ansible/` deploys the cluster across hosts:

- **`airflow_control`** — Postgres, Redis, api-server, scheduler, dag-processor, triggerer
- **`airflow_workers`** — celery workers (scale horizontally, distinct IPs/hosts)

Workers reach the control host for the DB, broker, and HTTPS execution API, so the
control host's `airflow_advertise_host` must be cluster-reachable. The role generates
the TLS cert on the control host and distributes it to the workers so they trust the
execution API.

```bash
cd ansible
ansible-playbook -i inventory.ini deploy-airflow.yml
# sync the repo DAGs onto every node:
ansible-playbook -i inventory.ini deploy-airflow.yml -e dags_src=$PWD/..
```

A **Molecule** scenario (`roles/airflow_node/molecule/default/`) converges control +
worker on one AlmaLinux systemd container and verifies the api-server serves HTTPS,
plain HTTP is refused, and the worker registers with the broker.

## Custom image

`docker-compose.yaml` and `k8s-deployment.yaml` use the stock `apache/airflow:3.3.0`.
To bake in extra libraries, build the `Dockerfile` (adds the `requirements.txt` deps —
scikit-learn, matplotlib, psycopg2-binary, redis, the pentaho plugin) and set
`AIRFLOW_IMAGE_NAME` to your image. Pins target cp313 wheels for the image's Python 3.13.

## Tests

```bash
pip install -r tests/requirements.txt
pytest tests/                 # config/TLS/migration invariants + pipeline-source checks
```

The DagBag-integrity tests (no import errors, expected tasks, asset wiring) run when
`apache-airflow` is importable; otherwise they skip and the static invariants still run.

## Airflow 3.x notes

Key differences this deployment accounts for vs 2.x:

- `webserver` → **`api-server`** (`/api/v2/monitor/health`); the standalone
  **`dag-processor`** is now required.
- Auth via the **FAB auth manager** (`AIRFLOW__CORE__AUTH_MANAGER`); components
  authenticate over the execution API with `AIRFLOW__API_AUTH__JWT_SECRET` +
  `AIRFLOW__CORE__EXECUTION_API_SERVER_URL` (the 2.x webserver secret key is gone).
- `db init` → **`db migrate`**; the admin user is created via the
  `_AIRFLOW_DB_MIGRATE`/`_AIRFLOW_WWW_USER_*` entrypoint variables.
- Manual DAG runs may have **no data interval**, so DAGs must not assume
  `data_interval_start` exists (see `telemetry_etl.resolve_window`).
- `PYTHONPATH` is pinned to the user-site venv so `import airflow` works for any UID
  under rootless podman / OpenShift, where the image's HOME rewrite doesn't fire.
