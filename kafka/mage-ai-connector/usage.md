##

Basic
```yaml
connector_type: kafka
bootstrap_server: "localhost:9092"
topic: topic_name
api_version: "0.10.2"
batch_size: 100
timeout_ms: 500
```

SSL Auth
```yaml
security_protocol: "SSL"
ssl_config:
  cafile: "CARoot.pem"
  certfile: "certificate.pem"
  keyfile: "key.pem"
  password: password
  check_hostname: true
```

