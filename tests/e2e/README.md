# E2E Tests for AVI

End-to-end tests that verify the complete functionality of AVI from user request to response.

## Prerequisites

- Docker and docker-compose installed
- AVI services running (`docker-compose up`)

## Running E2E Tests

### Start Services

```bash
# Start all services
docker-compose up -d

# Wait for services to be ready
docker-compose ps
curl http://localhost:8000/health
```

### Run Tests

```bash
# Run all E2E tests
pytest tests/e2e -v

# Run specific test file
pytest tests/e2e/test_health_check.py -v

# Run with markers
pytest tests/e2e -m "not skip" -v

# Run and show output
pytest tests/e2e -v -s
```

### From Makefile

```bash
# Add to Makefile
make test-e2e
```

## Test Structure

```
tests/e2e/
├── __init__.py
├── conftest.py           # Pytest fixtures and configuration
├── test_health_check.py  # Health and status endpoints
├── test_api_workflow.py  # Full API workflows
└── README.md            # This file
```

## Writing E2E Tests

### Test Template

```python
import pytest

class TestFeature:
    """Test feature end-to-end"""

    def test_feature_workflow(self, api_client, api_base_url):
        """Test complete feature workflow"""
        # 1. Setup
        payload = {"key": "value"}

        # 2. Execute
        response = api_client.post(
            f"{api_base_url}/api/v1/endpoint",
            json=payload
        )

        # 3. Verify
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
```

### Available Fixtures

- `api_base_url` - Base URL for API (http://localhost:8000)
- `api_client` - Requests session with headers
- `wait_for_api` - Waits for API to be ready

### Using Markers

```python
@pytest.mark.skip(reason="Endpoint not yet implemented")
def test_future_feature():
    pass

@pytest.mark.slow
def test_long_running():
    pass
```

## Test Coverage

Current E2E test coverage:

- ✅ Health check endpoints
- ✅ Metrics endpoints
- ✅ Error handling
- ✅ CORS headers
- ⏳ Query processing (placeholder)
- ⏳ Chat endpoints (skipped - not implemented)
- ⏳ Settings endpoints (skipped - not implemented)
- ⏳ Rate limiting (skipped - conditional)

## Adding New Tests

1. Create test file in `tests/e2e/`
2. Import necessary fixtures
3. Write test class with descriptive methods
4. Run tests to verify
5. Update this README

## CI/CD Integration

E2E tests run in GitHub Actions workflow:

```yaml
# .github/workflows/e2e.yml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Start services
        run: docker-compose up -d
      - name: Run E2E tests
        run: pytest tests/e2e -v
```

## Troubleshooting

### Services Not Ready

```bash
# Check service health
docker-compose ps
docker-compose logs api

# Restart services
docker-compose down
docker-compose up -d
```

### Tests Failing Locally

```bash
# Clear old data
docker-compose down -v
docker-compose up -d

# Check network
curl http://localhost:8000/health
```

### Timeouts

Increase timeout in `conftest.py`:

```python
max_retries = 60  # Wait up to 2 minutes
```

## Best Practices

1. **Test Real Workflows** - Test what users actually do
2. **Use Fixtures** - Reuse setup code via fixtures
3. **Be Explicit** - Clear test names and assertions
4. **Handle Not Implemented** - Use `@pytest.mark.skip` for future features
5. **Clean Up** - Ensure tests don't leave artifacts
6. **Test Errors** - Verify error handling, not just happy path

## Future Enhancements

- [ ] Add authentication flow tests
- [ ] Test file upload workflows
- [ ] Test streaming responses
- [ ] Add performance benchmarks
- [ ] Test database interactions
- [ ] Add UI E2E tests (Playwright/Selenium)
