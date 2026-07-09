# Nomad configuration for a single-node setup (server + client)

# Data directory for Nomad
data_dir = "/opt/nomad/data"

# Bind address for Nomad
bind_addr = "0.0.0.0"

# Server configuration (enable server mode)
server {
  enabled = true
  bootstrap_expect = 1 # Single-node cluster
}

# Client configuration (enable client mode)
client {
  enabled = true
  servers = ["127.0.0.1:4647"]
}

# Consul integration (optional, disabled by default)
consul {
  address = "127.0.0.1:8500"
  auto_advertise = true
}

# Telemetry (optional, for monitoring)
telemetry {
  collection_interval = "1s"
  disable_hostname = true
  prometheus_metrics = true
}