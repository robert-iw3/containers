// Mint a short-lived JWT for calling the gateway.
//   JWT_SECRET=... node mint-token.js [subject] [ttl-seconds]
// In the running container:
//   docker compose exec api-gateway node mint-token.js app 3600
const jwt = require('jsonwebtoken');

const secret = process.env.JWT_SECRET;
if (!secret) {
  console.error('JWT_SECRET is required'); // eslint-disable-line no-console
  process.exit(1);
}
const sub = process.argv[2] || 'app';
const ttl = parseInt(process.argv[3] || '3600', 10);
process.stdout.write(jwt.sign({ sub }, secret, { expiresIn: ttl }) + '\n');
