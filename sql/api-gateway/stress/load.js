// k6 load profile for the SQL gateway.
//
// Drives a realistic mix of read and write operations across many owners
// (spread over both shards) and asserts the pooled gateway holds up: high
// throughput, low error rate, bounded latency. Rate limiting is expected to
// be raised for the run (see run-stress.sh), so 429s are treated as failures.
//
// Env:
//   BASE   gateway base URL (default http://api-gateway:3000)
//   TOKEN  bearer token (required)
//   VUS    virtual users (default 50)
//   DURATION  test duration (default 30s)
import http from 'k6/http';
import { check } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const BASE = __ENV.BASE || 'http://api-gateway:3000';
const TOKEN = __ENV.TOKEN;
const VUS = parseInt(__ENV.VUS || '50', 10);
const DURATION = __ENV.DURATION || '30s';

const opErrors = new Rate('op_errors');
const opLatency = new Trend('op_latency_ms', true);

export const options = {
  scenarios: {
    ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '5s', target: VUS },
        { duration: DURATION, target: VUS },
        { duration: '5s', target: 0 },
      ],
      gracefulRampDown: '5s',
    },
  },
  thresholds: {
    // The gateway must stay fast and correct under load.
    http_req_failed: ['rate<0.01'],
    op_errors: ['rate<0.01'],
    http_req_duration: ['p(95)<500', 'p(99)<1500'],
  },
};

const headers = {
  'Content-Type': 'application/json',
  Authorization: `Bearer ${TOKEN}`,
};

function post(op, params) {
  const res = http.post(`${BASE}/v1/op/${op}`, JSON.stringify({ params }), { headers });
  opLatency.add(res.timings.duration);
  const ok = check(res, { [`${op} 2xx`]: (r) => r.status === 200 });
  opErrors.add(!ok);
  return res;
}

export function setup() {
  if (!TOKEN) throw new Error('TOKEN env is required');
  // Seed a pool of owners spread across both shards.
  for (let id = 1; id <= 200; id += 1) {
    http.post(`${BASE}/v1/op/create_user`, JSON.stringify({
      params: { id, username: `u${id}`, email: `u${id}@load.test` },
    }), { headers });
  }
}

export default function () {
  // Random owner -> mix of shards; 80% reads, 20% writes.
  const owner = 1 + Math.floor(Math.random() * 200);
  const roll = Math.random();
  if (roll < 0.6) {
    post('get_user', { id: owner });
  } else if (roll < 0.8) {
    post('list_orders', { user_id: owner, limit: 10, offset: 0 });
  } else {
    post('create_order', { user_id: owner, amount: 9.99, status: 'paid' });
  }
}
