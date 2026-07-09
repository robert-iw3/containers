# Consul integration reference

The Ansible role's `consul {}` stanza (see `ansible/roles/nomad/templates/nomad.hcl.j2`,
gated by `nomad_consul_enabled`) only wires up address/auto-join. It assumes Consul is
deployed and managed separately (bring-your-own cluster), not by this repository. These
snippets are reference material for extending that stanza or configuring the external
Consul cluster's own ACLs — they are not applied automatically by anything here.

## Full `consul {}` stanza with TLS and ACL token

```hcl
consul {
  address      = "127.0.0.1:8500"
  grpc_address = "127.0.0.1:8502"
  token        = "<consul-acl-token>"

  ssl        = true
  verify_ssl = true
  ca_file    = "/etc/consul.d/tls/consul-agent-ca.pem"
  cert_file  = "/etc/consul.d/tls/consul-server-consul-0.pem"
  key_file   = "/etc/consul.d/tls/consul-server-consul-0-key.pem"

  server_service_name = "nomad"
  client_service_name = "nomad-client"
  auto_advertise       = true
  server_auto_join     = true
  client_auto_join     = true
}
```

## Consul agent config needed for Nomad Connect integration

```hcl
ports {
  grpc     = 8503
  grpc_tls = 8502
}

connect {
  enabled = true
}
```

## Consul ACL policies for a Nomad-facing agent token

```hcl
service_prefix "" { policy = "read" }
node_prefix    "" { policy = "read" }
```

## Consul ACL policy for a Nomad namespace integration

```hcl
agent_prefix "" {
  policy = "read"
}

namespace "nomad-ns" {
  acl = "write"

  key_prefix "" {
    policy = "read"
  }

  node_prefix "" {
    policy = "read"
  }

  service_prefix "" {
    policy = "write"
  }
}
```

## Host volumes for stateful workloads (client config)

The Podman driver supports the same `host_volume` client stanza as the Docker driver:

```hcl
client {
  enabled = true
  servers = ["nomad-server-1:4647", "nomad-server-2:4647", "nomad-server-3:4647"]

  host_volume "letsencrypt" {
    path      = "/etc/letsencrypt"
    read_only = false
  }
}
```

Add `host_volume` blocks like this directly to `ansible/roles/nomad/templates/nomad.hcl.j2`
if a job needs a specific host path mounted; there's no generic default since the right
paths are workload-specific.
