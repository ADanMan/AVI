# Production Deployment Checklist

Checklist for deploying AVI to production safely and securely.

## Phase 1: Production Readiness ✅

### Pre-Deployment

- [ ] **Environment Variables**
  - [ ] Set `ENVIRONMENT=production`
  - [ ] Set `DEBUG=false`
  - [ ] Set valid `MAIN_LLM_API_KEY`
  - [ ] Set valid `MAIN_LLM_MODEL`
  - [ ] Ensure `AVI_TEST_MODE` is NOT set or set to `0`
  - [ ] Set `REQUIRE_API_KEY=true` for security

- [ ] **Vector Database**
  - [ ] Configure Qdrant connection (`QDRANT_HOST`, `QDRANT_PORT`)
  - [ ] Or use in-memory/file-based for small deployments
  - [ ] Verify `VECTOR_DB_PROVIDER` is set correctly

- [ ] **API Keys**
  - [ ] Run `python scripts/bootstrap_admin_key.py` to create first admin key
  - [ ] Save the admin key securely (password manager, vault)
  - [ ] Create API keys for applications/users as needed
  - [ ] Configure `AVI_API_KEY` for internal clients (UI, CLI)

- [ ] **Rate Limiting**
  - [ ] Set appropriate rate limits in environment
  - [ ] Optional: Configure Redis for distributed rate limiting
  - [ ] Test rate limiting works as expected

### Validation

- [ ] **Run Startup Validation**
  ```bash
  # Production validation runs automatically on startup
  python main.py
  # Should see: ✅ Production validation passed - all checks OK
  ```

- [ ] **Check Configuration**
  ```bash
  # Verify no test mode
  echo $AVI_TEST_MODE  # Should be empty or 0

  # Verify production environment
  echo $ENVIRONMENT  # Should be "production"

  # Verify API keys are set
  echo $MAIN_LLM_API_KEY | head -c 10  # Should show valid key
  ```

- [ ] **Test Endpoints**
  ```bash
  # Health check (should work without auth)
  curl http://localhost:8000/health

  # Query endpoint (should require auth if REQUIRE_API_KEY=true)
  curl -H "X-API-Key: $AVI_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"query": "test"}' \
    http://localhost:8000/query
  ```

### Security

- [ ] **Authentication**
  - [ ] Confirm `REQUIRE_API_KEY=true` in production
  - [ ] Test endpoints return 401 without API key
  - [ ] Test admin endpoints require admin role
  - [ ] Verify rate limiting is active

- [ ] **Secrets Management**
  - [ ] API keys not in version control
  - [ ] API keys stored in secure location (env vars, vault, secrets manager)
  - [ ] API key storage file (`data/security/api_keys.json`) is in `.gitignore`
  - [ ] LLM API keys stored securely

- [ ] **Network Security**
  - [ ] Use HTTPS in production (reverse proxy)
  - [ ] Configure CORS appropriately
  - [ ] Firewall rules limit access as needed

### Monitoring

- [ ] **Enable Observability**
  - [ ] Prometheus metrics enabled (`PROMETHEUS_ENABLED=true`)
  - [ ] Optional: Configure OpenTelemetry/Jaeger
  - [ ] Set up log aggregation

- [ ] **Health Checks**
  - [ ] Test `/health` endpoint
  - [ ] Configure load balancer health checks
  - [ ] Set up alerting for health check failures

### Data & Storage

- [ ] **Backup Strategy**
  - [ ] Backup vector database
  - [ ] Backup API keys storage
  - [ ] Backup application data
  - [ ] Test restore procedures

- [ ] **Disk Space**
  - [ ] Ensure sufficient space for data directories
  - [ ] Monitor disk usage
  - [ ] Set up alerts for low disk space

### Performance

- [ ] **Load Testing**
  - [ ] Test with expected load
  - [ ] Verify rate limits are appropriate
  - [ ] Check memory and CPU usage
  - [ ] Test concurrent requests

- [ ] **Optimization**
  - [ ] Enable caching (Redis or in-memory)
  - [ ] Configure appropriate timeout values
  - [ ] Optimize vector DB settings for workload

### Content Filtering Configuration

- [ ] **Filter Thresholds** (Phase 3.1)
  - [ ] Set `FILTER_DEFAULT_THRESHOLD` (recommended: 0.60 for production)
  - [ ] Set `FILTER_FALLBACK_THRESHOLD` (recommended: 0.50)
  - [ ] Adjust thresholds based on false positive/negative rates
  - [ ] Test threshold effectiveness with sample queries

- [ ] **Vector Search Settings** (Phase 3.1)
  - [ ] Configure `VECTOR_SEARCH_TOP_K` (default: 10)
  - [ ] Set `VECTOR_SEARCH_SIMILARITY_MIN` (default: 0.3)
  - [ ] Tune based on rule matching performance

- [ ] **RAG Configuration** (Phase 3.1)
  - [ ] Set `RAG_CANDIDATE_COUNT` (default: 5)
  - [ ] Configure `RAG_RELEVANCE_THRESHOLD` (default: 0.5)
  - [ ] Test context retrieval quality

- [ ] **Granular Filter Control** (Phase 2.6)
  - [ ] Configure default `FilteringOptions` for input stage
  - [ ] Configure default `FilteringOptions` for output stage
  - [ ] Test component-level toggles (vector_rules, safety_llm, etc.)
  - [ ] Verify component metrics in `/metrics` endpoint

### Caching Setup

- [ ] **Cache Backend Selection**
  - [ ] Development: Use `CACHE_BACKEND=memory` (default)
  - [ ] Single instance: Either memory or Redis
  - [ ] Multi-instance: **Must use** `CACHE_BACKEND=redis`
  - [ ] Set `CACHE_TTL` (default: 3600 seconds)
  - [ ] Set `CACHE_MAX_SIZE` (default: 10000, for memory fallback)

- [ ] **Redis Configuration** (if using Redis)
  - [ ] Follow [REDIS_SETUP.md](./REDIS_SETUP.md) guide
  - [ ] Set `REDIS_URL` or individual connection parameters
  - [ ] Test Redis connectivity before deployment
  - [ ] Configure Redis persistence (AOF + RDB recommended)
  - [ ] Set `maxmemory` and `maxmemory-policy allkeys-lru`
  - [ ] Enable authentication (`requirepass` or ACL)
  - [ ] Configure SSL/TLS for production
  - [ ] Set up Redis monitoring and alerting
  - [ ] Test failover if using Sentinel/Cluster

### Safety Service Configuration

- [ ] **Safety Mode Selection** (Phase 2.1)
  - [ ] Set `SAFETY_MODE` (options: disabled, llm, remote, hybrid)
  - [ ] Development: Use `disabled` or `llm`
  - [ ] Production: Use `hybrid` for redundancy

- [ ] **Safety LLM** (if SAFETY_MODE=llm or hybrid)
  - [ ] Set `SAFETY_LLM_API_KEY`
  - [ ] Set `SAFETY_LLM_API_BASE`
  - [ ] Set `SAFETY_LLM_MODEL`
  - [ ] Configure `SAFETY_LLM_TEMPERATURE=0.1` (strict)
  - [ ] Test safety rephrasing functionality

- [ ] **Streaming Guard** (Phase 2.5)
  - [ ] Set `STREAM_GUARD_MODE` (options: disabled, vector_only, llm_only, hybrid)
  - [ ] Production recommended: `hybrid`
  - [ ] Test streaming with `/stream` endpoint
  - [ ] Verify buffer size and window behavior
  - [ ] Monitor streaming latency metrics

### Response Streaming

- [ ] **Streaming Configuration** (Phase 2.5)
  - [ ] Test `/stream` endpoint with SSE client
  - [ ] Verify backpressure handling under load
  - [ ] Test connection interruption recovery
  - [ ] Monitor streaming metrics:
    - `avi_stream_requests_total`
    - `avi_stream_tokens_total`
    - `avi_stream_duration_seconds`
  - [ ] Configure client-side timeout appropriately

## Phase 2: Core Services ✅

All Phase 2 tasks completed and deployed:

- [x] **Safety Service Plugin Architecture** (Task 2.1)
  - [x] Modular safety adapter system
  - [x] Support for external, local, and hybrid safety modes
  - [x] Dynamic fallback between safety providers

- [x] **Implement All Endpoints** (Task 2.2)
  - [x] `/stream` - Response streaming with safety guards
  - [x] `/filters/update_threshold` - Update individual rule thresholds
  - [x] `/filters/documents/approve` - Approve document-rule links
  - [x] `/filters/documents/bulk_update` - Bulk link management
  - [x] `/chat/reset` - Session management

- [x] **Threshold Validation** (Task 2.3)
  - [x] Per-rule threshold configuration
  - [x] Automatic threshold validation
  - [x] Fallback to default thresholds

- [x] **Category-Specific Prompts** (Task 2.4)
  - [x] Specialized modification prompts per violation type
  - [x] Context-aware safety rephrasing

- [x] **Response Streaming** (Task 2.5)
  - [x] SSE-based streaming with backpressure
  - [x] Sliding window content filtering
  - [x] Token-by-token safety validation

- [x] **Granular Filter Control** (Task 2.6)
  - [x] `FilteringOptions` for input/output stages
  - [x] Toggle vector rules, safety LLM, prompt modification, output cleaning
  - [x] Component-level metrics and observability

## Phase 3: Configuration & Production Polish ✅

Production readiness improvements:

- [x] **Move Hardcoded Values to Configuration** (Task 3.1)
  - [x] Configurable filter thresholds (default: 0.60, fallback: 0.50)
  - [x] Vector search parameters (top_k: 10, similarity_min: 0.3)
  - [x] RAG retrieval settings (candidate_count: 5, threshold: 0.5)
  - [x] Cache size configuration (max_size: 10000)
  - [x] All values tunable via environment variables

- [x] **Redis Documentation** (Task 3.2)
  - [x] Comprehensive Redis setup guide
  - [x] Docker Compose examples
  - [x] High availability (Sentinel) configuration
  - [x] Horizontal scaling (Cluster) setup
  - [x] Security and performance tuning
  - [x] See [REDIS_SETUP.md](./REDIS_SETUP.md)

- [x] **Deployment Checklist** (Task 3.3)
  - [x] Updated production checklist with Phase 2/3 features
  - [x] New environment variables documented
  - [x] Streaming and filtering configuration
  - [x] Redis cache setup instructions

## Complete Environment Variables Reference

### Essential Configuration

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `ENVIRONMENT` | `development` | ✓ | Set to `production` for production deployments |
| `DEBUG` | `true` | ✓ | Set to `false` in production |
| `APP_NAME` | `AVI_PoC` | ✗ | Application name (used in cache keys, metrics) |

### LLM Configuration

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `MAIN_LLM_API_KEY` | - | ✓ | API key for primary LLM (OpenRouter, OpenAI, etc.) |
| `MAIN_LLM_API_BASE` | `https://openrouter.ai/api/v1` | ✓ | Base URL for LLM API |
| `MAIN_LLM_MODEL` | `openai/gpt-4o-mini` | ✓ | Model identifier |
| `MAIN_LLM_TEMPERATURE` | `0.7` | ✗ | Response temperature (0.0-1.0) |
| `MAIN_LLM_MAX_TOKENS` | `2000` | ✗ | Maximum tokens per response |

### Authentication & Security

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `REQUIRE_API_KEY` | `false` | ✓ | Set to `true` in production |
| `AVI_API_KEY` | - | ✗ | API key for internal clients (UI, CLI) |
| `AVI_API_BASE` | `http://localhost:8000` | ✗ | Base URL for AVI API |

### Safety & Filtering (Phase 2.1, 2.4, 2.6)

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `SAFETY_MODE` | `disabled` | ✗ | Safety backend: `disabled`, `llm`, `remote`, `hybrid` |
| `SAFETY_LLM_API_KEY` | - | ✗ | API key for safety LLM (if SAFETY_MODE=llm/hybrid) |
| `SAFETY_LLM_API_BASE` | - | ✗ | Base URL for safety LLM |
| `SAFETY_LLM_MODEL` | - | ✗ | Safety LLM model identifier |
| `SAFETY_LLM_TEMPERATURE` | `0.1` | ✗ | Temperature for safety responses (strict) |
| `SAFETY_LLM_MAX_TOKENS` | `1000` | ✗ | Max tokens for safety responses |
| `SAFETY_SERVICE_URL` | - | ✗ | External safety microservice URL (if SAFETY_MODE=remote) |
| `SAFETY_SERVICE_TIMEOUT` | `5.0` | ✗ | Timeout for safety service calls (seconds) |

### Streaming Guard (Phase 2.5)

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `STREAM_GUARD_MODE` | `hybrid` | ✗ | Streaming filter: `disabled`, `vector_only`, `llm_only`, `hybrid` |

### Filter Thresholds (Phase 3.1)

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `FILTER_DEFAULT_THRESHOLD` | `0.60` | ✗ | Default relevance threshold for filter rules (0.0-1.0) |
| `FILTER_FALLBACK_THRESHOLD` | `0.50` | ✗ | Fallback threshold when rule-specific unavailable |
| `VECTOR_SEARCH_TOP_K` | `10` | ✗ | Number of similar rules to retrieve (1-100) |
| `VECTOR_SEARCH_SIMILARITY_MIN` | `0.3` | ✗ | Minimum similarity score for matches (0.0-1.0) |

### RAG Configuration (Phase 3.1)

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `RAG_THRESHOLD` | `0.75` | ✗ | Legacy RAG threshold (use RAG_RELEVANCE_THRESHOLD) |
| `RAG_CANDIDATE_COUNT` | `5` | ✗ | Number of documents to retrieve (1-50) |
| `RAG_RELEVANCE_THRESHOLD` | `0.5` | ✗ | Minimum relevance score for documents (0.0-1.0) |

### Caching (Phase 3.1, 3.2)

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `CACHE_BACKEND` | `memory` | ✗ | Cache backend: `memory` or `redis` |
| `CACHE_TTL` | `3600` | ✗ | Cache entry TTL in seconds |
| `CACHE_MAX_SIZE` | `10000` | ✗ | Max items in memory cache (1-1000000) |
| `REDIS_URL` | - | ✗ | Full Redis connection URL (overrides individual params) |
| `REDIS_HOST` | `localhost` | ✗ | Redis server hostname |
| `REDIS_PORT` | `6379` | ✗ | Redis server port |
| `REDIS_DB` | `0` | ✗ | Redis database number (0-15) |
| `REDIS_USERNAME` | - | ✗ | Redis ACL username (Redis 6+) |
| `REDIS_PASSWORD` | - | ✗ | Redis password |

### Vector Database

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `VECTOR_DB_PROVIDER` | `chroma` | ✗ | Vector DB: `chroma` or `qdrant` |
| `VECTOR_DB_PATH` | `./data/indexes/chroma` | ✗ | Path for Chroma database |
| `INDEX_DIMENSION` | `384` | ✗ | Embedding dimension (must match model) |
| `QDRANT_HOST` | - | ✗ | Qdrant server hostname (if using Qdrant) |
| `QDRANT_PORT` | `6333` | ✗ | Qdrant server port |
| `QDRANT_API_KEY` | - | ✗ | Qdrant API key (cloud deployments) |
| `QDRANT_PATH` | `./data/indexes/qdrant` | ✗ | Path for local Qdrant storage |

### Reranker

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `RERANK_ENABLED` | `true` | ✗ | Enable cross-encoder reranking |
| `RERANK_MODEL_NAME` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | ✗ | Reranker model |
| `RERANK_CANDIDATE_COUNT` | `15` | ✗ | Candidates before reranking |
| `RERANK_SCORE_THRESHOLD` | `0.0` | ✗ | Minimum rerank score |
| `RERANK_MAX_LENGTH` | `512` | ✗ | Max sequence length for reranker |

### Monitoring & Observability

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `PROMETHEUS_ENABLED` | `true` | ✗ | Enable Prometheus metrics endpoint |
| `PROMETHEUS_ROUTE` | `/metrics` | ✗ | Metrics endpoint path |
| `METRICS_NAMESPACE` | `avi` | ✗ | Prometheus metrics namespace |
| `CORRELATION_ID_HEADER` | `X-Correlation-ID` | ✗ | Request correlation header name |
| `OTEL_ENABLED` | `false` | ✗ | Enable OpenTelemetry tracing |
| `OTEL_SERVICE_NAME` | `avi-api` | ✗ | Service name for traces |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | - | ✗ | OTLP endpoint for traces |

### Data Directories

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `DATA_DIR` | `./data` | ✗ | Root data directory |
| `RAW_DATA_DIR` | `./data/raw` | ✗ | Raw data storage |
| `PROCESSED_DATA_DIR` | `./data/processed` | ✗ | Processed data storage |
| `INDEXES_DIR` | `./data/indexes` | ✗ | Vector index storage |
| `FEEDBACK_DIR` | `./data/feedback` | ✗ | User feedback storage |

### Experimental Features

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `ENABLE_MLFLOW` | `false` | ✗ | Enable MLflow experiment tracking |
| `MLFLOW_TRACKING_URI` | - | ✗ | MLflow server URI |
| `MLFLOW_EXPERIMENT_NAME` | `content_filter_metrics` | ✗ | Experiment name |
| `ENABLE_WANDB` | `false` | ✗ | Enable Weights & Biases tracking |
| `WANDB_PROJECT` | - | ✗ | W&B project name |
| `WANDB_ENTITY` | - | ✗ | W&B entity/team name |

### Deprecated Variables

| Variable | Replacement | Description |
|----------|-------------|-------------|
| `EXTERNAL_LLM_API_KEY` | `MAIN_LLM_API_KEY` | Legacy alias for main LLM key |
| `OPENROUTER_API_KEY` | `MAIN_LLM_API_KEY` | Legacy OpenRouter-specific key |

## Emergency Procedures

### Lost Admin API Key

```bash
# Create new admin key
python scripts/bootstrap_admin_key.py --name "Emergency Admin"

# Save the new key securely
# Revoke old keys via UI or API
```

### Startup Validation Failures

```bash
# Check validation errors
python main.py 2>&1 | grep "Production validation failed"

# Common issues:
# 1. AVI_TEST_MODE=1 -> unset AVI_TEST_MODE
# 2. Missing API keys -> set MAIN_LLM_API_KEY
# 3. Invalid vector DB -> check VECTOR_DB_PROVIDER
```

### Service Won't Start

```bash
# Check logs
tail -f logs/avi.log

# Verify environment
env | grep -E "(ENVIRONMENT|AVI_|MAIN_LLM|VECTOR_DB)"

# Test configuration
python -c "from config.settings import settings; print(settings.model_dump_json(indent=2))"
```

## Post-Deployment

- [ ] **Monitor First Hour**
  - [ ] Check logs for errors
  - [ ] Monitor response times
  - [ ] Verify health check status
  - [ ] Check rate limiting effectiveness

- [ ] **Documentation**
  - [ ] Document deployment specifics
  - [ ] Update runbook with environment details
  - [ ] Share API key creation process with team
  - [ ] Document monitoring dashboards

- [ ] **Team Training**
  - [ ] Train team on API key management
  - [ ] Share authentication documentation
  - [ ] Review emergency procedures
  - [ ] Schedule regular security reviews

## Regular Maintenance

### Weekly
- [ ] Review API key usage
- [ ] Check for unused/old keys
- [ ] Monitor rate limit violations
- [ ] Review error logs

### Monthly
- [ ] Rotate API keys (as per policy)
- [ ] Review and update access roles
- [ ] Backup verification
- [ ] Performance review

### Quarterly
- [ ] Security audit
- [ ] Update dependencies
- [ ] Review and update documentation
- [ ] Capacity planning

## Resources

- [Authentication Documentation](./AUTHENTICATION.md)
- [API Documentation](./API.md)
- [Deployment Guide](./deployment.md)
- [Production MVP Plan](../PRODUCTION_MVP_PLAN.md)
