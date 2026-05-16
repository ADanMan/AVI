# Detailed Sequence Diagram - Streaming Query Flow

> Детальная sequence диаграмма обработки streaming запроса с real-time фильтрацией

**Поток**: POST /query/stream (Server-Sent Events)
**Версия**: 1.0
**Дата**: 2025-11-15

---

## 🔄 Полный поток streaming обработки

```mermaid
sequenceDiagram
    autonumber

    participant C as Client
    participant API as FastAPI
    participant Auth as AuthService
    participant RL as RateLimiter
    participant SG as StreamingGuard
    participant CF as ContentFilter
    participant VDB as VectorDB
    participant LLM as LLMService
    participant ExtLLM as External LLM
    participant Metrics as Metrics

    Note over C,Metrics: 1. Authentication & Setup

    C->>+API: POST /query/stream<br/>{query, stream_guard_mode}
    API->>+Auth: validate_api_key(X-API-Key)

    alt Invalid API Key
        Auth-->>API: ❌ 401 Unauthorized
        API-->>C: SSE: event: error, data: {error}
    end

    Auth-->>-API: ✅ APIKey validated
    API->>+RL: check_rate_limit()

    alt Rate Limit Exceeded
        RL-->>API: ❌ 429 Too Many Requests
        API-->>C: SSE: event: error, data: {error}
    end

    RL-->>-API: ✅ Within limits

    Note over API,VDB: 2. Input Filtering

    API->>+CF: filter_input(query)
    CF->>+VDB: search_similar_rules(query)
    VDB-->>-CF: matched_rules
    CF-->>-API: FilterResult{filtered_query}

    alt Query Blocked
        API-->>C: SSE: event: error, data: {blocked}
        API-->>C: SSE: event: done
    end

    Note over API,ExtLLM: 3. Start Streaming Generation

    API-->>C: SSE: event: start, data: {request_id}
    API->>Metrics: record_stream_start()

    API->>+LLM: generate_stream(filtered_query)
    LLM->>+ExtLLM: POST /v1/chat/completions<br/>{stream: true}

    Note over ExtLLM,SG: 4. Stream with Real-time Filtering

    loop For each chunk from LLM
        ExtLLM-->>LLM: chunk: {delta: "text"}
        LLM-->>API: chunk_text

        alt StreamGuard Enabled
            API->>+SG: filter_chunk(chunk_text, context)

            alt Rule-based check
                SG->>+VDB: quick_rule_check(chunk)
                VDB-->>-SG: rule_match_result
            end

            alt LLM Safety check (if enabled)
                SG->>ExtLLM: safety_check(accumulated_text)
                ExtLLM-->>SG: safety_result
            end

            alt Chunk Blocked
                SG-->>API: ❌ BlockResult{reason}
                API-->>C: SSE: event: error, data: {filtered}
                API->>LLM: cancel_stream()
                LLM->>ExtLLM: Close connection
                Note over API: Stream terminated
            end

            SG-->>-API: ✅ Safe chunk
        end

        API-->>C: SSE: event: chunk, data: {text: chunk}
        API->>Metrics: record_chunk_sent()
    end

    ExtLLM-->>-LLM: [Stream end]
    LLM-->>-API: stream_complete

    Note over API,VDB: 5. Final Output Validation

    API->>API: accumulate_full_response()
    API->>+CF: filter_output(full_response)
    CF->>+VDB: search_similar_rules(response)
    VDB-->>-CF: matched_rules
    CF-->>-API: FilterResult{final_validation}

    alt Final Response Blocked
        API-->>C: SSE: event: error, data: {output_blocked}
    else Response OK
        API->>Metrics: record_stream_complete()
        API-->>C: SSE: event: done, data: {stats}
    end

    API-->>-C: [Close SSE connection]

    Note over C,Metrics: ✅ Streaming Complete
```

---

## 📊 Streaming Guard Modes

| Mode | Description | Latency | Accuracy |
|------|-------------|---------|----------|
| **BYPASS** | No filtering during streaming | 0ms | N/A |
| **RULE_ONLY** | Fast vector rule checks only | 10-30ms/chunk | 70% |
| **LLM_ONLY** | Safety LLM checks on accumulated text | 100-300ms/check | 95% |
| **HYBRID** | Rules first, LLM fallback | 10-300ms | 90% |

---

## 🔀 Stream Flow Variants

### Fast Path (BYPASS mode)
```
Client → Auth → LLM Stream → Client
Chunks flow: Real-time, no filtering
```

### Safe Path (HYBRID mode)
```
Client → Auth → Input Filter → LLM Stream → Streaming Guard (chunk-by-chunk) → Client
May terminate stream if violation detected
```

---

## ⚠️ Error Handling

### Stream Termination Scenarios

**1. Input Filter Violation (before streaming)**
```json
{
  "event": "error",
  "data": {
    "error": "Query blocked by content filter",
    "categories": ["prompt_injection"]
  }
}
```

**2. Mid-Stream Violation**
```json
{
  "event": "chunk",
  "data": {"text": "The answer is "}
}
{
  "event": "error",
  "data": {
    "error": "Stream terminated",
    "reason": "Unsafe content detected",
    "chunk_number": 5
  }
}
```

**3. Final Output Blocked**
```json
{
  "event": "error",
  "data": {
    "error": "Complete response blocked after validation",
    "categories": ["pii", "toxicity"]
  }
}
```

---

## 🎯 Configuration

```bash
# Streaming Guard Mode
STREAM_GUARD_MODE=hybrid  # bypass | rule_only | llm_only | hybrid

# Chunk Processing
STREAM_CHUNK_SIZE=50  # characters per chunk
STREAM_BUFFER_SIZE=200  # context window for LLM checks

# Timeouts
STREAM_TIMEOUT=30  # seconds
STREAM_IDLE_TIMEOUT=5  # seconds between chunks
```

---

## 📈 Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| First chunk latency | 500-1000ms | Input filter + LLM start |
| Chunk interval | 50-200ms | Depends on LLM speed |
| Guard overhead (RULE_ONLY) | 10-30ms/chunk | Fast vector check |
| Guard overhead (LLM_ONLY) | 100-300ms/check | Every 5 chunks |
| Total stream time | 2-10s | For 500 token response |

---

**Версия**: 1.0
**Дата**: 2025-11-15
**Статус**: ✅ Production
**Связанные диаграммы**: [Query Detailed](./02_SEQUENCE_QUERY_DETAILED.md), [HLD](./01_HLD_ARCHITECTURE.md)
