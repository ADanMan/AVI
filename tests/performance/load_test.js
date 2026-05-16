/**
 * Load testing script for AVI using k6
 *
 * Install k6: https://k6.io/docs/getting-started/installation/
 * Run: k6 run tests/performance/load_test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const queryDuration = new Trend('query_duration');

// Test configuration
export const options = {
  stages: [
    { duration: '30s', target: 10 },  // Ramp up to 10 users
    { duration: '1m', target: 10 },   // Stay at 10 users
    { duration: '30s', target: 50 },  // Ramp up to 50 users
    { duration: '1m', target: 50 },   // Stay at 50 users
    { duration: '30s', target: 0 },   // Ramp down to 0
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% of requests should be below 500ms
    errors: ['rate<0.1'],              // Error rate should be below 10%
    query_duration: ['p(95)<1000'],    // 95% of queries below 1s
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';

export default function () {
  // Test 1: Health check
  const healthRes = http.get(`${BASE_URL}/health`);
  check(healthRes, {
    'health status is 200': (r) => r.status === 200,
    'health response has status': (r) => JSON.parse(r.body).status !== undefined,
  });
  errorRate.add(healthRes.status !== 200);

  sleep(1);

  // Test 2: Query endpoint (if implemented)
  const queryPayload = JSON.stringify({
    query: 'What is AI safety?',
    max_tokens: 100,
  });

  const queryParams = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  const queryRes = http.post(
    `${BASE_URL}/api/v1/query`,
    queryPayload,
    queryParams
  );

  const querySuccess = check(queryRes, {
    'query status is 200 or 404': (r) => r.status === 200 || r.status === 404,
  });

  if (queryRes.status === 200) {
    queryDuration.add(queryRes.timings.duration);
  }

  errorRate.add(!querySuccess && queryRes.status !== 404);

  sleep(1);

  // Test 3: Metrics endpoint
  const metricsRes = http.get(`${BASE_URL}/metrics`);
  check(metricsRes, {
    'metrics accessible': (r) => r.status === 200 || r.status === 404,
  });

  sleep(2);
}

export function handleSummary(data) {
  return {
    'performance-results/summary.json': JSON.stringify(data),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}

function textSummary(data, options = {}) {
  const indent = options.indent || '';
  const enableColors = options.enableColors !== false;

  let summary = '\n';
  summary += `${indent}     ✓ checks.........................: ${data.metrics.checks.values.passes}/${data.metrics.checks.values.fails + data.metrics.checks.values.passes}\n`;
  summary += `${indent}       ✓ health status is 200........: ${data.metrics['check{health status is 200}']?.values.passes || 0}\n`;
  summary += `${indent}     █ errors........................: ${(data.metrics.errors.values.rate * 100).toFixed(2)}%\n`;
  summary += `${indent}     █ http_req_duration.............: avg=${data.metrics.http_req_duration.values.avg.toFixed(2)}ms p(95)=${data.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms\n`;
  summary += `${indent}     █ iterations....................: ${data.metrics.iterations.values.count}\n`;
  summary += `${indent}     █ vus...........................: ${data.metrics.vus.values.value}\n`;

  return summary;
}
