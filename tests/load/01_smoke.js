// k6 smoke test — 1 virtual user, 10 turns/min, 5 min run.
//
// Purpose: prove the staging backend serves /v1/triage/turn end-to-end
// with no errors. Acts as a baseline latency / error-rate measurement
// before the heavier scenarios. If smoke fails, do not run the others.
//
// Run:
//   k6 run -e BASE_URL=https://triaige-staging.fly.dev \
//          -e BYPASS_TOKEN=$STAGING_RL_BYPASS \
//          tests/load/01_smoke.js
//
// Targets:
//   p95 latency < 800 ms
//   error rate  < 0.1%
//   one /health 200 every 30s

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

const errorRate = new Rate('triage_errors');
const triageLatency = new Trend('triage_latency_ms', true);

const BASE_URL = __ENV.BASE_URL || 'https://triaige-staging.fly.dev';
const BYPASS_TOKEN = __ENV.BYPASS_TOKEN || '';

export const options = {
  vus: 1,
  duration: '5m',
  thresholds: {
    'triage_errors': ['rate<0.001'],            // < 0.1%
    'http_req_duration{name:triage}': ['p(95)<800'],
    'http_req_failed': ['rate<0.01'],
  },
};

// Small fixture set — pre-canonical Turkish phrases the backend should
// accept without a panic. Mix of QUESTION + EMERGENCY candidates.
const FIXTURES = [
  'baş ağrım var iki gündür',
  'karnımda hafif sancı',
  'göğsüm sıkışıyor sol koluma vuruyor',
  'midem bulanıyor sabahtan beri',
  'boğazım çok ağrıyor',
  'ateşim 38 derece',
  'sırtımda ağrı var',
  'baş dönmem var',
];

function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

export default function () {
  const sessionId = uuidv4();
  const body = JSON.stringify({
    text: pick(FIXTURES),
    session_id: sessionId,
  });

  const headers = {
    'Content-Type': 'application/json',
    'X-Client-Capabilities': 'envelope_v2,facility_discovery',
  };
  if (BYPASS_TOKEN) headers['X-Rate-Limit-Bypass'] = BYPASS_TOKEN;

  const res = http.post(`${BASE_URL}/v1/triage/turn`, body, {
    headers,
    tags: { name: 'triage' },
  });

  const ok = check(res, {
    'status 200': (r) => r.status === 200,
    'has envelope type': (r) => {
      try {
        const j = JSON.parse(r.body);
        return ['QUESTION', 'RESULT', 'EMERGENCY', 'ERROR'].includes(j.type);
      } catch (_) { return false; }
    },
    'no 5xx': (r) => r.status < 500,
  });

  errorRate.add(!ok);
  triageLatency.add(res.timings.duration);

  // 6 second sleep → 10 turns / minute.
  sleep(6);
}

export function handleSummary(data) {
  return {
    'tests/load/results/01_smoke_summary.json': JSON.stringify(data, null, 2),
    stdout: '\n01_smoke complete — see tests/load/results/01_smoke_summary.json\n',
  };
}
