# Functional Blocks Diagram - AVI System

> Функциональная схема системы AVI с блоками ответственности

**Версия**: 2.0
**Дата**: 2025-11-13
**Цель**: Показать функциональные блоки и их взаимодействие

---

## 🎯 Функциональные блоки системы

```mermaid
graph TB
    subgraph "User Interaction"
        UI_DASH[📱 Dashboard UI<br/>React SPA]
        UI_PLAY[🎮 Playground<br/>Query Testing]
        UI_ADMIN[⚙️ Admin Panel<br/>Configuration]
        API_CLIENT[📡 API Clients<br/>External Systems]
    end

    subgraph "API Layer"
        AUTH[🔐 Authentication<br/>API Key Validation<br/>RBAC]
        RATE[⏱️ Rate Limiting<br/>Request Throttling<br/>Quota Management]
        ROUTING[🔀 Request Routing<br/>Endpoint Mapping<br/>Versioning]
        VALID[✅ Input Validation<br/>Schema Validation<br/>Sanitization]
    end

    subgraph "Query Processing"
        INPUT_FILTER[🛡️ Input Filtering<br/>- Vector Rule Matching<br/>- Safety LLM Check<br/>- Prompt Modification]
        RAG_RETRIEVAL[📚 RAG Retrieval<br/>- Vector Search<br/>- Document Reranking<br/>- Context Assembly]
        LLM_GEN[🤖 LLM Generation<br/>- Prompt Construction<br/>- API Calls<br/>- Response Parsing]
        OUTPUT_FILTER[🔍 Output Filtering<br/>- Response Validation<br/>- Content Sanitization<br/>- Output Cleaning]
    end

    subgraph "Data Management"
        RULE_MGT[📋 Rules Management<br/>- Upload Rules<br/>- Validate Rules<br/>- Version Control]
        DOC_MGT[📄 Documents Management<br/>- Upload Documents<br/>- Update Metadata<br/>- Link to Rules]
        LINK_MGT[🔗 Links Management<br/>- Rule-Doc Associations<br/>- Approval Workflow<br/>- Batch Operations]
        INDEX_MGT[🗂️ Indexing Management<br/>- Vector Generation<br/>- Background Reindex<br/>- Index Optimization]
    end

    subgraph "Configuration"
        CONFIG_MGT[⚙️ Configuration Manager<br/>- Dynamic Settings<br/>- Feature Flags<br/>- Threshold Tuning]
        API_KEY_MGT[🔑 API Key Management<br/>- Key Generation<br/>- Permission Assignment<br/>- Key Rotation]
        FILTER_CONFIG[🛠️ Filter Configuration<br/>- Granular Control<br/>- Component Toggle<br/>- Default Settings]
    end

    subgraph "Storage & Caching"
        VECTOR_STORE[💾 Vector Storage<br/>- Embeddings<br/>- Similarity Search<br/>- Collection Management]
        CACHE_LAYER[⚡ Cache Layer<br/>- Result Caching<br/>- TTL Management<br/>- Invalidation]
        FILE_STORE[📁 File Storage<br/>- Raw Data<br/>- Configurations<br/>- Artifacts]
    end

    subgraph "External Integrations"
        LLM_PROVIDER[🤖 LLM Providers<br/>- OpenAI<br/>- Anthropic<br/>- Custom APIs]
        SAFETY_PROVIDER[🛡️ Safety Providers<br/>- OpenAI Moderation<br/>- Llama Guard<br/>- Custom Plugins]
        EMBED_PROVIDER[🧠 Embedding Providers<br/>- Sentence Transformers<br/>- OpenAI Embeddings]
    end

    subgraph "Observability"
        METRICS[📊 Metrics Collection<br/>- Request Latency<br/>- Cache Hit Rate<br/>- Filter Interventions]
        TRACING[🔍 Distributed Tracing<br/>- Request Flow<br/>- Service Dependencies<br/>- Performance Analysis]
        LOGGING[📝 Structured Logging<br/>- JSON Logs<br/>- Correlation IDs<br/>- Error Tracking]
        MONITORING[📈 Monitoring Dashboards<br/>- Grafana<br/>- Jaeger UI<br/>- MLflow]
    end

    subgraph "Research & Experiments"
        NOTEBOOKS[📓 Jupyter Notebooks<br/>- Experiment Templates<br/>- Interactive Analysis]
        EXP_TRACKER[🧪 Experiment Tracker<br/>- Metadata Management<br/>- Result Logging<br/>- Artifact Storage]
        BENCHMARK[📊 Benchmarking<br/>- Performance Tests<br/>- Accuracy Evaluation<br/>- Comparison]
    end

    %% User Interactions
    UI_DASH --> ROUTING
    UI_PLAY --> ROUTING
    UI_ADMIN --> ROUTING
    API_CLIENT --> ROUTING

    %% API Layer Flow
    ROUTING --> AUTH
    AUTH --> RATE
    RATE --> VALID
    VALID --> INPUT_FILTER

    %% Query Processing Flow
    INPUT_FILTER --> RAG_RETRIEVAL
    RAG_RETRIEVAL --> LLM_GEN
    LLM_GEN --> OUTPUT_FILTER

    %% Data Management Dependencies
    INPUT_FILTER --> RULE_MGT
    OUTPUT_FILTER --> RULE_MGT
    RAG_RETRIEVAL --> DOC_MGT
    RULE_MGT --> LINK_MGT
    DOC_MGT --> LINK_MGT
    LINK_MGT --> INDEX_MGT

    %% Configuration Dependencies
    INPUT_FILTER --> FILTER_CONFIG
    OUTPUT_FILTER --> FILTER_CONFIG
    AUTH --> API_KEY_MGT
    RATE --> CONFIG_MGT

    %% Storage Dependencies
    RULE_MGT --> VECTOR_STORE
    DOC_MGT --> VECTOR_STORE
    INDEX_MGT --> VECTOR_STORE
    INPUT_FILTER --> CACHE_LAYER
    LLM_GEN --> CACHE_LAYER
    CONFIG_MGT --> FILE_STORE

    %% External Integrations
    LLM_GEN --> LLM_PROVIDER
    INPUT_FILTER --> SAFETY_PROVIDER
    OUTPUT_FILTER --> SAFETY_PROVIDER
    INDEX_MGT --> EMBED_PROVIDER

    %% Observability
    ROUTING --> METRICS
    AUTH --> METRICS
    INPUT_FILTER --> METRICS
    LLM_GEN --> METRICS
    OUTPUT_FILTER --> METRICS
    ROUTING --> TRACING
    ROUTING --> LOGGING
    METRICS --> MONITORING

    %% Research
    NOTEBOOKS --> EXP_TRACKER
    BENCHMARK --> EXP_TRACKER
    EXP_TRACKER --> MONITORING

    %% Styling
    classDef userLayer fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef apiLayer fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef processingLayer fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef dataLayer fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef configLayer fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    classDef storageLayer fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef externalLayer fill:#eceff1,stroke:#263238,stroke-width:2px
    classDef obsLayer fill:#e0f2f1,stroke:#004d40,stroke-width:2px
    classDef researchLayer fill:#f1f8e9,stroke:#33691e,stroke-width:2px

    class UI_DASH,UI_PLAY,UI_ADMIN,API_CLIENT userLayer
    class AUTH,RATE,ROUTING,VALID apiLayer
    class INPUT_FILTER,RAG_RETRIEVAL,LLM_GEN,OUTPUT_FILTER processingLayer
    class RULE_MGT,DOC_MGT,LINK_MGT,INDEX_MGT dataLayer
    class CONFIG_MGT,API_KEY_MGT,FILTER_CONFIG configLayer
    class VECTOR_STORE,CACHE_LAYER,FILE_STORE storageLayer
    class LLM_PROVIDER,SAFETY_PROVIDER,EMBED_PROVIDER externalLayer
    class METRICS,TRACING,LOGGING,MONITORING obsLayer
    class NOTEBOOKS,EXP_TRACKER,BENCHMARK researchLayer
```

---

## 📋 Детальное описание блоков

### 🎯 User Interaction Layer

#### Dashboard UI
- **Ответственность**: Административный интерфейс
- **Функции**:
  - Dashboard overview (metrics, health)
  - Query playground (testing)
  - Filters management (rules, documents)
  - Monitoring (embedded Grafana, Jaeger)
  - Experiments (notebook management)
  - Settings (configuration)
- **Технологии**: React 18, TypeScript, Ant Design

#### API Clients
- **Ответственность**: Внешние системы интеграции
- **Функции**:
  - REST API calls
  - Authentication via API keys
  - Programmatic access
- **Примеры**: Python SDK, JavaScript client, CLI tool

---

### 🔐 API Layer

#### Authentication
- **Ответственность**: Проверка подлинности
- **Функции**:
  - API key validation (SHA-256)
  - Role-based access control (RBAC)
  - Permission checks
  - Key expiration management
- **Файл**: `src/api/auth.py`

#### Rate Limiting
- **Ответственность**: Защита от перегрузки
- **Функции**:
  - Request throttling
  - Per-endpoint limits
  - API key quotas
  - Distributed rate limiting (Redis)
- **Файл**: `src/api/rate_limit.py`

#### Request Routing
- **Ответственность**: Маршрутизация запросов
- **Функции**:
  - Endpoint mapping
  - API versioning
  - CORS handling
  - Request correlation
- **Файл**: `src/api/routes.py`

#### Input Validation
- **Ответственность**: Валидация входных данных
- **Функции**:
  - Schema validation (Pydantic)
  - Type checking
  - Input sanitization
  - Error handling
- **Технология**: Pydantic models

---

### 🔄 Query Processing Layer

#### Input Filtering
- **Ответственность**: Фильтрация входных запросов
- **Функции**:
  - Vector-based rule matching
  - Safety LLM integration (optional)
  - Prompt modification
  - Category detection
- **Файл**: `src/core/content_filter.py`
- **Компоненты**:
  - `enable_vector_rules` - поиск похожих правил
  - `enable_safety_llm` - проверка через Safety API
  - `enable_prompt_modification` - модификация запроса

#### RAG Retrieval
- **Ответственность**: Контекстуальное обогащение
- **Функции**:
  - Vector similarity search
  - Document reranking (cross-encoder)
  - Relevance scoring
  - Context assembly
- **Файл**: `src/core/rag_system.py`

#### LLM Generation
- **Ответственность**: Генерация ответа
- **Функции**:
  - Prompt construction
  - API calls to LLM providers
  - Response parsing
  - Streaming support
  - Error handling
- **Файл**: `src/core/llm_service.py`

#### Output Filtering
- **Ответственность**: Фильтрация ответов LLM
- **Функции**:
  - Response validation
  - Content sanitization
  - PII detection
  - Output cleaning (system markers removal)
- **Файл**: `src/core/content_filter.py`
- **Компоненты**:
  - `enable_vector_rules` - проверка ответа
  - `enable_safety_llm` - Safety API проверка
  - `enable_output_cleaning` - очистка выхода

---

### 📊 Data Management Layer

#### Rules Management
- **Ответственность**: Управление правилами фильтрации
- **Функции**:
  - Upload rules (CSV)
  - Rule validation
  - Category management
  - Version control
- **Файл**: `src/services/filter_service.py`

#### Documents Management
- **Ответственность**: Управление knowledge base
- **Функции**:
  - Upload documents (CSV)
  - Metadata management
  - Document linking
  - Content updates
- **Файл**: `src/services/rag_service.py`

#### Links Management
- **Ответственность**: Rule-Document ассоциации
- **Функции**:
  - Create links
  - Approval workflow
  - Batch operations
  - Link validation
- **Файл**: `src/services/links_manager.py`

#### Indexing Management
- **Ответственность**: Векторное индексирование
- **Функции**:
  - Embedding generation
  - Background reindex tasks
  - Index optimization
  - Collection management
- **Файл**: `src/services/indexing_service.py`

---

### ⚙️ Configuration Layer

#### Configuration Manager
- **Ответственность**: Динамическая конфигурация
- **Функции**:
  - Settings management
  - Feature flags
  - Threshold tuning
  - Configuration persistence
- **Файл**: `src/services/config_manager.py`

#### API Key Management
- **Ответственность**: Управление API keys
- **Функции**:
  - Key generation
  - Role assignment
  - Key rotation
  - Usage tracking
- **Файл**: `src/api/auth.py` (APIKeyManager)

#### Filter Configuration
- **Ответственность**: Настройка фильтрации
- **Функции**:
  - Granular component control
  - Default settings
  - Per-request overrides
  - Configuration validation
- **Файл**: `src/services/config_manager.py`

---

### 💾 Storage & Caching Layer

#### Vector Storage
- **Ответственность**: Хранение embeddings
- **Функции**:
  - Vector indexing (HNSW)
  - Similarity search
  - Collection management
  - Persistence
- **Технология**: Qdrant
- **Файл**: `src/services/vector_db.py`

#### Cache Layer
- **Ответственность**: Кэширование результатов
- **Функции**:
  - Query result caching
  - TTL management
  - Cache invalidation
  - Distributed cache
- **Технология**: Redis
- **Файл**: `src/services/cache_service.py`

#### File Storage
- **Ответственность**: Файловое хранилище
- **Функции**:
  - Raw data storage
  - Configuration files
  - Experiment artifacts
  - API key storage
- **Директории**: `data/`, `artifacts/`

---

### 🔌 External Integrations Layer

#### LLM Providers
- **Ответственность**: Интеграция с LLM API
- **Поддерживаемые**:
  - OpenAI (GPT-4, GPT-3.5)
  - Anthropic (Claude)
  - Custom endpoints
- **Файл**: `src/services/llm_adapter.py`

#### Safety Providers
- **Ответственность**: Safety model интеграции
- **Поддерживаемые**:
  - OpenAI Moderation API
  - Llama Guard 2
  - Custom plugins
- **Файл**: `src/services/safety_client.py`, `src/services/safety_plugin.py`

#### Embedding Providers
- **Ответственность**: Генерация embeddings
- **Поддерживаемые**:
  - Sentence Transformers (local)
  - OpenAI Embeddings API
- **Файл**: `src/services/vector_db.py`

---

### 📈 Observability Layer

#### Metrics Collection
- **Ответственность**: Сбор метрик
- **Метрики**:
  - `avi_http_request_latency_seconds`
  - `avi_cache_hits_total` / `avi_cache_misses_total`
  - `avi_safety_interventions_total`
  - `avi_rerank_latency_seconds`
- **Технология**: Prometheus
- **Файл**: `src/monitoring/metrics.py`

#### Distributed Tracing
- **Ответственность**: Трассировка запросов
- **Функции**:
  - Request flow visualization
  - Service dependency mapping
  - Performance bottleneck identification
- **Технология**: OpenTelemetry, Tempo, Jaeger
- **Файл**: `src/monitoring/tracing.py`

#### Structured Logging
- **Ответственность**: Логирование
- **Функции**:
  - JSON formatted logs
  - Correlation IDs
  - Error tracking
  - Audit logs
- **Технология**: Loguru
- **Файл**: `src/utils/logger.py`

#### Monitoring Dashboards
- **Ответственность**: Визуализация
- **Компоненты**:
  - Grafana (metrics visualization)
  - Jaeger UI (trace visualization)
  - MLflow (experiment tracking)
- **Порты**: 3000, 16686, 5000

---

### 🧪 Research & Experiments Layer

#### Jupyter Notebooks
- **Ответственность**: Интерактивные эксперименты
- **Функции**:
  - Experiment templates
  - Interactive analysis
  - Data visualization
  - Result export
- **Директория**: `notebooks/`

#### Experiment Tracker
- **Ответственность**: Tracking экспериментов
- **Функции**:
  - Metadata management
  - Result logging
  - Artifact storage
  - MLflow integration
- **Файл**: `avi/experiments.py`

#### Benchmarking
- **Ответственность**: Performance тестирование
- **Функции**:
  - Accuracy evaluation
  - Latency benchmarking
  - Model comparison
  - Report generation
- **Интеграция**: Through notebooks

---

## 🔄 Взаимодействие между блоками

### Критические пути

**Path 1: Query Processing**
```
UI → Routing → Auth → Rate Limit → Input Filter
→ RAG Retrieval → LLM Generation → Output Filter → Cache → Response
```

**Path 2: Data Upload**
```
UI → Routing → Auth → Rules Management → Index Management
→ Vector Storage → Background Job → Completion
```

**Path 3: Configuration Update**
```
UI → Routing → Auth → Config Manager → File Storage
→ Dynamic Reload → Apply Changes
```

---

## 📊 Ответственность по категориям

| Категория | Блоки | Основная функция |
|-----------|-------|------------------|
| **Security** | Auth, Rate Limiting, Input/Output Filtering | Безопасность и защита |
| **Processing** | Query Processing Layer | Обработка запросов |
| **Storage** | Vector Store, Cache, File Storage | Хранение данных |
| **Integration** | LLM/Safety/Embedding Providers | Внешние интеграции |
| **Management** | Rules/Docs/Links/Index Management | Управление данными |
| **Configuration** | Config Manager, API Keys, Filter Config | Настройка системы |
| **Observability** | Metrics, Tracing, Logging, Monitoring | Мониторинг и диагностика |
| **Research** | Notebooks, Experiment Tracker, Benchmark | Исследования и оптимизация |

---

**Версия**: 2.0
**Дата**: 2025-11-13
**Статус**: ✅ Complete
**Связанные диаграммы**: [HLD](./01_HLD_ARCHITECTURE.md), [Component](./10_COMPONENTS.md)
