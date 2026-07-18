// Write-heavy k6 profile for the shard-scaling benchmark. Every iteration is
// an INSERT (create_order) spread across a wide owner range so writes land on
// all shards. Isolating writes makes the SQL tier — not reads from cache — the
// thing under pressure, so the effect of adding a shard is visible.
//
// Env: BASE, TOKEN, VUS (default 80), DURATION (default 20s), OWNERS (default 400)
import http from 'k6/http';
import { check } from 'k6';
import { Rate } from 'k6/metrics';

const BASE = __ENV.BASE || 'http://api-gateway:3000';
const TOKEN = __ENV.TOKEN;
const VUS = parseInt(__ENV.VUS || '80', 10);
const DURATION = __ENV.DURATION || '20s';
const OWNERS = parseInt(__ENV.OWNERS || '400', 10);

const errors = new Rate('op_errors');
const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}` };

export const options = {
  scenarios: {
    write: {
      executor: 'constant-vus',
      vus: VUS,
      duration: DURATION,
    },
  },
  thresholds: { http_req_failed: ['rate<0.02'] },
};

export function setup() {
  if (!TOKEN) throw new Error('TOKEN env is required');
  for (let id = 1; id <= OWNERS; id += 1) {
    http.post(`${BASE}/v1/op/create_user`, JSON.stringify({
      params: { id, username: `u${id}`, email: `u${id}@bench.test` },
    }), { headers });
  }
}

export default function () {
  const owner = 1 + Math.floor(Math.random() * OWNERS);
  const res = http.post(`${BASE}/v1/op/create_order`, JSON.stringify({
    params: { user_id: owner, amount: 9.99, status: 'paid' },
  }), { headers });
  errors.add(!check(res, { 'create_order 2xx': (r) => r.status === 200 }));
}
