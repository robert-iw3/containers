## spark

Apache Spark 4.1.2 standalone cluster for large-scale data / ML processing —
built for high-volume telemetry: an ETL + MLlib pipeline, dynamic-allocation
autoscaling, and three deployment avenues (single-host compose, multi-host
Ansible, Kubernetes).

### Images

`build.sh` builds a layered image set off one Spark base (Scala 2.13, Java 17,
numpy/pandas for PySpark ML):

```console
spark-base ──┬── spark-master
             ├── spark-worker
             ├── spark-history-server
             └── spark-submit ──┬── spark-python-template ── python-example
                                ├── spark-maven-template
                                └── spark-sbt-template
```

```bash
./build.sh            # build everything
./build.sh worker     # or a single image
```

### Quick start (single host)

```bash
docker compose up -d                    # master + 3 workers + history server
open http://localhost:8080              # master UI (workers registered)
open http://localhost:18080             # history server (completed jobs)
docker compose up -d --scale spark-worker=5   # more compute
```

### The telemetry pipeline (data + ML)

`pipelines/telemetry_pipeline.py` generates (or reads) high-volume device
telemetry, does structured per-minute windowed aggregation, and trains an MLlib
KMeans model to score anomalies — all distributed, all config-driven so the same
job scales from a laptop to hundreds of executors:

```bash
docker compose run --rm submit          # runs the pipeline against the cluster
# or explicitly, at scale:
docker compose run --rm submit \
  /spark/bin/spark-submit --master spark://spark-master:7077 \
  /pipelines/telemetry_pipeline.py --rows 50000000 --devices 5000 --output /tmp/out
```

Point `--input` at parquet/CSV to process real telemetry instead of synthetic
data. Verified end to end: 500k rows → 86,400 per-minute rollups → 8 anomaly
clusters, distributed across the workers.

### At-scale performance, baked in

`base/spark-defaults.conf` ships production defaults (override per job with
`--conf`):

- **Adaptive Query Execution** — right-sizes shuffle partitions and handles skew
  at runtime (the biggest win for skewed telemetry).
- **Dynamic allocation** — executors scale up under load and release when idle
  (1→50) with shuffle tracking so shed executors don't lose data. This is Spark's
  executor autoscaling.
- Kryo serialization, shuffle/RDD compression, event logging for the history
  server.

### Multi-host deployment (Ansible)

`ansible/` deploys a real distributed cluster across separate machines, each with
its own IP/hostname. The master advertises its reachable address and workers
connect to it cross-host:

```bash
cd ansible
# edit inventory.ini: one host under [spark_master], N under [spark_workers],
# each with ansible_host + spark_advertise_host (its private IP)
ansible-playbook -i inventory.ini deploy-spark.yml
```

Scale out by adding hosts under `[spark_workers]` and re-running.

### Kubernetes

`k8s-spark-cluster.yaml` runs the master + a worker Deployment with a
HorizontalPodAutoscaler (3→20 workers on CPU) + history server:

```bash
kubectl apply -f k8s-spark-cluster.yaml
kubectl -n spark scale deployment/spark-worker --replicas=10   # or let the HPA do it
```

### Tests

```bash
pip install -r tests/requirements.txt && pytest tests/           # config + pipeline logic
(cd ansible/roles/spark_node && molecule test)                   # live cluster convergence
```

- `tests/test_spark.py` — cluster-config invariants (single image tag, the
  `--host` master flag that replaced the removed `--ip`, Scala 2.13 for Spark 4,
  the autoscaling defaults) and, when pyspark is installed, the pipeline's
  rollup/synthesis logic in local mode.
- **molecule** converges the Ansible role in a container and verifies a master +
  worker register and a Spark job runs to completion.

### Templates & examples

`template/{python,maven,sbt}` scaffold your own Spark apps on top of
`spark-submit`; `examples/{python,maven}` are runnable references.
