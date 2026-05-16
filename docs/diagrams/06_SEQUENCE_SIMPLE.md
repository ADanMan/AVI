# Simple Sequence Diagrams - AVI System

> Упрощенные sequence диаграммы для быстрого понимания основных потоков

**Версия**: 2.0
**Дата**: 2025-11-13
**Аудитория**: Новые разработчики, stakeholders

---

## 1. Query Processing (Simplified)

Основной поток обработки запроса пользователя.

```mermaid
sequenceDiagram
    participant User as 👤 User
    participant API as FastAPI
    participant Filter as Content Filter
    participant VectorDB as Qdrant
    participant LLM as External LLM

    User->>API: Send query
    API->>Filter: Check input safety
    Filter->>VectorDB: Find matching rules
    VectorDB-->>Filter: Matched rules
    Filter-->>API: Safe to proceed

    API->>VectorDB: Retrieve context (RAG)
    VectorDB-->>API: Relevant documents

    API->>LLM: Generate response
    LLM-->>API: LLM response

    API->>Filter: Check output safety
    Filter->>VectorDB: Check response
    VectorDB-->>Filter: Validation result
    Filter-->>API: Safe response

    API-->>User: Final filtered response
```

**Время**: ~700-2500ms (зависит от LLM)

---

## 2. Upload & Index (Simplified)

Загрузка и индексирование новых правил или документов.

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

## 3. Authentication Flow (Simplified)

Аутентификация запроса через API Key.

```mermaid
sequenceDiagram
    participant Client as Client
    participant API as FastAPI
    participant Auth as Auth Service
    participant Redis as Redis

    Client->>API: Request with X-API-Key
    API->>Auth: Validate key
    Auth->>Redis: Check key hash
    Redis-->>Auth: Key data

    alt Invalid Key
        Auth-->>API: ❌ Unauthorized
        API-->>Client: 401 Error
    end

    Auth->>Auth: Check expiration
    Auth->>Auth: Check permissions

    alt Insufficient Permissions
        Auth-->>API: ❌ Forbidden
        API-->>Client: 403 Error
    end

    Auth->>Redis: Update last_used
    Auth-->>API: ✅ Authorized

    API->>API: Process request
    API-->>Client: Success response
```

**Время**: ~5-15ms

---

## 4. Streaming Response (Simplified)

Потоковая генерация ответа с фильтрацией чанков.

```mermaid
sequenceDiagram
    participant Client as Client
    participant API as FastAPI
    participant StreamGuard as Stream Guard
    participant LLM as External LLM

    Client->>API: POST /query/stream
    API->>API: Validate & prepare

    API->>LLM: Start streaming
    loop Each chunk
        LLM-->>API: Chunk
        API->>StreamGuard: Check chunk safety
        StreamGuard-->>API: Safe/Blocked

        alt Chunk Safe
            API-->>Client: Stream chunk
        else Chunk Blocked
            API-->>Client: [FILTERED]
        end
    end

    LLM-->>API: Stream complete
    API-->>Client: Close stream
```

**Время**: 1-5 секунд (зависит от длины ответа)

---

## 5. Experiment Execution (Simplified)

Запуск эксперимента через Jupyter Notebook.

```mermaid
sequenceDiagram
    participant Researcher as 👩‍🔬 Researcher
    participant CLI as AVI CLI
    participant Notebook as Jupyter Notebook
    participant Tracker as Experiment Tracker
    participant MLflow as MLflow

    Researcher->>CLI: avi experiment run notebook.ipynb
    CLI->>Notebook: Execute cells
    Notebook->>Tracker: Initialize experiment
    Tracker->>MLflow: Start run

    loop For each test case
        Notebook->>API: Send test query
        API-->>Notebook: Response
        Notebook->>Tracker: Log result
        Tracker->>MLflow: Log metrics
    end

    Notebook->>Tracker: Finalize
    Tracker->>MLflow: Save artifacts
    MLflow-->>CLI: ✅ Complete

    CLI-->>Researcher: Experiment complete
```

**Время**: 5-30 минут (зависит от размера эксперимента)

---

## 6. UI Real-time Update (Simplified)

Real-time обновления в React Dashboard через WebSocket.

```mermaid
sequenceDiagram
    participant UI as React Dashboard
    participant WS as WebSocket Server
    participant API as FastAPI
    participant Metrics as Metrics Service

    UI->>WS: Connect WebSocket
    WS-->>UI: Connected

    loop Every 5 seconds
        Metrics->>WS: Publish metrics update
        WS->>WS: Check subscribers
        WS-->>UI: Push metrics
        UI->>UI: Update charts
    end

    Note over UI: User performs action
    UI->>API: POST /query
    API->>Metrics: Record metrics
    Metrics->>WS: Notify update
    WS-->>UI: Push new data
    UI->>UI: Update UI instantly
```

**Latency**: < 100ms для updates

---

## 📊 Сравнение сложности потоков

| Поток | Компоненты | Шаги | Типичное время |
|-------|-----------|------|----------------|
| Query (Simple) | 4 | 8 | 700-2500ms |
| Query (Full) | 12 | 50+ | 700-2500ms |
| Upload | 5 | 15 | 1-5 минут |
| Auth | 3 | 10 | 5-15ms |
| Streaming | 4 | Variable | 1-5 секунд |
| Experiment | 5 | 100+ | 5-30 минут |
| Real-time Update | 4 | 5 | < 100ms |

---

## 🎯 Ключевые паттерны

### 1. Request-Response (Синхронный)
```
Client → API → Processing → Response → Client
```
Примеры: Query, Upload, Auth

### 2. Background Processing (Асинхронный)
```
Client → API → Trigger Background Job
Background Job → Long Processing → Completion Notification
```
Примеры: Upload & Index, Reindex

### 3. Streaming (Server-Sent Events)
```
Client → API → Open Stream
Loop: LLM Chunk → Filter → Send to Client
Stream Complete
```
Примеры: Streaming Query

### 4. Real-time (WebSocket)
```
Client ↔ WebSocket Server
Server pushes updates when available
```
Примеры: Live metrics, System notifications

---

## ⚡ Быстрые пути (Fast Paths)

### Cache Hit (Query)
```
Client → API → Auth → Cache → Client
Time: ~15ms (100x faster!)
```

### Bypass Filtering (если доверенный клиент)
```
Client → API → Auth → LLM → Client
Time: ~500-2000ms (no filtering overhead)
```

### Pre-computed Results (для популярных запросов)
```
Client → API → Auth → Database → Client
Time: ~10-50ms
```

---

## 🔍 Когда использовать какую диаграмму

| Диаграмма | Используйте для |
|-----------|-----------------|
| **Simple Query** | Объяснение основного потока новичкам |
| **Detailed Query** | Debugging, оптимизация, полное понимание |
| **Upload** | Понимание процесса индексирования |
| **Auth** | Настройка безопасности |
| **Streaming** | Реализация real-time features |
| **Experiment** | Настройка исследовательской инфраструктуры |
| **Real-time Update** | Разработка WebSocket features |

---

## 📚 Связанные документы

- [Detailed Sequence - Query Flow](./02_SEQUENCE_QUERY_DETAILED.md)
- [HLD Architecture](./01_HLD_ARCHITECTURE.md)
- [Functional Blocks](./08_FUNCTIONAL_BLOCKS.md)
- [API Documentation](../API.md)

---

**Версия**: 2.0
**Дата**: 2025-11-13
**Статус**: ✅ Complete
**Цель**: Быстрое понимание основных потоков для новых разработчиков
