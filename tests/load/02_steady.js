// k6 steady-state test — 10 concurrent VUs, ramp 5min → hold 15min →
// ramp-down 5min. Models a normal pilot-day load profile.
//
// Run:
//   k6 run -e BASE_URL=https://triaige-staging.fly.dev \
//          -e BYPASS_TOKEN=$STAGING_RL_BYPASS \
//          tests/load/02_steady.js
//
// Targets:
//   p95 latency < 1500 ms
//   error rate  < 0.5%
//   no per-IP rate-limit denials (using bypass token)

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

const errorRate = new Rate('triage_errors');
const triageLatency = new Trend('triage_latency_ms', true);
const rateLimitDenied = new Counter('rate_limit_denied');

const BASE_URL = __ENV.BASE_URL || 'https://triaige-staging.fly.dev';
const BYPASS_TOKEN = __ENV.BYPASS_TOKEN || '';

export const options = {
  stages: [
    { duration: '5m', target: 10 },   // ramp-up
    { duration: '15m', target: 10 },  // hold steady
    { duration: '5m', target: 0 },    // ramp-down
  ],
  thresholds: {
    'triage_errors': ['rate<0.005'],
    'http_req_duration{name:triage}': ['p(95)<1500', 'p(99)<3000'],
    'rate_limit_denied': ['count<10'],
  },
};

// Multi-turn flow — model a real session. Each VU runs through 4
// turns, randomized phrase order, then starts a new session.
const TURN_FIXTURES = [
  ['baş ağrım var', 'iki gündür sürüyor', '7 üzerinden 6 şiddetinde', 'mide bulantısı yok'],
  ['karnımda ağrı', 'sabahtan beri', 'kusma yok', 'ateş yok'],
  ['boğazım ağrıyor', 'üç gün önce başladı', 'ateş 37.8', 'yutkunurken acıyor'],
  ['nefesim daralıyor', 'merdiven çıkarken', 'göğüs ağrısı yok', 'sigara içiyorum'],
  ['sırtımda ağrı', 'bir hafta önce ağırlık kaldırdım', 'kola vurmuyor', 'ateş yok'],
];

function pickFixture() {
  return TURN_FIXTURES[Math.floor(Math.random() * TURN_FIXTURES.length)];
}

export default function () {
  const sessionId = uuidv4();
  const turns = pickFixture();
  const headers = {
    'Content-Type': 'application/json',
    'X-Client-Capabilities': 'envelope_v2,facility_discovery',
  };
  if (BYPASS_TOKEN) headers['X-Rate-Limit-Bypass'] = BYPASS_TOKEN;

  for (const text of turns) {
    const res = http.post(
      `${BASE_URL}/v1/triage/turn`,
      JSON.stringify({ text, session_id: sessionId }),
      { headers, tags: { name: 'triage' } },
    );

    const ok = check(res, {
      'status < 500': (r) => r.status < 500,
      'has body': (r) => r.body && r.body.length > 0,
    });
    if (res.status === 429) rateLimitDenied.add(1);

    errorRate.add(!ok);
    triageLatency.add(res.timings.duration);

    // Realistic inter-turn pause — patient reads + types.
    sleep(Math.random() * 3 + 2); // 2-5s
  }
}

export function handleSummary(data) {
  return {
    'tests/load/results/02_steady_summary.json': JSON.stringify(data, null, 2),
    stdout: '\n02_steady complete — see tests/load/results/02_steady_summary.json\n',
  };
}
