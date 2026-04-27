// k6 sustained-heavy test — 50 RPS for 30 minutes. Hunts memory
// leaks, slow Supabase queries that compound, and per-machine
// resource exhaustion that does not show in shorter tests.
//
// Run:
//   k6 run -e BASE_URL=https://triaige-staging.fly.dev \
//          -e BYPASS_TOKEN=$STAGING_RL_BYPASS \
//          tests/load/04_sustained.js
//
// During the run, watch (in a second terminal):
//   flyctl logs --app triaige-staging-backend
//   flyctl status --app triaige-staging-backend  # mem trend
//   Grafana dashboard "Backend overview" — heap, p99 latency drift
//
// Targets:
//   no upward p99 drift over the 30-min window (drift > 20% = fail)
//   error rate < 0.5% sustained
//   no machine restarts (Fly health check drops)

import http from 'k6/http';
import { check } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

const errorRate = new Rate('triage_errors');
const sustainedLatency = new Trend('sustained_latency_ms', true);

const BASE_URL = __ENV.BASE_URL || 'https://triaige-staging.fly.dev';
const BYPASS_TOKEN = __ENV.BYPASS_TOKEN || '';

export const options = {
  scenarios: {
    sustained: {
      executor: 'constant-arrival-rate',
      rate: 50,
      timeUnit: '1s',
      duration: '30m',
      preAllocatedVUs: 50,
      maxVUs: 150,
    },
  },
  thresholds: {
    'triage_errors': ['rate<0.005'],
    'http_req_duration': ['p(95)<2000', 'p(99)<4000'],
  },
};

// Larger fixture pool to spread Supabase write patterns; each session
// is one row in triage_sessions, so 30 min × 50 RPS × ~1 turn = 90k
// rows. Keep staging Supabase project on a paid plan if running this
// often, or truncate triage_sessions before each run.
const FIXTURES = [
  'baş ağrım var iki gündür', 'karnımda hafif sancı sabahtan beri',
  'göğsüm sıkışıyor', 'midem bulanıyor', 'boğazım çok ağrıyor',
  'ateşim 38 derece var', 'sırtımda ağrı', 'baş dönmem var',
  'nefesim daralıyor', 'kusma var', 'idrar yanması',
  'göz kızarıklığı', 'kulak ağrısı', 'diş ağrısı çekiyorum',
  'sürekli yorgunum', 'eklemlerim ağrıyor sabahları',
];

function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

export default function () {
  const headers = {
    'Content-Type': 'application/json',
    'X-Client-Capabilities': 'envelope_v2,facility_discovery',
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
  errorRate.add(!ok);
  sustainedLatency.add(res.timings.duration);
}

export function handleSummary(data) {
  return {
    'tests/load/results/04_sustained_summary.json': JSON.stringify(data, null, 2),
    stdout: '\n04_sustained complete — see tests/load/results/04_sustained_summary.json\n',
  };
}
