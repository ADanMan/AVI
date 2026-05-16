# Detailed Sequence Diagram - Upload & Reindex Flow

> Детальная sequence диаграмма процесса загрузки и индексирования данных

**Поток**: POST /upload/rules, POST /reindex
**Версия**: 1.0
**Дата**: 2025-11-15

---

## 🔄 Полный поток загрузки и индексирования

```mermaid
sequenceDiagram
    autonumber

    participant Admin as Admin User
    participant API as FastAPI
    participant Auth as AuthService
    participant Validator as FilterService
    participant IndexSvc as IndexingService
    participant StateMan as IndexingStateManager
    participant VDB as VectorDBService
    participant Qdrant as Qdrant DB
    participant BG as BackgroundTask
    participant Metrics as Metrics

    Note over Admin,Metrics: 1. Authentication & Validation

    Admin->>+API: POST /upload/rules<br/>Content-Type: multipart/form-data
    API->>+Auth: validate_api_key(X-API-Key)
    Auth->>Auth: check_permission("write")

    alt Insufficient Permissions
        Auth-->>API: ❌ 403 Forbidden
        API-->>Admin: {error: "Write permission required"}
    end

    Auth-->>-API: ✅ Authorized

    Note over API,Validator: 2. File Upload & Parsing

    API->>API: save_uploaded_file()
    API->>API: parse_csv(file)

    alt Invalid CSV Format
        API-->>Admin: ❌ 400 Bad Request<br/>{error: "Invalid CSV format"}
    end

    API->>API: rules[] = parse_rules(csv_data)

    Note over API,Validator: 3. Rule Validation

    loop For each rule in rules[]
        API->>+Validator: validate_rule(rule)

        Validator->>Validator: check_text_length()
        Validator->>Validator: check_threshold_range()
        Validator->>Validator: check_category_valid()
        Validator->>Validator: check_risk_level()

        alt Check for Duplicates
            Validator->>+VDB: find_matching_rules(rule.text)
            VDB->>+Qdrant: search(vector, top_k=1)
            Qdrant-->>-VDB: similar_rules
            VDB-->>-Validator: similarity_scores

            alt Duplicate Found (score > 0.95)
                Validator-->>API: ❌ ValidationError
                Note over API: Add to failed_rules[]
            end
        end

        Validator-->>-API: ✅ Rule valid
        Note over API: Add to valid_rules[]
    end

    alt All Rules Failed Validation
        API-->>Admin: ❌ 400 Bad Request<br/>{failed_rules, errors}
    end

    Note over API,Qdrant: 4. Indexing Preparation

    API->>+StateMan: get_status()
    StateMan-->>-API: current_status

    alt Indexing Already In Progress
        API-->>Admin: ❌ 409 Conflict<br/>{error: "Indexing in progress"}
    end

    API->>+StateMan: start_indexing()
    StateMan->>StateMan: status = IN_PROGRESS
    StateMan->>StateMan: start_time = now()
    StateMan-->>-API: ✅ Started

    API-->>Admin: ✅ 202 Accepted<br/>{message: "Upload successful", job_id}

    Note over BG,Qdrant: 5. Background Indexing Process

    API->>+BG: trigger_indexing_task(valid_rules)

    BG->>+IndexSvc: index_rules(valid_rules)

    IndexSvc->>StateMan: update_progress(phase="embedding")

    loop For each rule in valid_rules
        IndexSvc->>IndexSvc: generate_embedding(rule.text)
        IndexSvc->>StateMan: increment_processed_count()

        alt Every 10 rules
            IndexSvc->>StateMan: update_progress()
        end
    end

    IndexSvc->>StateMan: update_progress(phase="indexing")

    IndexSvc->>+VDB: batch_add_rules(rules_with_embeddings)
    VDB->>+Qdrant: upsert(collection="filter_rules", points)
    Qdrant-->>-VDB: ✅ Indexed
    VDB-->>-IndexSvc: success_count

    IndexSvc->>StateMan: update_progress(phase="links")

    alt If Links Provided
        loop For each link in links[]
            IndexSvc->>+VDB: create_link(rule_id, doc_id)
            VDB->>+Qdrant: upsert(collection="rule_links", point)
            Qdrant-->>-VDB: ✅ Created
            VDB-->>-IndexSvc: link_created
            IndexSvc->>StateMan: increment_links_count()
        end
    end

    IndexSvc->>StateMan: update_progress(phase="finalizing")
    IndexSvc->>StateMan: complete_indexing(success=true)

    StateMan->>StateMan: status = COMPLETED
    StateMan->>StateMan: end_time = now()
    StateMan->>StateMan: calculate_duration()

    IndexSvc->>Metrics: record_indexing_complete()
    IndexSvc-->>-BG: ✅ Indexing complete

    BG-->>-Admin: Webhook/SSE: {status: "completed", stats}

    Note over Admin,Metrics: ✅ Upload & Index Complete
```

---

## 📊 Indexing Phases

| Phase | Description | Progress Range | Typical Time |
|-------|-------------|----------------|--------------|
| **idle** | No indexing running | 0% | - |
| **embedding** | Generating vector embeddings | 0-40% | 30-60s |
| **indexing** | Storing in Qdrant | 40-70% | 20-40s |
| **links** | Creating rule-document links | 70-95% | 10-30s |
| **finalizing** | Cleanup and verification | 95-100% | 5-10s |
| **completed** | All done | 100% | - |

---

## 🔀 Alternative Flows

### Reindex Existing Data

```mermaid
sequenceDiagram
    participant Admin
    participant API
    participant IndexSvc
    participant VDB
    participant Qdrant

    Admin->>API: POST /reindex
    API->>IndexSvc: reindex_all_data()

    IndexSvc->>VDB: delete_all_collections()
    VDB->>Qdrant: delete_collection("filter_rules")
    VDB->>Qdrant: delete_collection("vector_documents")
    VDB->>Qdrant: delete_collection("rule_links")

    IndexSvc->>VDB: recreate_collections()
    VDB->>Qdrant: create_collection(config)

    IndexSvc->>IndexSvc: load_from_csv_files()
    IndexSvc->>VDB: batch_index_all()

    IndexSvc-->>API: ✅ Reindex complete
    API-->>Admin: {status: "completed", stats}
```

---

## ⚠️ Error Scenarios

### 1. Validation Errors

```json
{
  "error": "Validation failed",
  "message": "3 rules failed validation",
  "failed_rules": [
    {
      "row": 5,
      "rule_text": "test...",
      "error": "Threshold must be between 0.0 and 1.0"
    }
  ],
  "valid_count": 47,
  "failed_count": 3
}
```

### 2. Concurrent Indexing

```json
{
  "error": "Indexing already in progress",
  "current_progress": 45,
  "phase": "embedding",
  "started_at": "2025-11-15T10:30:00Z"
}
```

### 3. Indexing Failure

```json
{
  "error": "Indexing failed",
  "phase": "indexing",
  "processed": 120,
  "total": 200,
  "last_error": "Qdrant connection timeout"
}
```

---

## 🎯 Validation Rules

### Rule Validation Checks

```python
# Text validation
- Length: 3-1000 characters
- Not empty or whitespace only

# Threshold validation
- Range: 0.0 to 1.0
- Must be specified

# Category validation
- Must be in ALLOWED_CATEGORIES:
  ["Toxicity", "PII", "PromptInjection", "Bias",
   "Hallucination", "Violence", "Hate", "Sexual", "Custom"]

# Risk level validation (optional)
- Must be in: ["low", "medium", "high", "critical"]

# Duplicate check
- Similarity score with existing rules < 0.95
```

---

## 📈 Performance Metrics

| Dataset Size | Embedding Time | Indexing Time | Total Time |
|--------------|----------------|---------------|------------|
| 100 rules | 15s | 5s | 25s |
| 1,000 rules | 1m 30s | 20s | 2m |
| 10,000 rules | 15m | 3m | 20m |
| 100,000 rules | 2h 30m | 30m | 3h 15m |

*Assuming CPU-based embeddings, single worker*

---

## 🔧 Configuration

```bash
# Indexing Settings
INDEXING_ENABLED=true
INDEXING_BATCH_SIZE=100
INDEXING_MAX_WORKERS=4

# Vector DB
VECTOR_DB_PROVIDER=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_RULES=filter_rules
QDRANT_COLLECTION_DOCS=vector_documents
QDRANT_COLLECTION_LINKS=rule_links

# Validation
VALIDATE_DUPLICATES=true
DUPLICATE_THRESHOLD=0.95
```

---

## 📊 State Tracking (SSE/WebSocket)

Admins can subscribe to real-time indexing updates:

**GET /api/v1/indexing/status/stream** (SSE)

```javascript
const eventSource = new EventSource('/api/v1/indexing/status/stream');

eventSource.addEventListener('progress', (e) => {
  const data = JSON.parse(e.data);
  console.log(`Phase: ${data.phase}, Progress: ${data.progress}%`);
});

eventSource.addEventListener('complete', (e) => {
  console.log('Indexing complete!');
  eventSource.close();
});
```

---

**Версия**: 1.0
**Дата**: 2025-11-15
**Статус**: ✅ Production
**Связанные документы**: [INDEXING_PROCESS.md](../INDEXING_PROCESS.md), [INDEXING_STATUS.md](../INDEXING_STATUS.md)
