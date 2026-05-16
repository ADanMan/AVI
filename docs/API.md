# AVI API — Current Endpoints

This document mirrors the Swagger UI after localization and refreshed examples.

> Operational validation steps (environment variables, health checks, and
> benchmarking) are documented in [`docs/runbook.md`](./runbook.md).

## Basic Information
- **Base URL:** `http://localhost:8000`
- **Swagger UI:** `http://localhost:8000/docs`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

> For production deployments, add authentication (for example, via FastAPI dependencies or a reverse proxy).

---

## 1. Request Processing

### `POST /query`
Safely processes a user query with filtering and (optionally) an attached RAG context.

**Request example**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
        "query": "Tell me how AVI moderates LLM answers",
        "use_cache": true,
        "use_llm_filter": true,
        "rag_mode": true
      }'
```

**Successful response (200)**
```json
{
  "response": "The AVI system analyzes the query, selects related documents, and filters the answer before returning it.",
  "context_used": true,
  "relevance_scores": [0.92, 0.87],
  "processing_time": 0.42,
  "timestamp": "2024-05-20T11:05:12",
  "input_filter_result": null,
  "output_filter_result": null
}
```

**Error codes**
- `422` — Request body failed validation (for example, an empty `query`).
- `500` — Internal error when reaching the database or LLM.

---

### `POST /query/stream`
Returns a streaming SSE response (`text/event-stream`) with every chunk filtered by the streaming guard.

**Query parameters**
- `stream_mode` — Moderation mode (`rule-only`, `llm-only`, `hybrid`, `bypass`). Defaults to `STREAM_GUARD_MODE`.

```bash
curl -N -X POST 'http://localhost:8000/query/stream?stream_mode=hybrid' \
  -H "Content-Type: application/json" \
  -d '{"query": "Summarize AVI security policies"}'
```

**Typical events in the stream**
- `data: {"chunk": "..."}` — A safe fragment of the answer. If `filtered=true`, the chunk was rewritten.
- `data: {"event": "guard_blocked", "reason": "rule_violation", ...}` — The stream was stopped because a filtering rule triggered.
- `data: {"event": "guard_metrics", "mode": "hybrid", "metrics": {"processed_chunks": 3, ...}}` — Final metrics for the session.

Errors: `422` (validation), `500` (generation failure).

---

## 2. Managing Knowledge and Rules

### `POST /upload/documents`
Uploads documents in CSV format. Required columns: `id`, `text`. Optional: `category`, `source`, `rule_ids`.

**Form fields**
- `file`: CSV file.
- `text_columns`: for example `text`.
- `metadata_columns`: for example `category,source,rule_ids`.
- `batch_size`: Batch size (defaults to `1000`).

```bash
curl -X POST http://localhost:8000/upload/documents \
  -F "file=@data/raw/vector_documents.csv" \
  -F "text_columns=text" \
  -F "metadata_columns=category,source,rule_ids"
```

Response 200:
```json
{
  "status": "success",
  "processed_documents": 125,
  "file_name": "vector_documents.csv",
  "errors": null,
  "warnings": ["Row 8: rule_ids were not provided"],
  "timestamp": "2024-05-20T11:02:44"
}
```

Errors: `400` (missing required columns), `409` (conflict, resource reserved), `500` (internal error).

---

### `POST /upload/rules`
Adds filtering rules. Required columns: `id`, `text`, `risk_level`.

```bash
curl -X POST http://localhost:8000/upload/rules \
  -F "file=@data/raw/filter_rules.csv" \
  -F "text_columns=text" \
  -F "metadata_columns=category,risk_level,threshold,document_ids"
```

A 200 response matches the document upload contract (returns `CSVUploadResponse`). Errors: `400`, `409`, `500`.

---

### `POST /cache/clear`
Clears the response cache.

```bash
curl -X POST http://localhost:8000/cache/clear
```

Response 200: `{ "status": "success", "message": "Cache successfully cleared" }`

---

### `POST /reindex`
Starts background reindexing of documents and rules. Returns `409` if indexing is disabled by configuration.

```bash
curl -X POST http://localhost:8000/reindex
```

Response 200: `{ "status": "started", "message": "Reindexing started in the background" }`

---

## 3. Inspecting Rules and Links

### `GET /rules`
Returns the list of all filtering rules with metadata.

### `GET /rules/{rule_id}`
Returns a specific filtering rule. Returns `404` if the rule is missing.

### `POST /rules/{rule_id}/documents/{document_id}`
Creates a link between a filtering rule and a document (when indexing is enabled).

### `DELETE /rules/{rule_id}/documents/{document_id}`
Removes the link.

> Approval endpoints and batch linking (`PATCH` / `POST` with `batch`) currently return `501 Not Implemented`.

---

## 4. Managing the LLM and Settings

### `GET /stats`
Summary statistics for the vector database, cache, and streaming guard.

### `GET /health`
Comprehensive health check for the LLM, safety LLM, and vector database.

### `GET /llm/external/status`
Checks connectivity to the primary LLM.

### `GET /llm/safety/status`
Checks connectivity to the safety LLM.

### `GET /settings`
Returns the current value of `indexing_enabled`.

### `POST /settings`
Toggles indexing on or off:
```bash
curl -X POST http://localhost:8000/settings \
  -H "Content-Type: application/json" \
  -d '{"indexing_enabled": false}'
```

---

## 5. Standard Error Responses

| Code | Meaning | When it appears |
| --- | ------- | --------------- |
| 400 | Bad request | CSV missing the required columns |
| 404 | Not found | Filtering rule or document does not exist |
| 409 | Conflict | Indexing is disabled, so the operation cannot proceed |
| 422 | Validation error | Invalid JSON body or form data |
| 500 | Internal error | Database, LLM, or filesystem issues |
| 501 | Not implemented | Administrative placeholders |

Every error response includes a `detail` field for logging and UI display.

---

## 6. Granular Filter Control (Phase 2.6)

**Phase 2.6** introduces fine-grained control over filtering components for both INPUT (user queries) and OUTPUT (LLM responses). You can now enable or disable individual filtering steps independently.

### Filtering Components

Each direction (INPUT/OUTPUT) supports 4 configurable components:

| Component | Description | INPUT | OUTPUT |
|-----------|-------------|-------|--------|
| `enable_vector_rules` | Vector-based rule matching against filter database | ✓ | ✓ |
| `enable_safety_llm` | Safety LLM for content sanitization/rephrasing | ✓ | ✓ |
| `enable_prompt_modification` | Automatic prompt rewriting when rules match | ✓ | - |
| `enable_output_cleaning` | Remove system prompts and internal markers | - | ✓ |

### Per-Request Filtering Control

You can specify filtering options in each query request:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
        "query": "What is AVI?",
        "input_filtering": {
          "enable_vector_rules": true,
          "enable_safety_llm": false,
          "enable_prompt_modification": true,
          "enable_output_cleaning": false
        },
        "output_filtering": {
          "enable_vector_rules": true,
          "enable_safety_llm": false,
          "enable_prompt_modification": false,
          "enable_output_cleaning": true
        }
      }'
```

**Benefits:**
- Disable Safety LLM for trusted users → save costs
- Skip vector search for simple queries → improve latency
- Granular control per use case

### Server-Wide Default Configuration

#### `GET /settings/filtering`
Returns current default filtering configuration:

```json
{
  "default_input_filtering": {
    "enable_vector_rules": true,
    "enable_safety_llm": true,
    "enable_prompt_modification": true,
    "enable_output_cleaning": false
  },
  "default_output_filtering": {
    "enable_vector_rules": true,
    "enable_safety_llm": false,
    "enable_prompt_modification": false,
    "enable_output_cleaning": true
  }
}
```

#### `POST /settings/filtering`
Updates default filtering configuration:

```bash
curl -X POST http://localhost:8000/settings/filtering \
  -H "Content-Type: application/json" \
  -d '{
        "default_input_filtering": {
          "enable_vector_rules": true,
          "enable_safety_llm": false,
          "enable_prompt_modification": true,
          "enable_output_cleaning": false
        },
        "default_output_filtering": {
          "enable_vector_rules": true,
          "enable_safety_llm": false,
          "enable_prompt_modification": false,
          "enable_output_cleaning": false
        }
      }'
```

**Response (200):**
```json
{
  "status": "updated",
  "category": "filtering",
  "config": {
    "default_input_filtering": {...},
    "default_output_filtering": {...}
  },
  "timestamp": "2025-11-11T18:52:00"
}
```

### Component Usage Tracking

Every `FilterResult` now includes `components_applied` dict showing which components ran:

```json
{
  "input_filter_result": {
    "was_modified": false,
    "matches": [],
    "components_applied": {
      "vector_rules": true,
      "safety_llm": false,
      "prompt_modification": true,
      "output_cleaning": false
    }
  }
}
```

### Prometheus Metrics

New metrics track component usage:

```
# Number of times component was applied
content_filter_component_applied_total{component="vector_rules",stage="input"}
content_filter_component_applied_total{component="safety_llm",stage="output"}

# Number of times component modified content
content_filter_component_modified_total{component="prompt_modification",stage="input"}
```

### Streaming Endpoint Support

`POST /query/stream` supports INPUT filtering with the same options:

```bash
curl -N -X POST http://localhost:8000/query/stream \
  -H "Content-Type: application/json" \
  -d '{
        "query": "Summarize AVI",
        "input_filtering": {
          "enable_vector_rules": true,
          "enable_safety_llm": false,
          "enable_prompt_modification": true,
          "enable_output_cleaning": false
        }
      }'
```

OUTPUT filtering for streaming uses existing `stream_mode` parameter (`rule-only`, `llm-only`, `hybrid`, `bypass`).

### Backward Compatibility

The old `use_llm_filter` parameter still works but is deprecated:

```json
{
  "query": "Test",
  "use_llm_filter": true  // ⚠️ Deprecated - use input_filtering.enable_safety_llm
}
```

System automatically converts old parameter to new format with a deprecation warning.

---

## 7. Additional Notes
- All endpoints are exposed without a prefix (`/query`, not `/rag/query`).
- Request and response formats are kept in sync with the Swagger UI.
- To extend the available models, update the services in `src/services/` and the schemas in `src/models/schemas.py`.
