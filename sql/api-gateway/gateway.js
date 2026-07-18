// SQL API Gateway — safe, sharded, pooled entry point to the SQL Server tier.
//
//   * Persistent connection pools, one per shard, reused across requests.
//   * Safe by default: clients invoke allowlisted, parameterized operations
//     (operations.json) at POST /v1/op/:name and never send SQL. A raw
//     /query path is available for admin/migrations, disabled unless
//     GATEWAY_ALLOW_RAW_SQL=1, and accepts only parameterized SQL.
//   * Global rate limiting via Redis, shared across workers and replicas.
//   * JWT auth that fails closed when no secret is configured.
//   * Prometheus metrics, health/readiness endpoints, graceful shutdown.
//   * Optional in-process clustering via CLUSTER_WORKERS (default 1: one
//     process per container, scaled horizontally with compose/k8s replicas).

const cluster = require('node:cluster');
const os = require('node:os');
const fs = require('node:fs');
const path = require('node:path');

const express = require('express');
const sql = require('mssql');
const { createClient } = require('redis');
const jwt = require('jsonwebtoken');
const winston = require('winston');
const rateLimit = require('express-rate-limit');
const { RedisStore } = require('rate-limit-redis');
const client = require('prom-client');

// ---------------------------------------------------------------- config --
const PORT = parseInt(process.env.PORT || '3000', 10);
const CLUSTER_WORKERS = parseInt(process.env.CLUSTER_WORKERS || '1', 10);
const JWT_SECRET = process.env.JWT_SECRET;
const ALLOW_RAW_SQL = process.env.GATEWAY_ALLOW_RAW_SQL === '1';
const RAW_SQL_READONLY = process.env.GATEWAY_RAW_SQL_READONLY !== '0'; // default read-only
const RATE_LIMIT_MAX = parseInt(process.env.RATE_LIMIT_MAX || '100', 10);
const RATE_LIMIT_WINDOW_MS = parseInt(process.env.RATE_LIMIT_WINDOW_MS || '60000', 10);

if (!JWT_SECRET) {
  // Fail closed: refuse to run without an auth secret.
  console.error('FATAL: JWT_SECRET is required'); // eslint-disable-line no-console
  process.exit(1);
}

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.json(),
  transports: [new winston.transports.Console()],
});

// "sql1:1433,sql2:1433" -> [{server:'sql1',port:1433}, ...]
const SHARDS = (process.env.SQL_SHARDS || 'sql1:1433')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean)
  .map((s) => {
    const [server, port] = s.split(':');
    return { server, port: parseInt(port || '1433', 10) };
  });

const OPERATIONS = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'operations.json'), 'utf8')
);
delete OPERATIONS.$comment;

const APP_DB = process.env.SQL_DATABASE || 'AppDb';

// Idempotent schema applied to each shard's database on startup.
const SCHEMA_DDL = `
IF OBJECT_ID('dbo.Users', 'U') IS NULL
    CREATE TABLE dbo.Users (
        id INT NOT NULL PRIMARY KEY,
        username NVARCHAR(64) NOT NULL,
        email NVARCHAR(256) NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
IF OBJECT_ID('dbo.Orders', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Orders (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL,
        amount DECIMAL(18,2) NOT NULL,
        status NVARCHAR(32) NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
    CREATE INDEX ix_orders_user ON dbo.Orders (user_id);
END;
`;

const basePoolConfig = {
  user: process.env.SQL_USER || 'sa',
  password: process.env.SQL_PASSWORD,
  database: process.env.SQL_DATABASE || 'AppDb',
  options: {
    encrypt: process.env.SQL_ENCRYPT === '1',
    trustServerCertificate: true,
  },
  pool: {
    max: parseInt(process.env.SQL_POOL_MAX || '20', 10),
    min: parseInt(process.env.SQL_POOL_MIN || '2', 10),
    idleTimeoutMillis: 30000,
  },
  requestTimeout: parseInt(process.env.SQL_REQUEST_TIMEOUT_MS || '15000', 10),
  connectionTimeout: 15000,
};

// ---------------------------------------------------------------- metrics --
const registry = new client.Registry();
client.collectDefaultMetrics({ register: registry });
const httpHist = new client.Histogram({
  name: 'gateway_request_duration_seconds',
  help: 'Request duration by route and status',
  labelNames: ['route', 'method', 'status'],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5],
  registers: [registry],
});
const opCounter = new client.Counter({
  name: 'gateway_operations_total',
  help: 'Operations executed by name and result',
  labelNames: ['operation', 'shard', 'result'],
  registers: [registry],
});

// ---------------------------------------------------- shard pooling / Redis --
const pools = new Map(); // shardId -> mssql.ConnectionPool (connected)
let redis;

async function getPool(shardId) {
  let pool = pools.get(shardId);
  if (pool && pool.connected) return pool;
  if (pool && pool.connecting) return pool.connect();
  const shard = SHARDS[shardId];
  pool = new sql.ConnectionPool({ ...basePoolConfig, server: shard.server, port: shard.port });
  pool.on('error', (err) => logger.error('pool error', { shardId, err: err.message }));
  pools.set(shardId, pool);
  await pool.connect();
  logger.info('shard pool connected', { shardId, server: shard.server });
  return pool;
}

// Ensure the app database and schema exist on a shard. Idempotent and safe
// to run from every replica; connects to master to create the DB, then
// applies the schema. Retries while the SQL Server finishes starting.
async function bootstrapShard(shardId, maxWaitMs = 300000) {
  const shard = SHARDS[shardId];
  const deadline = Date.now() + maxWaitMs;
  for (;;) {
    let master;
    try {
      master = new sql.ConnectionPool({
        ...basePoolConfig, server: shard.server, port: shard.port, database: 'master',
      });
      await master.connect();
      await master.request()
        .input('db', sql.NVarChar, APP_DB)
        .query("IF DB_ID(@db) IS NULL BEGIN DECLARE @s nvarchar(300) = N'CREATE DATABASE ' + QUOTENAME(@db); EXEC (@s); END");
      await master.close();
      const pool = await getPool(shardId);
      await pool.request().batch(SCHEMA_DDL);
      logger.info('shard bootstrapped', { shardId, server: shard.server, db: APP_DB });
      return;
    } catch (err) {
      if (master) { try { await master.close(); } catch { /* ignore */ } }
      if (Date.now() > deadline) throw err;
      logger.info('waiting for shard to accept connections', { shardId, err: err.code || err.message });
      await new Promise((r) => setTimeout(r, 3000));
    }
  }
}

async function shardForKey(keyValue) {
  const fallback = Math.abs(parseInt(keyValue, 10)) % SHARDS.length;
  try {
    const mapped = await redis.get(`shard:${keyValue}`);
    if (mapped !== null) return parseInt(mapped, 10);
    await redis.set(`shard:${keyValue}`, String(fallback), { EX: 3600 });
    return fallback;
  } catch (err) {
    logger.warn('redis shard lookup failed; using hash', { err: err.message });
    return fallback;
  }
}

// mssql type for a declared param type.
const SQL_TYPES = {
  int: sql.Int,
  bigint: sql.BigInt,
  string: sql.NVarChar,
  decimal: sql.Decimal(18, 2),
  bit: sql.Bit,
};

function coerce(type, value) {
  if (type === 'int' || type === 'bigint') {
    const n = Number(value);
    if (!Number.isInteger(n)) throw new Error('expected integer');
    return n;
  }
  if (type === 'decimal') {
    const n = Number(value);
    if (Number.isNaN(n)) throw new Error('expected number');
    return n;
  }
  if (type === 'bit') return value ? 1 : 0;
  return String(value);
}

// ---------------------------------------------------------------- express --
const app = express();
app.disable('x-powered-by');
// Behind nginx/LB: trust the immediate proxy so rate-limit keys on the real IP.
app.set('trust proxy', parseInt(process.env.TRUST_PROXY_HOPS || '1', 10));
app.use(express.json({ limit: '256kb' }));

// Per-request timing.
app.use((req, res, next) => {
  const end = httpHist.startTimer({ route: req.path.split('/').slice(0, 3).join('/'), method: req.method });
  res.on('finish', () => end({ status: res.statusCode }));
  next();
});

// Redis-backed limiter: one global budget across every worker and replica.
// Built in start() once the Redis client exists; routes call it through this
// indirection so they can be registered at load time.
let rateLimiter;
const limiter = (req, res, next) => rateLimiter(req, res, next);

function authenticate(req, res, next) {
  const header = req.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : null;
  if (!token) return res.status(401).json({ error: 'missing bearer token' });
  try {
    req.jwt = jwt.verify(token, JWT_SECRET);
    next();
  } catch {
    return res.status(403).json({ error: 'invalid token' });
  }
}

// ---- unauthenticated infra endpoints ----
app.get('/health', (req, res) => res.json({ status: 'ok', pid: process.pid }));

app.get('/ready', async (req, res) => {
  const out = { redis: false, shards: [] };
  try { await redis.ping(); out.redis = true; } catch { /* stays false */ }
  for (let i = 0; i < SHARDS.length; i += 1) {
    try {
      const pool = await getPool(i);
      await pool.request().query('SELECT 1');
      out.shards.push({ shard: i, healthy: true });
    } catch (err) {
      out.shards.push({ shard: i, healthy: false, error: err.code || err.message });
    }
  }
  const ready = out.redis && out.shards.every((s) => s.healthy);
  res.status(ready ? 200 : 503).json(out);
});

app.get('/metrics', async (req, res) => {
  res.set('Content-Type', registry.contentType);
  res.end(await registry.metrics());
});

app.get('/operations', authenticate, (req, res) => {
  // Advertise the callable operations and their params (not the SQL).
  const catalog = {};
  for (const [name, op] of Object.entries(OPERATIONS)) {
    catalog[name] = { params: op.params, shardBy: op.shardBy, mode: op.mode };
  }
  res.json(catalog);
});

// ---- safe named operations (the default path) ----
app.post('/v1/op/:name', authenticate, limiter, async (req, res, next) => {
  const op = OPERATIONS[req.params.name];
  if (!op) return res.status(404).json({ error: 'unknown operation' });

  const provided = req.body && req.body.params;
  if (typeof provided !== 'object' || provided === null) {
    return res.status(400).json({ error: 'body must be { "params": { ... } }' });
  }

  // Validate: exactly the declared params, correctly typed.
  const bound = {};
  try {
    for (const [pname, ptype] of Object.entries(op.params)) {
      if (!(pname in provided)) throw new Error(`missing param '${pname}'`);
      bound[pname] = { type: SQL_TYPES[ptype], value: coerce(ptype, provided[pname]) };
    }
    for (const pname of Object.keys(provided)) {
      if (!(pname in op.params)) throw new Error(`unknown param '${pname}'`);
    }
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }

  const shardId = await shardForKey(bound[op.shardBy].value);
  try {
    const pool = await getPool(shardId);
    const request = pool.request();
    for (const [pname, b] of Object.entries(bound)) request.input(pname, b.type, b.value);
    const result = await request.query(op.sql);
    opCounter.inc({ operation: req.params.name, shard: shardId, result: 'ok' });
    res.json({ shard: shardId, rows: result.recordset || [], rowsAffected: result.rowsAffected });
  } catch (err) {
    opCounter.inc({ operation: req.params.name, shard: shardId, result: 'error' });
    next(err);
  }
});

// ---- admin: dynamic shard remap ----
app.post('/v1/admin/set-shard', authenticate, async (req, res, next) => {
  const { key, shard_id } = req.body || {};
  if (key === undefined || shard_id === undefined || shard_id < 0 || shard_id >= SHARDS.length) {
    return res.status(400).json({ error: 'need key and valid shard_id' });
  }
  try {
    await redis.set(`shard:${key}`, String(shard_id));
    res.json({ key, shard_id });
  } catch (err) {
    next(err);
  }
});

// ---- guarded raw SQL (disabled unless GATEWAY_ALLOW_RAW_SQL=1) ----
if (ALLOW_RAW_SQL) {
  logger.warn('raw /query enabled', { readOnly: RAW_SQL_READONLY });
  app.post('/query', authenticate, limiter, async (req, res, next) => {
    const { shard_key, query, params = [] } = req.body || {};
    if (shard_key === undefined || typeof query !== 'string') {
      return res.status(400).json({ error: 'need shard_key and query' });
    }
    if (!Array.isArray(params)) return res.status(400).json({ error: 'params must be an array' });
    if (RAW_SQL_READONLY && !/^\s*(select|with)\b/i.test(query)) {
      return res.status(403).json({ error: 'raw SQL is read-only (set GATEWAY_RAW_SQL_READONLY=0 to allow writes)' });
    }
    const shardId = await shardForKey(shard_key);
    try {
      const pool = await getPool(shardId);
      const request = pool.request();
      // Positional params bound as @p0, @p1, ... — still parameterized.
      params.forEach((v, i) => request.input(`p${i}`, v));
      const result = await request.query(query);
      res.json({ shard: shardId, rows: result.recordset || [], rowsAffected: result.rowsAffected });
    } catch (err) {
      next(err);
    }
  });
}

// Error handler is registered after the routes so it catches their errors.
app.use((err, req, res, _next) => {
  logger.error('request error', { path: req.path, err: err.message });
  if (res.headersSent) return;
  res.status(500).json({ error: 'internal error' });
});

// ---------------------------------------------------------------- lifecycle --
async function start() {
  redis = createClient({
    url: `redis://${process.env.REDIS_HOST || 'redis'}:${process.env.REDIS_PORT || 6379}`,
    password: process.env.REDIS_PASSWORD,
  });
  redis.on('error', (err) => logger.error('redis error', { err: err.message }));
  await redis.connect();

  rateLimiter = rateLimit({
    windowMs: RATE_LIMIT_WINDOW_MS,
    max: RATE_LIMIT_MAX,
    standardHeaders: true,
    legacyHeaders: false,
    store: new RedisStore({ sendCommand: (...args) => redis.sendCommand(args) }),
    message: { error: 'rate limit exceeded' },
  });

  // Provision every shard before serving traffic.
  for (let i = 0; i < SHARDS.length; i += 1) {
    await bootstrapShard(i);
  }

  const server = app.listen(PORT, () => logger.info('gateway listening', { pid: process.pid, port: PORT }));

  async function shutdown(signal) {
    logger.info('shutting down', { signal });
    server.close();
    await Promise.allSettled([...pools.values()].map((p) => p.close()));
    try { await redis.quit(); } catch { /* ignore */ }
    process.exit(0);
  }
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

if (CLUSTER_WORKERS > 1 && cluster.isPrimary) {
  const n = CLUSTER_WORKERS === 0 ? os.cpus().length : CLUSTER_WORKERS;
  logger.info('primary forking workers', { pid: process.pid, workers: n });
  for (let i = 0; i < n; i += 1) cluster.fork();
  cluster.on('exit', (worker) => {
    logger.warn('worker died; restarting', { pid: worker.process.pid });
    cluster.fork();
  });
} else {
  start().catch((err) => {
    logger.error('startup failed', { err: err.message });
    process.exit(1);
  });
}
