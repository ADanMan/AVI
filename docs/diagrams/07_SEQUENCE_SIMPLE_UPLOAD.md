# Simple Sequence Diagram - Upload Flow

> Упрощенная sequence диаграмма для быстрого понимания процесса загрузки данных

**Поток**: Upload & Index
**Версия**: 1.0
**Дата**: 2025-11-15
**Аудитория**: Новые разработчики, stakeholders

---

## 📤 Upload & Index (Simplified)

Процесс загрузки и индексирования новых правил или документов.

```mermaid
sequenceDiagram
    participant Admin as 👨‍💼 Admin
    participant API as FastAPI
    participant Validator as Validator
    participant VectorDB as Qdrant
    participant BG as Background Task

    Admin->>API: Upload CSV file
    API->>Validator: Validate data
    Validator->>Validator: Check format
    Validator->>Validator: Check duplicates

    alt Validation Failed
        Validator-->>API: ❌ Errors
        API-->>Admin: Validation errors
    end

    Validator-->>API: ✅ Valid data

    API->>BG: Start indexing job
    BG->>VectorDB: Generate embeddings
    BG->>VectorDB: Store vectors
    VectorDB-->>BG: ✅ Indexed

    API-->>Admin: Upload successful

    BG-->>Admin: Indexing complete (async)
```

**Время**: ~1-5 минут (зависит от размера)

---

## 🔄 Reindex Existing Data (Simplified)

Полная переиндексация всех данных.

```mermaid
sequenceDiagram
    participant Admin as 👨‍💼 Admin
    participant API as FastAPI
    participant Indexing as IndexingService
    participant VectorDB as Qdrant

    Admin->>API: POST /reindex
    API->>Indexing: Start reindex

    Indexing->>VectorDB: Delete old indexes
    VectorDB-->>Indexing: ✅ Deleted

    Indexing->>Indexing: Load CSV files
    Indexing->>VectorDB: Generate new embeddings
    Indexing->>VectorDB: Create new indexes

    VectorDB-->>Indexing: ✅ Complete
    Indexing-->>API: Reindex done

    API-->>Admin: Success
```

**Время**: ~5-20 минут (зависит от объема)

---

## 📊 Key Points

### Validation Checks
- ✅ CSV format correctness
- ✅ Required fields present
- ✅ Value ranges (threshold 0-1)
- ✅ Duplicate detection
- ✅ Category validation

### Indexing Phases
1. **Embedding** - Generate vector embeddings (30-60s)
2. **Indexing** - Store in Qdrant (20-40s)
3. **Links** - Create relationships (10-30s)

### Real-time Progress
Admins can track progress via:
- **SSE**: `/api/v1/indexing/status/stream`
- **Polling**: `/api/v1/indexing/status`

---

## ⚠️ Common Errors

**Validation Failed:**
```
Some rules failed validation. Check:
- Text length (3-1000 chars)
- Threshold range (0.0-1.0)
- Valid category
```

**Indexing In Progress:**
```
Cannot start new indexing while
another is running. Wait or cancel.
```

**Permission Denied:**
```
Upload requires 'write' permission.
Admin key needed for reindex.
```

---

**Версия**: 1.0
**Дата**: 2025-11-15
**Статус**: ✅ Production
**Связанные диаграммы**: [Upload Detailed](./04_SEQUENCE_UPLOAD_DETAILED.md), [HLD](./01_HLD_ARCHITECTURE.md)
