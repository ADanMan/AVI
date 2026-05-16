# Performance Tests for AVI

Load testing and performance benchmarking for AVI API.

## Tools

We use **k6** for load testing - a modern, developer-friendly load testing tool.

### Installation

```bash
# macOS
brew install k6

# Ubuntu/Debian
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6

# Windows (Chocolatey)
choco install k6

# Docker
docker pull grafana/k6
```

## Running Tests

### Basic Load Test

```bash
# Run load test
k6 run tests/performance/load_test.js

# With custom API URL
API_URL=http://your-api:8000 k6 run tests/performance/load_test.js

# Using Docker
docker run -i grafana/k6 run - <tests/performance/load_test.js
```

### Advanced Options

```bash
# Run with specific number of VUs and duration
k6 run --vus 50 --duration 30s tests/performance/load_test.js

# Run with stages (ramp-up pattern)
k6 run --stage 1m:10,3m:50,1m:0 tests/performance/load_test.js

# Output results to JSON
k6 run --out json=performance-results.json tests/performance/load_test.js
```

## Test Scenarios

### 1. Load Test (load_test.js)

Simulates gradually increasing load:
- 0-30s: Ramp up to 10 users
- 30s-1m30s: Maintain 10 users
- 1m30s-2m: Ramp up to 50 users
- 2m-3m: Maintain 50 users
- 3m-3m30s: Ramp down to 0

**Thresholds:**
- 95% of requests < 500ms
- Error rate < 10%
- Query duration p(95) < 1000ms

**Endpoints tested:**
- `/health` - Health check
- `/api/v1/query` - Query processing
- `/metrics` - Prometheus metrics

## Interpreting Results

### Key Metrics

```
✓ checks.........................: 95.00% ✓ 950 ✗ 50
  ✓ health status is 200........: 100.00% ✓ 500 ✗ 0
  ✗ query status is 200.........: 90.00% ✓ 450 ✗ 50
█ errors........................: 5.00%
█ http_req_duration.............: avg=245.32ms p(95)=486.21ms
█ iterations....................: 1000
█ vus...........................: 50
```

**Good performance:**
- ✓ checks > 95%
- http_req_duration p(95) < 500ms
- errors < 10%

**Needs improvement:**
- ✗ checks < 90%
- http_req_duration p(95) > 1000ms
- errors > 20%

### HTTP Request Duration

```
http_req_duration
  avg: 245.32ms   (average response time)
  min: 102.45ms   (fastest request)
  med: 231.67ms   (median)
  max: 1.2s       (slowest request)
  p(90): 412.89ms (90% of requests faster than this)
  p(95): 486.21ms (95% of requests faster than this)
```

**Targets:**
- p(50) < 200ms - Most requests are fast
- p(95) < 500ms - Even slow requests are acceptable
- p(99) < 1000ms - Very few slow requests

## Performance Benchmarks

### Expected Performance

| Endpoint | p(50) | p(95) | p(99) | Target RPS |
|----------|-------|-------|-------|------------|
| /health | <50ms | <100ms | <200ms | 1000+ |
| /api/v1/query | <300ms | <800ms | <1500ms | 100+ |
| /api/v1/chat | <500ms | <1200ms | <2000ms | 50+ |
| /metrics | <100ms | <200ms | <300ms | 500+ |

### Load Capacity

| Load Level | VUs | Expected Performance |
|------------|-----|----------------------|
| Light | 1-10 | All endpoints < p(95) targets |
| Medium | 10-50 | Slight degradation acceptable |
| Heavy | 50-100 | Query endpoints may slow |
| Stress | 100+ | Testing limits, errors expected |

## Continuous Benchmarking

### Makefile Integration

Add to your Makefile:

```makefile
perf-test: ## Run performance tests
	@echo "Running k6 load tests..."
	k6 run tests/performance/load_test.js

perf-test-quick: ## Quick performance test (30s)
	k6 run --vus 10 --duration 30s tests/performance/load_test.js

perf-test-stress: ## Stress test (high load)
	k6 run --vus 100 --duration 2m tests/performance/load_test.js
```

### CI/CD Integration

Add to `.github/workflows/performance.yml`:

```yaml
name: Performance Tests

on:
  schedule:
    - cron: '0 3 * * 0'  # Weekly on Sunday
  workflow_dispatch:

jobs:
  performance:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Start services
        run: docker-compose up -d

      - name: Wait for API
        run: sleep 30

      - name: Install k6
        run: |
          sudo gpg -k
          sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
          echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
          sudo apt-get update
          sudo apt-get install k6

      - name: Run load tests
        run: k6 run tests/performance/load_test.js

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: performance-results
          path: performance-results/
```

## Monitoring During Tests

### Watch Metrics

```bash
# In one terminal
docker-compose up

# In another terminal
watch -n 1 'curl -s http://localhost:8000/metrics | grep http_request'

# Or use Grafana
open http://localhost:3000
```

### System Resources

```bash
# Monitor Docker containers
docker stats

# Monitor specific container
docker stats avi_api
```

## Optimization Tips

### If Response Times Are High

1. **Check Database Queries**
   - Add indexes
   - Optimize slow queries
   - Use connection pooling

2. **Enable Caching**
   - Redis for frequently accessed data
   - In-memory caching for static data

3. **Optimize Code**
   - Profile slow functions
   - Reduce unnecessary computations
   - Use async/await properly

4. **Scale Horizontally**
   - Add more API instances
   - Use load balancer
   - Distribute traffic

### If Error Rate Is High

1. **Check Logs**
   ```bash
   docker-compose logs api --tail=100 -f
   ```

2. **Common Issues**
   - Rate limiting too aggressive
   - Database connection limits
   - Memory exhaustion
   - Timeout configurations

3. **Adjust Limits**
   - Increase connection pool size
   - Adjust timeout values
   - Configure rate limits appropriately

## Grafana k6 Integration

For advanced monitoring, integrate with Grafana:

```bash
# Run k6 with InfluxDB output
k6 run --out influxdb=http://localhost:8086/k6 tests/performance/load_test.js

# Or with Prometheus
k6 run --out prometheus tests/performance/load_test.js
```

## Best Practices

1. **Baseline First** - Establish performance baseline before changes
2. **Test Regularly** - Run weekly or after major changes
3. **Monitor Trends** - Track performance over time
4. **Test Realistic Scenarios** - Use real user patterns
5. **Include Ramp-Up** - Don't slam services with instant load
6. **Test Different Loads** - Light, medium, heavy, and stress
7. **Monitor Resources** - Watch CPU, memory, network during tests
8. **Document Results** - Keep history of performance tests

## Troubleshooting

### k6 Not Found

```bash
# Verify installation
k6 version

# Reinstall if needed (macOS)
brew reinstall k6
```

### Connection Refused

```bash
# Check if API is running
curl http://localhost:8000/health

# Check Docker services
docker-compose ps

# Restart services
docker-compose restart api
```

### Out of Memory Errors

```bash
# Reduce VUs
k6 run --vus 10 --duration 1m tests/performance/load_test.js

# Increase Docker memory limit
# Edit docker-compose.yml and add memory limits
```

## Resources

- [k6 Documentation](https://k6.io/docs/)
- [k6 Examples](https://k6.io/docs/examples/)
- [Performance Testing Best Practices](https://k6.io/docs/testing-guides/test-types/)
- [k6 Cloud](https://k6.io/cloud/) - For distributed testing

---

**Last Updated:** 2025-11-15
