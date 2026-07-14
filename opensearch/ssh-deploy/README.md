# SSH multi-host deploy (no ansible)

Brings up an OpenSearch cluster across hosts over SSH with TLS. One node
container per host, `--network host`.

1. List your nodes in `cluster.hosts`: `<node-name> <ssh-target> <advertise-host>`.
   The node index (line order) maps to `node{N}.pem` from
   `../certs/generate-certificates.sh`.
2. Ensure passwordless SSH + sudo to each target.
3. Run:

   ```bash
   OPENSEARCH_INITIAL_ADMIN_PASSWORD='Str0ng!pass' ./deploy-cluster.sh
   ```

It mints certs for the node count, prepares each host (`host-prep`), ships the
per-node cert + `opensearch.yml` + security config, and starts the node.

After the nodes form a cluster, initialize the security index once from any node:

```bash
docker exec -it opensearch \
  plugins/opensearch-security/tools/securityadmin.sh \
  -cd config/opensearch-security -icl -nhnv \
  -cacert config/certs/root-ca.pem \
  -cert config/certs/admin.pem -key config/certs/admin-key.pem
```
