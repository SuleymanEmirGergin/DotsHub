// k6 peak-burst test — 100 RPS for 60 seconds after a 5-minute steady
// preheat. Models the worst-case: 5 hospital branches all opening
// their morning queue at 08:00.
//
// Run:
//   k6 run -e BASE_URL=https://triaige-staging.fly.dev \
//          -e BYPASS_TOKEN=$STAGING_RL_BYPASS \
//          tests/load/03_burst.js
//
// Targets:
//   p95 latency during burst < 3000 ms
//   error rate < 1%
//   no rate-limit thrash (denied < 5% of bursted requests)

import http from 'k6/http';
import { check } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

const errorRate = new Rate('triage_errors');
const burstLatency = new Trend('burst_latency_ms', true);
const rateLimitDenied = new Counter('rate_limit_denied');

const BASE_URL = __ENV.BASE_URL || 'https://triaige-staging.fly.dev';
const BYPASS_TOKEN = __ENV.BYPASS_TOKEN || '';

export const options = {
  scenarios: {
    preheat: {
      executor: 'constant-arrival-rate',
      rate: 5,
      timeUnit: '1s',
      duration: '5m',
      preAllocatedVUs: 20,
      maxVUs: 50,
      tags: { phase: 'preheat' },
    },
    burst: {
      executor: 'constant-arrival-rate',
      rate: 100,
      timeUnit: '1s',
      duration: '60s',
      preAllocatedVUs: 100,
      maxVUs: 200,
      startTime: '5m',
      tags: { phase: 'burst' },
    },
  },
  thresholds: {
    'triage_errors{phase:burst}': ['rate<0.01'],
    'http_req_duration{phase:burst}': ['p(95)<3000', 'p(99)<5000'],
    'rate_limit_denied': ['count<300'], // < 5% of 6000 burst requests
  },
};

const FIXTURES = [
  'baş ağrım var',
  'karnımda ağrı',
  'göğüs sıkışması',
  'mide bulantısı',
  'ateşim var 38',
  'nefes darlığı',
  'baş dönmesi',
  'kusma',
];

function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

export default function () {
  const headers = {
    'Content-Type': 'application/json',
    'X-Client-Capabilities': 'envelope_v2',
  };
  if (BYPASS_TOKEN) headers['X-Rate-Limit-Bypass'] = BYPASS_TOKEN;

  const res = http.post(
    `${BASE_URL}/v1/triage/turn`,
    JSON.stringify({ text: pick(FIXTURES), session_id: uuidv4() }),
    { headers },
  );

  const ok = check(res, {
    'status < 500': (r) => r.status < 500,
  });
  if (res.status === 429) rateLimitDenied.add(1);
  errorRate.add(!ok);
  burstLatency.add(res.timings.duration);
}

export function handleSummary(data) {
  return {
    'tests/load/results/03_burst_summary.json': JSON.stringify(data, null, 2),
    stdout: '\n03_burst complete — see tests/load/results/03_burst_summary.json\n',
  };
}
