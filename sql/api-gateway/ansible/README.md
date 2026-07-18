# Ansible: deploy the SQL stack across separate hosts

Deploys each component of the stack to its own VM or bare-metal host:

```
[loadbalancer]  nginx | haproxy   ->  public entry point (:80)
      │
[gateways]      API gateway x N   ->  stateless, pooled, safe operations
      │
[redis]  shard map + rate limit   [sql_shards]  tuned SQL Server x N
```

Each component runs as a container; components reach each other over the host
IPs and published ports declared in the inventory (not compose DNS).

## Layout

```
ansible/
├── inventory.ini        # host groups: redis, sql_shards, gateways, loadbalancer
├── group_vars/all.yml   # engine, ports, tuning, secrets (override with Vault)
├── site.yml             # ordered plays: common -> redis -> shards -> gateways -> lb
└── roles/
    ├── common/          # container engine + DB-host kernel tuning
    ├── redis/
    ├── sql_shard/       # builds the tuned shard image (Dockerfile.mssql)
    ├── gateway/         # builds the gateway image; SQL_SHARDS from inventory
    └── loadbalancer/    # nginx or haproxy, backends from the gateways group
```

Build contexts (Dockerfiles, gateway source, tuning scripts) are copied from
the parent `api-gateway/` directory, so this deploys the same artifacts the
compose UAT/stress tests exercise.

## Usage

1. Edit `inventory.ini` with your hosts (the first `sql_shards` host is
   shard 0, the second shard 1, …).
2. Put real secrets in an encrypted file rather than `group_vars/all.yml`:
   ```sh
   ansible-vault create group_vars/vault.yml   # sql_sa_password, jwt_secret, redis_password
   ```
3. Choose the load balancer in `group_vars/all.yml` (`lb_engine: nginx|haproxy`).
4. Deploy:
   ```sh
   ansible-playbook -i inventory.ini site.yml --ask-vault-pass
   ```

Deploy or update a single tier with tags:

```sh
ansible-playbook -i inventory.ini site.yml --tags gateway
ansible-playbook -i inventory.ini site.yml --tags shard
ansible-playbook -i inventory.ini site.yml --tags lb
```

## Notes

- `container_engine`/`compose_cmd` default to Docker; set them to
  `podman`/`podman-compose` for a Podman fleet.
- The gateway self-provisions each shard's database and schema on first start,
  so no separate migration step is required.
- Scale a tier by adding hosts to its inventory group and re-running the
  relevant tagged play; the load-balancer config is regenerated from the
  `gateways` group.
- Firewall the `sql_shards` and `redis` hosts so only the gateway hosts can
  reach `1433`/`6379`; expose only the load balancer publicly.
