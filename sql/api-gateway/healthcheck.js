// Container healthcheck: exit 0 iff the gateway answers /health.
fetch('http://127.0.0.1:3000/health')
  .then((r) => process.exit(r.ok ? 0 : 1))
  .catch(() => process.exit(1));
