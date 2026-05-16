# Detailed Sequence Diagram - Query Processing Flow

> Детальная sequence диаграмма обработки запроса пользователя через систему AVI

**Поток**: POST /query (с RAG и фильтрацией)
**Версия**: 2.0
**Дата**: 2025-11-13

---

## 🔄 Полный поток обработки запроса

```mermaid
sequenceDiagram
    autonumber

    participant C as Client<br/>(User/API)
    participant UI as React Dashboard<br/>(optional)
    participant API as FastAPI<br/>main.py
    participant Auth as AuthService<br/>auth.py
    participant RL as RateLimiter<br/>SlowAPI
    participant Metrics as Metrics<br/>Prometheus
    participant Cache as CacheService<br/>Redis
    participant CF as ContentFilter<br/>content_filter.py
    participant VDB as VectorDBService<br/>vector_db.py
    participant Safety as SafetyClient<br/>(optional)
    participant RAG as RAGSystem<br/>rag_system.py
    participant Rerank as Reranker<br/>cross-encoder
    participant LLM as LLMService<br/>llm_service.py
    participant ExtLLM as External LLM<br/>OpenAI/Anthropic
    participant Qdrant as Qdrant DB<br/>Vector Storage
    participant Redis as Redis<br/>Cache Storage

    Note over C,Redis: 1. Request Authentication & Rate Limiting

    C->>+API: POST /query<br/>{query, use_rag, input_filtering, output_filtering}
    API->>+Auth: validate_api_key(X-API-Key)
    Auth->>Auth: hash_key(api_key)
    Auth->>Auth: check_key_exists()
    Auth->>Auth: check_is_active()
    Auth->>Auth: check_not_expired()

    alt Invalid API Key
        Auth-->>API: ❌ 401 Unauthorized
        API-->>C: {error: "Invalid API key"}
    end

    Auth->>Auth: update_last_used()
    Auth-->>-API: ✅ APIKey(role="user", permissions=[])

    API->>+RL: check_rate_limit(api_key_hash)
    RL->>Redis: get_counter(f"rate_limit:{hash}")
    Redis-->>RL: counter_value

    alt Rate Limit Exceeded
        RL-->>API: ❌ 429 Too Many Requests
        API-->>C: {error: "Rate limit exceeded"}
    end

    RL->>Redis: incr_counter(f"rate_limit:{hash}")
    RL-->>-API: ✅ Within limits

    API->>+Metrics: record_request_start(endpoint="/query")

    Note over API,Redis: 2. Check Cache

    API->>API: generate_cache_key(query, options)
    API->>+Cache: get_cached_response(cache_key)
    Cache->>Redis: GET cache_key

    alt Cache Hit
        Redis-->>Cache: cached_response
        Cache-->>API: ✅ cached_response
        API->>Metrics: record_cache_hit()
        API->>Metrics: record_request_end(latency_ms)
        API-->>-C: {response, context_used, cached: true}
        Note over C,API: ⚡ Fast path - return cached result
    end

    Redis-->>Cache: None (cache miss)
    Cache-->>-API: ❌ No cached result
    API->>Metrics: record_cache_miss()

    Note over API,Qdrant: 3. Input Filtering

    API->>+CF: filter_input(query, input_filtering_options)

    alt Vector Rules Enabled
        CF->>+VDB: search_similar_rules(query, collection="filter_rules")
        VDB->>+Qdrant: search(vector=embed(query), limit=10)
        Qdrant-->>-VDB: [Rule(id, text, score, threshold, category)]
        VDB-->>-CF: matched_rules

        CF->>CF: apply_thresholds(matched_rules)
        CF->>CF: check_violations(matched_rules)
    end

    alt Safety LLM Enabled (optional)
        CF->>+Safety: check_safety(query)
        Safety->>ExtLLM: moderation_check(query)
        ExtLLM-->>Safety: {is_safe, categories, scores}
        Safety-->>-CF: safety_result

        alt Unsafe Content Detected
            CF->>CF: sanitize_content(query)
            Note over CF: Apply safety modifications
        end
    end

    alt Prompt Modification Enabled
        CF->>CF: modify_prompt(query, matched_rules)
        Note over CF: Rewrite query to avoid violations
    end

    CF->>Metrics: record_safety_intervention(stage="input")
    CF-->>-API: FilterResult{<br/>  filtered_query,<br/>  was_modified,<br/>  matches,<br/>  components_applied<br/>}

    alt Query Blocked by Filter
        API-->>C: {<br/>  error: "Query blocked",<br/>  reason: "Filter violation",<br/>  categories: ["toxicity"]<br/>}
    end

    Note over API,Qdrant: 4. RAG Context Retrieval (if enabled)

    alt RAG Enabled
        API->>+RAG: retrieve_context(filtered_query)
        RAG->>+VDB: search_documents(filtered_query, limit=20)
        VDB->>+Qdrant: search(vector=embed(query), collection="vector_documents")
        Qdrant-->>-VDB: [Doc(id, text, score, metadata)]
        VDB-->>-RAG: candidate_documents

        alt Reranking Enabled
            RAG->>+Rerank: rerank(query, candidate_documents)
            Rerank->>Rerank: compute_cross_encoder_scores()
            Rerank->>Rerank: apply_threshold(min_score=0.5)
            Rerank->>Rerank: sort_by_score()
            Rerank->>Metrics: record_rerank_latency()
            Rerank-->>-RAG: reranked_documents[0:5]
        end

        RAG->>RAG: format_context(reranked_documents)
        RAG-->>-API: context_documents, relevance_scores
    end

    Note over API,ExtLLM: 5. LLM Generation

    API->>API: build_prompt(filtered_query, context_documents)
    API->>+LLM: generate(prompt, max_tokens, temperature)
    LLM->>+ExtLLM: POST /v1/chat/completions
    ExtLLM-->>-LLM: {choices: [{message: {content}}]}
    LLM-->>-API: llm_response

    Note over API,Qdrant: 6. Output Filtering

    API->>+CF: filter_output(llm_response, output_filtering_options)

    alt Vector Rules Enabled
        CF->>+VDB: search_similar_rules(llm_response)
        VDB->>+Qdrant: search(vector=embed(response))
        Qdrant-->>-VDB: matched_rules
        VDB-->>-CF: matched_rules
        CF->>CF: apply_thresholds(matched_rules)
    end

    alt Safety LLM Enabled (optional)
        CF->>+Safety: check_safety(llm_response)
        Safety->>ExtLLM: moderation_check(response)
        ExtLLM-->>Safety: {is_safe, categories}
        Safety-->>-CF: safety_result
    end

    alt Output Cleaning Enabled
        CF->>CF: remove_system_markers(llm_response)
        CF->>CF: sanitize_output(llm_response)
    end

    CF->>Metrics: record_safety_intervention(stage="output")
    CF-->>-API: FilterResult{<br/>  filtered_response,<br/>  was_modified,<br/>  matches<br/>}

    alt Response Blocked by Filter
        API-->>C: {<br/>  error: "Response blocked",<br/>  reason: "Contains unsafe content"<br/>}
    end

    Note over API,Redis: 7. Cache Result & Return

    API->>API: build_final_response()
    API->>+Cache: store_response(cache_key, response, ttl=3600)
    Cache->>Redis: SET cache_key response EX 3600
    Redis-->>Cache: OK
    Cache-->>-API: ✅ Cached

    API->>Metrics: record_request_end(latency_ms, status=200)
    API-->>-C: {<br/>  response: filtered_response,<br/>  context_used: true,<br/>  relevance_scores: [0.92, 0.87, ...],<br/>  processing_time_ms: 420,<br/>  timestamp: "2025-11-13T10:30:00Z",<br/>  input_filter_result: {...},<br/>  output_filter_result: {...},<br/>  cached: false<br/>}

    Note over C,Redis: ✅ Query Processing Complete
```

---

## 📊 Временные характеристики

| Этап | Типичное время | Комментарий |
|------|----------------|-------------|
| 1. Auth & Rate Limit | 5-10ms | Redis lookup |
| 2. Cache Check | 2-5ms | Redis GET |
| 3. Input Filtering | 50-150ms | Vector search + optional Safety LLM |
| 4. RAG Retrieval | 100-200ms | Vector search + reranking |
| 5. LLM Generation | 500-2000ms | Зависит от провайдера |
| 6. Output Filtering | 50-150ms | Vector search |
| 7. Cache Store | 2-5ms | Redis SET |
| **Total (without cache)** | **700-2500ms** | |
| **Total (with cache hit)** | **7-15ms** | ⚡ 100x faster |

---

## 🔀 Варианты потока

### Быстрый путь (Cache Hit)
```
Client → API → Auth → Rate Limit → Cache → Client
Time: ~15ms
```

### Без RAG
```
Client → API → Auth → Input Filter → LLM → Output Filter → Cache → Client
Time: ~600-2200ms
```

### Без фильтрации (bypass mode)
```
Client → API → Auth → LLM → Cache → Client
Time: ~500-2000ms
```

### Полный путь (все включено)
```
Client → API → Auth → Input Filter (Vector + Safety LLM)
→ RAG (Vector + Rerank) → LLM → Output Filter (Vector + Safety LLM)
→ Cache → Client
Time: ~700-2500ms
```

---

## ⚠️ Точки отказа и обработка ошибок

### 1. Authentication Failed (401)
```json
{
  "error": "Invalid or expired API key",
  "detail": "API key is invalid or has expired",
  "status_code": 401
}
```

### 2. Rate Limit Exceeded (429)
```json
{
  "error": "Rate limit exceeded",
  "detail": "Too many requests. Limit: 30/minute",
  "retry_after": 45,
  "status_code": 429
}
```

### 3. Input Filter Violation (400)
```json
{
  "error": "Query blocked by content filter",
  "reason": "Detected unsafe content",
  "categories": ["toxicity", "prompt_injection"],
  "matched_rules": [
    {
      "rule_id": "rule_123",
      "category": "toxicity",
      "score": 0.87,
      "threshold": 0.75
    }
  ],
  "status_code": 400
}
```

### 4. Output Filter Violation (500)
```json
{
  "error": "Response blocked by content filter",
  "reason": "LLM response contained unsafe content",
  "categories": ["pii", "hallucination"],
  "status_code": 500
}
```

### 5. LLM Service Error (502)
```json
{
  "error": "External LLM service error",
  "detail": "OpenAI API returned 503",
  "retry_possible": true,
  "status_code": 502
}
```

### 6. Vector DB Error (503)
```json
{
  "error": "Vector database unavailable",
  "detail": "Qdrant connection timeout",
  "status_code": 503
}
```

---

## 🎯 Ключевые особенности

### Granular Filtering Control
Клиент может контролировать каждый компонент фильтрации:

```json
{
  "query": "What is AVI?",
  "input_filtering": {
    "enable_vector_rules": true,
    "enable_safety_llm": false,
    "enable_prompt_modification": true
  },
  "output_filtering": {
    "enable_vector_rules": true,
    "enable_safety_llm": false,
    "enable_output_cleaning": true
  }
}
```

### Observability
Каждый запрос логирует:
- **Metrics**: Latency, cache hits, filter interventions
- **Traces**: Full distributed trace в Tempo/Jaeger
- **Logs**: Structured JSON с correlation_id

### Caching Strategy
- **Key**: SHA-256(query + options)
- **TTL**: 3600 seconds (configurable)
- **Invalidation**: Manual или by TTL
- **Hit rate**: 60-80% (typical)

---

## 📈 Производительность

### Оптимизации

1. **Redis для Auth & Rate Limiting**
   - Shared state между workers
   - Sub-millisecond latency

2. **Aggressive Caching**
   - 60-80% cache hit rate
   - 100x speedup для повторных запросов

3. **Vector Search Optimizations**
   - HNSW index в Qdrant
   - Batch embeddings (где возможно)

4. **Reranker Optimization**
   - Only top-K candidates
   - Score threshold для early exit

5. **Async/Await везде**
   - Non-blocking I/O
   - Concurrent operations где возможно

### Bottlenecks

1. **External LLM API** - 500-2000ms (самый медленный)
2. **Safety LLM** - 200-500ms (если включен)
3. **Vector Search** - 50-100ms (зависит от размера БД)

---

## 🔧 Конфигурация

### Environment Variables

```bash
# Filtering
FILTER_DEFAULT_THRESHOLD=0.60
SAFETY_MODE=disabled  # disabled | local | external | plugin

# RAG
RAG_ENABLED=true
RAG_CANDIDATE_COUNT=5
RERANK_ENABLED=true

# Cache
CACHE_BACKEND=redis
CACHE_TTL=3600

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_QUERY=30/minute
```

### Request Options

```typescript
interface QueryRequest {
  query: string;
  use_rag?: boolean;
  use_cache?: boolean;
  input_filtering?: FilteringOptions;
  output_filtering?: FilteringOptions;
  max_tokens?: number;
  temperature?: number;
}

interface FilteringOptions {
  enable_vector_rules?: boolean;
  enable_safety_llm?: boolean;
  enable_prompt_modification?: boolean;
  enable_output_cleaning?: boolean;
}
```

---

**Версия**: 2.0
**Дата**: 2025-11-13
**Статус**: ✅ Production
**Связанные диаграммы**: [HLD Architecture](./01_HLD_ARCHITECTURE.md)
