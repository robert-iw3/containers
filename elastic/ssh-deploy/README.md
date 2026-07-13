# SSH multi-host deploy (non-Ansible)

Deploy the Elastic cluster across hosts with plain SSH -- an alternative to the
`../ansible/` role when you don't want Ansible.

1. Edit `cluster.hosts` (one line per node): `<role> <user@host> <advertise-ip>`.
2. Run from a control machine that has podman/docker (to mint certs) and SSH to each host:

```bash
ELASTIC_PASSWORD=... KIBANA_SYSTEM_PASSWORD=... ./deploy-cluster.sh cluster.hosts
```

`deploy-cluster.sh` mints one CA + per-node certs (SANs cover each advertise IP),
then for each host: preps it (`prepare-host.sh`), pushes the certs + `node-up.sh`,
starts the Elasticsearch/Kibana container wired into the cluster (discovery via the
ES advertise IPs, TLS on), and finally sets the `kibana_system` password.

Scale by adding lines to `cluster.hosts` (3-7 `es`, 1-2 `kibana`). Same topology as
the Ansible role and the `gen_stack.py` compose -- pick whichever driver you prefer.
