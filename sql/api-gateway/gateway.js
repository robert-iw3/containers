// gateway.js: API Gateway with pooling, error handling, dynamic mapping, auth, rate limiting

const express = require('express');
const sql = require('mssql');
const Redis = require('redis');
const jwt = require('jsonwebtoken');
const winston = require('winston');
const rateLimit = require('express-rate-limit');
const cluster = require('cluster');
const os = require('os');

const app = express();
app.use(express.json());

// Logging
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'error.log', level: 'error' })
  ]
});

// Rate limiting for high traffic
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000,  // 15 minutes
  max: 100,  // Limit each IP to 100 requests per window
  message: 'Too many requests, please try again later.'
});
app.use(limiter);

// Global error handler
app.use((err, req, res, next) => {
  logger.error(err.stack);
  res.status(500).json({ error: 'Internal server error' });
});

// Redis client for dynamic mapping/caching
const redisClient = Redis.createClient({
  url: `redis://${process.env.REDIS_HOST}:${process.env.REDIS_PORT}`
});
redisClient.on('error', err => logger.error('Redis Client Error', err));
(async () => {
  await redisClient.connect();
})();

// Base SQL configs (per shard/container)
const sqlShards = {
  1: {
    server: 'sql1',
    database: 'UserDb1'
  },
  2: {
    server: 'sql2',
    database: 'UserDb2'
  }
  // Dynamically add more via admin API
};

// Connection pooling config (global for efficiency)
const poolConfig = {
  user: process.env.SQL_USER || 'sa',
  password: process.env.SQL_PASSWORD || 'YourStrong!Passw0rd',
  options: { encrypt: false },  // Prod: true
  pool: {
    max: 50,  // Max connections for high volume
    min: 5,   // Min idle
    idleTimeoutMillis: 30000,
    acquireTimeoutMillis: 30000,  // Timeout for acquiring connection
    evictionRunIntervalMillis: 60000  // Check for evictions every minute
  }
};

// Function to get dynamic shard (from Redis; fallback to hash)
async function getShard(userId) {
  try {
    let shard = await redisClient.get(`user_shard:${userId}`);
    if (!shard) {
      shard = (userId % Object.keys(sqlShards).length) + 1;  // Fallback hash
      await redisClient.set(`user_shard:${userId}`, shard, { EX: 3600 });  // Cache 1hr
    }
    return parseInt(shard);
  } catch (err) {
    logger.error('Redis shard fetch error', err);
    return (userId % Object.keys(sqlShards).length) + 1;  // Fallback
  }
}

// Middleware: JWT Auth (for enterprise security)
const authenticate = (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1];
  if (!token) return res.status(401).json({ error: 'No token provided' });
  try {
    jwt.verify(token, process.env.JWT_SECRET || 'your_jwt_secret');
    next();
  } catch (err) {
    res.status(403).json({ error: 'Invalid token' });
  }
};

// API endpoint: /query - With auth, pooling, retries
app.post('/query', authenticate, async (req, res, next) => {
  const { user_id, query, params = [] } = req.body;
  if (!user_id || !query) {
    return res.status(400).json({ error: 'Missing user_id or query' });
  }

  try {
    const shardId = await getShard(user_id);
    const shardConfig = sqlShards[shardId];
    if (!shardConfig) {
      return res.status(404).json({ error: 'No shard for user' });
    }

    const config = { ...poolConfig, ...shardConfig };

    // Retry logic for high volume/resilience
    let attempts = 0;
    while (attempts < 3) {
      try {
        const pool = await sql.connect(config);
        const request = pool.request();
        params.forEach((param, index) => {
          request.input(`param${index}`, param);
        });
        const result = await request.query(query);
        await pool.close();
        return res.json(result.recordset);
      } catch (err) {
        attempts++;
        logger.warn(`Query retry ${attempts} for user ${user_id}: ${err.message}`);
        if (attempts >= 3) throw err;
        await new Promise(resolve => setTimeout(resolve, 1000 * attempts));  // Exponential backoff
      }
    }
  } catch (err) {
    next(err);
  }
});

// Admin endpoint: /set-shard - To dynamically set user-to-shard (auth protected)
app.post('/set-shard', authenticate, async (req, res) => {
  const { user_id, shard_id } = req.body;
  if (!user_id || !shard_id || !sqlShards[shard_id]) {
    return res.status(400).json({ error: 'Invalid user_id or shard_id' });
  }
  try {
    await redisClient.set(`user_shard:${user_id}`, shard_id);
    res.json({ success: true });
  } catch (err) {
    logger.error('Set shard error', err);
    res.status(500).json({ error: 'Failed to set shard' });
  }
});

// Health check
app.get('/health', (req, res) => res.send('API Gateway running'));

// Clustering for multi-core high traffic
if (cluster.isMaster) {
  const numCPUs = os.cpus().length;
  logger.info(`Master ${process.pid} is running`);
  for (let i = 0; i < numCPUs; i++) {
    cluster.fork();
  }
  cluster.on('exit', (worker, code, signal) => {
    logger.warn(`Worker ${worker.process.pid} died`);
    cluster.fork();
  });
} else {
  app.listen(PORT, () => {
    logger.info(`Worker ${process.pid} listening on port ${PORT}`);
  });
}

const PORT = 3000;