# Конфигурационная матрица AVI

## Обзор

Этот документ содержит полную матрицу конфигураций системы AVI для тестирования и развертывания в различных средах. Документ описывает все доступные параметры конфигурации, их валидные комбинации, use cases и требования к ресурсам.

**Дата создания:** 2025-11-14
**Версия:** 1.0
**Связанные задачи:** REFACTORING_PLAN.md - Задача 4.1

---

## 📊 Содержание

- [1. Конфигурационные параметры](#1-конфигурационные-параметры)
- [2. Матрица валидных комбинаций](#2-матрица-валидных-комбинаций)
- [3. Предопределенные конфигурации](#3-предопределенные-конфигурации)
- [4. Сравнительная таблица](#4-сравнительная-таблица)
- [5. Рекомендации по выбору](#5-рекомендации-по-выбору)
- [6. Автоматизированное тестирование](#6-автоматизированное-тестирование)

---

## 1. Конфигурационные параметры

### 1.1 Safety Mode (Режим безопасности)

**Параметр:** `SAFETY_MODE`
**Файл:** `config/settings.py`
**Описание:** Определяет метод санитизации контента через LLM

| Значение | Описание | Требования |
|----------|----------|------------|
| `disabled` | Только vector search, без LLM | Нет |
| `local` | Локальный safety микросервис | SAFETY_SERVICE_URL |
| `external` | Внешний LLM API (OpenRouter, OpenAI) | SAFETY_LLM_API_KEY, SAFETY_LLM_MODEL |
| `hybrid` | Комбинация local + external с fallback | Минимум один из: local или external |

**Альтернативные значения:**
- `llm` → `external`
- `remote` → `external`

---

### 1.2 Stream Guard Mode (Режим модерации streaming)

**Параметр:** `STREAM_GUARD_MODE`
**Файл:** `config/settings.py`
**Описание:** Стратегия модерации потоковых ответов от LLM

| Значение | Описание | Поведение при нарушении |
|----------|----------|------------------------|
| `bypass` | Нет проверки, все chunk'ы проходят | Нет модерации |
| `rule-only` | Только vector search по правилам | Останавливает stream |
| `llm-only` | Только LLM санитизация | Возвращает sanitized chunk |
| `hybrid` | Проверка правил + LLM санитизация | Sanitized chunk или stop |

**Default:** `hybrid`

---

### 1.3 RAG Configuration (Конфигурация RAG)

**Параметры:** `RAG_THRESHOLD`, `RERANK_ENABLED`, `RERANK_CANDIDATE_COUNT`

| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `RAG_THRESHOLD` | float | 0.75 | Минимальная релевантность для RAG документов |
| `RERANK_ENABLED` | bool | true | Включить переранжирование документов |
| `RERANK_CANDIDATE_COUNT` | int | 15 | Количество кандидатов для reranking |
| `RERANK_MODEL_NAME` | str | cross-encoder/ms-marco-MiniLM-L-6-v2 | Модель для reranking |
| `RERANK_SCORE_THRESHOLD` | float | 0.0 | Минимальный score после reranking |

**Режимы RAG:**
- **Disabled:** `RAG_THRESHOLD = 0` или очень высокое значение (> 0.99)
- **Basic:** `RERANK_ENABLED = false`
- **Advanced:** `RERANK_ENABLED = true`

---

### 1.4 Cache Backend (Кеширование)

**Параметр:** `CACHE_BACKEND`
**Допустимые значения:** `memory`, `redis`

| Значение | Описание | Требования |
|----------|----------|------------|
| `memory` | In-memory кеш (LRU) | Нет |
| `redis` | Redis для distributed кеширования | REDIS_URL или REDIS_HOST:REDIS_PORT |

**Дополнительные параметры:**
- `CACHE_TTL` (int, default: 3600) - Time to live в секундах
- `CACHE_MAX_SIZE` (int, default: 10000) - Максимум items в memory cache

---

### 1.5 Vector DB Provider (База векторов)

**Параметр:** `VECTOR_DB_PROVIDER`
**Допустимые значения:** `chroma`, `qdrant`

| Значение | Описание | Требования |
|----------|----------|------------|
| `chroma` | ChromaDB (embedded или client-server) | VECTOR_DB_PATH |
| `qdrant` | Qdrant (embedded или cloud) | QDRANT_PATH или QDRANT_HOST:QDRANT_PORT |

**Конфигурация ChromaDB:**
- `VECTOR_DB_PATH` (Path, default: ./data/indexes/chroma)

**Конфигурация Qdrant:**
- `QDRANT_PATH` (Path, default: ./data/indexes/qdrant) - для embedded
- `QDRANT_HOST` (str) - для remote
- `QDRANT_PORT` (int) - для remote
- `QDRANT_API_KEY` (str, optional) - для cloud

---

### 1.6 LLM Roles (Роли языковых моделей)

**Описание:** Система поддерживает до 3 различных LLM для разных задач

#### Main LLM (Основная модель)
**Параметры:** `MAIN_LLM_*`

Используется для генерации основных ответов пользователю.

- `MAIN_LLM_API_KEY` (required)
- `MAIN_LLM_API_BASE` (default: https://openrouter.ai/api/v1)
- `MAIN_LLM_MODEL` (required)
- `MAIN_LLM_TEMPERATURE` (default: 0.7)
- `MAIN_LLM_MAX_TOKENS` (default: 2000)

#### Safety LLM (Модель безопасности)
**Параметры:** `SAFETY_LLM_*`

Используется для санитизации контента в режимах `external` и `hybrid`.

- `SAFETY_LLM_API_KEY` (required для external/hybrid)
- `SAFETY_LLM_API_BASE` (optional)
- `SAFETY_LLM_MODEL` (required для external/hybrid)
- `SAFETY_LLM_TEMPERATURE` (default: 0.1)
- `SAFETY_LLM_MAX_TOKENS` (default: 1000)

#### Scoring LLM (Модель оценки)
**Параметры:** `SCORING_LLM_*`

**Статус:** Зарезервирован для будущих функций (ground truth annotation, качество)

- `SCORING_LLM_API_KEY` (optional)
- `SCORING_LLM_API_BASE` (optional)
- `SCORING_LLM_MODEL` (optional)
- `SCORING_LLM_TEMPERATURE` (default: 0.0)
- `SCORING_LLM_MAX_TOKENS` (default: 10)

**Комбинации LLM:**
1. **Main only:** Только основная модель (SAFETY_MODE = disabled)
2. **Main + Safety:** Основная + модель безопасности (SAFETY_MODE = external/local/hybrid)
3. **Main + Safety + Scoring:** Все три модели (для future features)

---

### 1.7 Filter Components (Компоненты фильтрации)

**Описание:** Система фильтрации состоит из 4 основных компонентов, каждый из которых можно включить/выключить

| Компонент | Описание | Управление | Default |
|-----------|----------|------------|---------|
| **Vector Rules** | Vector search по правилам | Всегда включен | ON |
| **Prompt Modification** | Модификация prompt при matches | `use_linked_docs` в API | ON |
| **Safety LLM** | LLM санитизация контента | `SAFETY_MODE` | Depends |
| **Output Cleaning** | Очистка system prompts из output | Всегда включен для output | ON |

**Примечание:** Vector Rules всегда включен как базовая функциональность AVI.

---

### 1.8 Monitoring & Observability (Мониторинг)

**Параметры мониторинга:**

| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `PROMETHEUS_ENABLED` | bool | true | Prometheus метрики |
| `OTEL_ENABLED` | bool | false | OpenTelemetry tracing |
| `ENABLE_MLFLOW` | bool | false | MLflow эксперименты |
| `ENABLE_WANDB` | bool | false | Weights & Biases |

**Комбинации мониторинга:**
- **Basic:** Только Prometheus
- **Advanced:** Prometheus + OpenTelemetry
- **Research:** Prometheus + MLflow + W&B

---

### 1.9 Rate Limiting (Ограничение скорости)

**Параметры:**

| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `RATE_LIMIT_ENABLED` | bool | true | Включить rate limiting |
| `RATE_LIMIT_DEFAULT` | str | "100/minute" | Default лимит |
| `RATE_LIMIT_QUERY` | str | "30/minute" | Лимит для query endpoints |
| `RATE_LIMIT_UPLOAD` | str | "10/minute" | Лимит для upload endpoints |

**Backend для rate limiting:**
- **In-memory:** Без REDIS_URL (для single instance)
- **Distributed:** С REDIS_URL (для multi-instance)

---

## 2. Матрица валидных комбинаций

### 2.1 Основные комбинации по назначению

Ниже представлена матрица основных конфигураций, упорядоченных по use case.

| # | Название | Safety Mode | Stream Guard | RAG | Cache | Vector DB | LLM Roles | Use Case |
|---|----------|-------------|--------------|-----|-------|-----------|-----------|----------|
| 1 | **Minimal** | disabled | bypass | basic | memory | chroma | main | Dev/Testing |
| 2 | **Lightweight** | local | rule-only | basic | memory | chroma | main+safety | Low-risk prod |
| 3 | **Recommended** | hybrid | hybrid | advanced | redis | chroma | main+safety | Production |
| 4 | **High-Security** | external | hybrid | advanced | redis | qdrant | main+safety | High-risk prod |
| 5 | **High-Performance** | disabled | bypass | disabled | redis | chroma | main | Max throughput |
| 6 | **Balanced** | hybrid | hybrid | advanced | memory | chroma | main+safety | Medium prod |
| 7 | **Research** | hybrid | hybrid | advanced | redis | qdrant | main+safety+scoring | Experiments |
| 8 | **Cloud-Native** | external | hybrid | advanced | redis | qdrant | main+safety | Cloud deployment |

---

## 3. Предопределенные конфигурации

### 3.1 Minimal Configuration

**Use Case:** Разработка, локальное тестирование, минимальные зависимости

**Характеристики:**
- Минимальное потребление ресурсов
- Быстрая настройка (< 5 минут)
- Не требует внешних сервисов
- Подходит для ознакомления с системой

**Конфигурация:**
```json
{
  "name": "minimal",
  "description": "Минимальная конфигурация для разработки и тестирования",

  "safety": {
    "SAFETY_MODE": "disabled",
    "STREAM_GUARD_MODE": "bypass"
  },

  "rag": {
    "RAG_THRESHOLD": 0.75,
    "RERANK_ENABLED": false,
    "RERANK_CANDIDATE_COUNT": 5
  },

  "cache": {
    "CACHE_BACKEND": "memory",
    "CACHE_TTL": 3600,
    "CACHE_MAX_SIZE": 1000
  },

  "vector_db": {
    "VECTOR_DB_PROVIDER": "chroma",
    "VECTOR_DB_PATH": "./data/indexes/chroma"
  },

  "llm": {
    "roles": ["main"]
  },

  "monitoring": {
    "PROMETHEUS_ENABLED": true,
    "OTEL_ENABLED": false,
    "ENABLE_MLFLOW": false,
    "ENABLE_WANDB": false
  },

  "rate_limiting": {
    "RATE_LIMIT_ENABLED": false
  }
}
```

**Performance Characteristics:**
- Latency overhead: ~10-50ms (только vector search)
- Memory footprint: ~500MB - 1GB
- CPU: 1-2 cores
- Throughput: ~50-100 req/min

**Минимальные требования:**
- CPU: 2 cores
- RAM: 2GB
- Disk: 5GB
- Network: Нет требований для внешних сервисов

**Недостатки:**
- ❌ Нет LLM-based санитизации
- ❌ Нет защиты streaming ответов
- ❌ Нет reranking для RAG
- ⚠️ Кеш не распределенный (single instance only)

---

### 3.2 Lightweight Configuration

**Use Case:** Production среда с низким риском, небольшая нагрузка

**Характеристики:**
- Базовая защита через local safety service
- Умеренное потребление ресурсов
- Подходит для internal tools, low-risk приложений
- Можно запустить на одном сервере

**Конфигурация:**
```json
{
  "name": "lightweight",
  "description": "Легковесная конфигурация для production с низким риском",

  "safety": {
    "SAFETY_MODE": "local",
    "STREAM_GUARD_MODE": "rule-only",
    "SAFETY_SERVICE_URL": "http://localhost:8001"
  },

  "rag": {
    "RAG_THRESHOLD": 0.75,
    "RERANK_ENABLED": false,
    "RERANK_CANDIDATE_COUNT": 10
  },

  "cache": {
    "CACHE_BACKEND": "memory",
    "CACHE_TTL": 3600,
    "CACHE_MAX_SIZE": 5000
  },

  "vector_db": {
    "VECTOR_DB_PROVIDER": "chroma",
    "VECTOR_DB_PATH": "./data/indexes/chroma"
  },

  "llm": {
    "roles": ["main", "safety"]
  },

  "monitoring": {
    "PROMETHEUS_ENABLED": true,
    "OTEL_ENABLED": false,
    "ENABLE_MLFLOW": false,
    "ENABLE_WANDB": false
  },

  "rate_limiting": {
    "RATE_LIMIT_ENABLED": true,
    "RATE_LIMIT_DEFAULT": "100/minute",
    "RATE_LIMIT_QUERY": "30/minute"
  }
}
```

**Performance Characteristics:**
- Latency overhead: ~10-50ms (vector rules только)
- Memory footprint: ~1-2GB
- CPU: 2-4 cores
- Throughput: ~30-50 req/min

**Минимальные требования:**
- CPU: 2 cores
- RAM: 4GB
- Disk: 10GB
- Network: Доступ к safety service

**Преимущества:**
- ✅ Базовая LLM санитизация
- ✅ Быстрая проверка streaming
- ✅ Низкая latency

**Недостатки:**
- ⚠️ При нарушении правил streaming останавливается (может быть слишком строго)
- ⚠️ Нет fallback для safety service
- ⚠️ Кеш не распределенный

---

### 3.3 Recommended Configuration

**Use Case:** Production среда, стандартная безопасность, distributed deployment

**Характеристики:**
- Hybrid safety mode с fallback
- Полная защита streaming через hybrid guard
- Reranking для лучшей RAG точности
- Redis для distributed кеширования
- Рекомендуется для большинства production deployments

**Конфигурация:**
```json
{
  "name": "recommended",
  "description": "Рекомендуемая конфигурация для production развертывания",

  "safety": {
    "SAFETY_MODE": "hybrid",
    "STREAM_GUARD_MODE": "hybrid",
    "SAFETY_SERVICE_URL": "http://safety-service:8001",
    "SAFETY_LLM_API_KEY": "${SAFETY_LLM_API_KEY}",
    "SAFETY_LLM_MODEL": "anthropic/claude-3-haiku-20240307"
  },

  "rag": {
    "RAG_THRESHOLD": 0.75,
    "RERANK_ENABLED": true,
    "RERANK_CANDIDATE_COUNT": 15,
    "RERANK_SCORE_THRESHOLD": 0.0
  },

  "cache": {
    "CACHE_BACKEND": "redis",
    "CACHE_TTL": 3600,
    "REDIS_URL": "redis://redis:6379/0"
  },

  "vector_db": {
    "VECTOR_DB_PROVIDER": "chroma",
    "VECTOR_DB_PATH": "./data/indexes/chroma"
  },

  "llm": {
    "roles": ["main", "safety"],
    "MAIN_LLM_MODEL": "anthropic/claude-3-5-sonnet-20241022",
    "SAFETY_LLM_MODEL": "anthropic/claude-3-haiku-20240307"
  },

  "monitoring": {
    "PROMETHEUS_ENABLED": true,
    "OTEL_ENABLED": true,
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://tempo:4318/v1/traces",
    "ENABLE_MLFLOW": false,
    "ENABLE_WANDB": false
  },

  "rate_limiting": {
    "RATE_LIMIT_ENABLED": true,
    "RATE_LIMIT_DEFAULT": "100/minute",
    "RATE_LIMIT_QUERY": "30/minute",
    "REDIS_URL": "redis://redis:6379/0"
  },

  "filter_components": {
    "vector_rules": true,
    "prompt_modification": true,
    "safety_llm": true,
    "output_cleaning": true
  }
}
```

**Performance Characteristics:**
- Latency overhead: ~110-550ms (с LLM санитизацией)
- Memory footprint: ~2-4GB
- CPU: 4-8 cores
- Throughput: ~20-40 req/min (зависит от LLM API)

**Требования:**
- CPU: 4 cores
- RAM: 8GB
- Disk: 20GB SSD
- Network:
  - Доступ к safety service
  - Доступ к LLM API (OpenRouter/OpenAI)
  - Доступ к Redis

**Внешние зависимости:**
- Redis server
- Local safety service (опционально, с fallback)
- LLM API (OpenRouter, OpenAI, etc.)
- Tempo для tracing (опционально)

**Преимущества:**
- ✅ Высокая надежность (fallback safety)
- ✅ Distributed кеширование
- ✅ Лучшая RAG точность (reranking)
- ✅ Полная защита streaming
- ✅ Tracing для debugging

---

### 3.4 High-Security Configuration

**Use Case:** Production с высокими требованиями к безопасности (финансы, здравоохранение)

**Характеристики:**
- Только external LLM (без local fallback для консистентности)
- Hybrid streaming guard
- Qdrant для production-grade vector search
- Все компоненты фильтрации включены
- Строгие thresholds

**Конфигурация:**
```json
{
  "name": "high-security",
  "description": "Конфигурация для высоких требований к безопасности",

  "safety": {
    "SAFETY_MODE": "external",
    "STREAM_GUARD_MODE": "hybrid",
    "SAFETY_LLM_API_KEY": "${SAFETY_LLM_API_KEY}",
    "SAFETY_LLM_MODEL": "anthropic/claude-3-5-sonnet-20241022",
    "SAFETY_LLM_TEMPERATURE": 0.0
  },

  "rag": {
    "RAG_THRESHOLD": 0.80,
    "RERANK_ENABLED": true,
    "RERANK_CANDIDATE_COUNT": 20,
    "RERANK_SCORE_THRESHOLD": 0.3
  },

  "cache": {
    "CACHE_BACKEND": "redis",
    "CACHE_TTL": 1800,
    "REDIS_URL": "redis://redis:6379/0"
  },

  "vector_db": {
    "VECTOR_DB_PROVIDER": "qdrant",
    "QDRANT_HOST": "qdrant",
    "QDRANT_PORT": 6333,
    "QDRANT_API_KEY": "${QDRANT_API_KEY}"
  },

  "llm": {
    "roles": ["main", "safety"],
    "MAIN_LLM_MODEL": "anthropic/claude-3-5-sonnet-20241022",
    "MAIN_LLM_TEMPERATURE": 0.3,
    "SAFETY_LLM_MODEL": "anthropic/claude-3-5-sonnet-20241022",
    "SAFETY_LLM_TEMPERATURE": 0.0
  },

  "thresholds": {
    "FILTER_DEFAULT_THRESHOLD": 0.70,
    "FILTER_FALLBACK_THRESHOLD": 0.60,
    "VECTOR_SEARCH_TOP_K": 15,
    "VECTOR_SEARCH_SIMILARITY_MIN": 0.4
  },

  "monitoring": {
    "PROMETHEUS_ENABLED": true,
    "OTEL_ENABLED": true,
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://tempo:4318/v1/traces",
    "ENABLE_MLFLOW": true,
    "MLFLOW_TRACKING_URI": "http://mlflow:5000",
    "ENABLE_WANDB": false
  },

  "rate_limiting": {
    "RATE_LIMIT_ENABLED": true,
    "RATE_LIMIT_DEFAULT": "50/minute",
    "RATE_LIMIT_QUERY": "20/minute",
    "RATE_LIMIT_UPLOAD": "5/minute",
    "REDIS_URL": "redis://redis:6379/0"
  },

  "filter_components": {
    "vector_rules": true,
    "prompt_modification": true,
    "safety_llm": true,
    "output_cleaning": true
  }
}
```

**Performance Characteristics:**
- Latency overhead: ~150-700ms (консервативная LLM санитизация)
- Memory footprint: ~3-6GB
- CPU: 8+ cores
- Throughput: ~10-20 req/min (агрессивная фильтрация)

**Требования:**
- CPU: 8 cores
- RAM: 16GB
- Disk: 50GB SSD
- Network:
  - Доступ к LLM API
  - Доступ к Qdrant
  - Доступ к Redis
  - Доступ к MLflow

**Внешние зависимости:**
- Redis server
- Qdrant server
- LLM API (предпочтительно Claude для safety)
- MLflow для метрик
- Tempo для tracing

**Преимущества:**
- ✅ Максимальная защита
- ✅ Консистентная LLM санитизация
- ✅ Production-grade vector DB
- ✅ Детальный мониторинг
- ✅ Строгие rate limits

**Недостатки:**
- ⚠️ Высокая latency
- ⚠️ Низкий throughput
- ⚠️ Высокая стоимость (LLM API calls)
- ⚠️ Много внешних зависимостей

---

### 3.5 High-Performance Configuration

**Use Case:** Максимальный throughput, low-latency требования, low-risk среда

**Характеристики:**
- Минимальная фильтрация (только vector rules)
- Нет streaming guard
- RAG отключен для скорости
- Redis кеширование для масштабирования
- Оптимизирован для latency

**Конфигурация:**
```json
{
  "name": "high-performance",
  "description": "Конфигурация для максимального throughput и минимальной latency",

  "safety": {
    "SAFETY_MODE": "disabled",
    "STREAM_GUARD_MODE": "bypass"
  },

  "rag": {
    "RAG_THRESHOLD": 0.99,
    "RERANK_ENABLED": false,
    "RAG_CANDIDATE_COUNT": 3
  },

  "cache": {
    "CACHE_BACKEND": "redis",
    "CACHE_TTL": 7200,
    "CACHE_MAX_SIZE": 50000,
    "REDIS_URL": "redis://redis:6379/0"
  },

  "vector_db": {
    "VECTOR_DB_PROVIDER": "chroma",
    "VECTOR_DB_PATH": "./data/indexes/chroma"
  },

  "llm": {
    "roles": ["main"],
    "MAIN_LLM_MODEL": "anthropic/claude-3-haiku-20240307",
    "MAIN_LLM_MAX_TOKENS": 1000
  },

  "thresholds": {
    "FILTER_DEFAULT_THRESHOLD": 0.65,
    "VECTOR_SEARCH_TOP_K": 5,
    "VECTOR_SEARCH_SIMILARITY_MIN": 0.5
  },

  "monitoring": {
    "PROMETHEUS_ENABLED": true,
    "OTEL_ENABLED": false,
    "ENABLE_MLFLOW": false,
    "ENABLE_WANDB": false
  },

  "rate_limiting": {
    "RATE_LIMIT_ENABLED": true,
    "RATE_LIMIT_DEFAULT": "500/minute",
    "RATE_LIMIT_QUERY": "200/minute",
    "REDIS_URL": "redis://redis:6379/0"
  },

  "filter_components": {
    "vector_rules": true,
    "prompt_modification": true,
    "safety_llm": false,
    "output_cleaning": true
  }
}
```

**Performance Characteristics:**
- Latency overhead: ~10-30ms (минимальная фильтрация)
- Memory footprint: ~2-3GB
- CPU: 4-8 cores
- Throughput: ~100-200 req/min

**Требования:**
- CPU: 4 cores
- RAM: 8GB
- Disk: 20GB SSD
- Network:
  - Доступ к Redis
  - Доступ к fast LLM API

**Преимущества:**
- ✅ Минимальная latency
- ✅ Максимальный throughput
- ✅ Низкая стоимость (меньше LLM calls)
- ✅ Distributed кеширование

**Недостатки:**
- ❌ Минимальная защита
- ❌ Нет RAG документов
- ❌ Не подходит для high-risk сценариев

**Рекомендуется для:**
- Internal tools
- Chatbots с низким риском
- Demo приложения
- Load testing

---

### 3.6 Balanced Configuration

**Use Case:** Средний production, баланс между безопасностью и производительностью

**Характеристики:**
- Hybrid safety для надежности
- Hybrid streaming guard
- Reranking включен
- Memory кеш (для single instance)
- Умеренная latency

**Конфигурация:**
```json
{
  "name": "balanced",
  "description": "Сбалансированная конфигурация для среднего production",

  "safety": {
    "SAFETY_MODE": "hybrid",
    "STREAM_GUARD_MODE": "hybrid",
    "SAFETY_SERVICE_URL": "http://safety-service:8001",
    "SAFETY_LLM_API_KEY": "${SAFETY_LLM_API_KEY}",
    "SAFETY_LLM_MODEL": "anthropic/claude-3-haiku-20240307"
  },

  "rag": {
    "RAG_THRESHOLD": 0.75,
    "RERANK_ENABLED": true,
    "RERANK_CANDIDATE_COUNT": 15
  },

  "cache": {
    "CACHE_BACKEND": "memory",
    "CACHE_TTL": 3600,
    "CACHE_MAX_SIZE": 10000
  },

  "vector_db": {
    "VECTOR_DB_PROVIDER": "chroma",
    "VECTOR_DB_PATH": "./data/indexes/chroma"
  },

  "llm": {
    "roles": ["main", "safety"],
    "MAIN_LLM_MODEL": "anthropic/claude-3-5-sonnet-20241022",
    "SAFETY_LLM_MODEL": "anthropic/claude-3-haiku-20240307"
  },

  "thresholds": {
    "FILTER_DEFAULT_THRESHOLD": 0.60,
    "FILTER_FALLBACK_THRESHOLD": 0.50,
    "VECTOR_SEARCH_TOP_K": 10
  },

  "monitoring": {
    "PROMETHEUS_ENABLED": true,
    "OTEL_ENABLED": false,
    "ENABLE_MLFLOW": false,
    "ENABLE_WANDB": false
  },

  "rate_limiting": {
    "RATE_LIMIT_ENABLED": true,
    "RATE_LIMIT_DEFAULT": "100/minute",
    "RATE_LIMIT_QUERY": "30/minute"
  },

  "filter_components": {
    "vector_rules": true,
    "prompt_modification": true,
    "safety_llm": true,
    "output_cleaning": true
  }
}
```

**Performance Characteristics:**
- Latency overhead: ~80-400ms (hybrid mode)
- Memory footprint: ~2-4GB
- CPU: 4 cores
- Throughput: ~25-50 req/min

**Требования:**
- CPU: 4 cores
- RAM: 8GB
- Disk: 20GB
- Network: Доступ к safety service и LLM API

**Преимущества:**
- ✅ Хороший баланс security/performance
- ✅ Fallback safety
- ✅ Reranking для точности
- ✅ Не требует Redis

**Подходит для:**
- Medium traffic production
- Single instance deployment
- MVP products
- Small team projects

---

### 3.7 Research Configuration

**Use Case:** Эксперименты, метрики, ground truth annotation

**Характеристики:**
- Все три LLM роли (main + safety + scoring)
- Полный мониторинг (MLflow + W&B)
- Qdrant для экспериментов
- Все компоненты фильтрации
- Детальные метрики

**Конфигурация:**
```json
{
  "name": "research",
  "description": "Конфигурация для исследований и экспериментов",

  "safety": {
    "SAFETY_MODE": "hybrid",
    "STREAM_GUARD_MODE": "hybrid",
    "SAFETY_SERVICE_URL": "http://safety-service:8001",
    "SAFETY_LLM_API_KEY": "${SAFETY_LLM_API_KEY}",
    "SAFETY_LLM_MODEL": "anthropic/claude-3-5-sonnet-20241022"
  },

  "rag": {
    "RAG_THRESHOLD": 0.75,
    "RERANK_ENABLED": true,
    "RERANK_CANDIDATE_COUNT": 20,
    "RERANK_SCORE_THRESHOLD": 0.0
  },

  "cache": {
    "CACHE_BACKEND": "redis",
    "CACHE_TTL": 3600,
    "REDIS_URL": "redis://redis:6379/0"
  },

  "vector_db": {
    "VECTOR_DB_PROVIDER": "qdrant",
    "QDRANT_HOST": "qdrant",
    "QDRANT_PORT": 6333
  },

  "llm": {
    "roles": ["main", "safety", "scoring"],
    "MAIN_LLM_MODEL": "anthropic/claude-3-5-sonnet-20241022",
    "SAFETY_LLM_MODEL": "anthropic/claude-3-5-sonnet-20241022",
    "SCORING_LLM_API_KEY": "${SCORING_LLM_API_KEY}",
    "SCORING_LLM_MODEL": "anthropic/claude-3-5-sonnet-20241022"
  },

  "monitoring": {
    "PROMETHEUS_ENABLED": true,
    "OTEL_ENABLED": true,
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://tempo:4318/v1/traces",
    "ENABLE_MLFLOW": true,
    "MLFLOW_TRACKING_URI": "http://mlflow:5000",
    "MLFLOW_EXPERIMENT_NAME": "avi_research",
    "ENABLE_WANDB": true,
    "WANDB_PROJECT": "avi-research",
    "WANDB_ENTITY": "${WANDB_ENTITY}"
  },

  "rate_limiting": {
    "RATE_LIMIT_ENABLED": false
  },

  "filter_components": {
    "vector_rules": true,
    "prompt_modification": true,
    "safety_llm": true,
    "output_cleaning": true
  }
}
```

**Performance Characteristics:**
- Latency overhead: ~150-800ms (полный мониторинг)
- Memory footprint: ~4-8GB
- CPU: 8+ cores
- Throughput: ~10-20 req/min

**Требования:**
- CPU: 8 cores
- RAM: 16GB
- Disk: 100GB SSD
- Network:
  - Доступ к всем LLM APIs
  - Доступ к Qdrant, Redis, MLflow, W&B

**Преимущества:**
- ✅ Полный набор метрик
- ✅ Scoring LLM для ground truth
- ✅ Эксперименты с разными моделями
- ✅ Визуализация в W&B

**Рекомендуется для:**
- ML research
- A/B testing
- Model evaluation
- Ground truth generation

---

### 3.8 Cloud-Native Configuration

**Use Case:** Cloud deployment (AWS, GCP, Azure), автоматическое масштабирование

**Характеристики:**
- External LLM (облачные API)
- Qdrant cloud
- Redis cloud
- Distributed всё
- High availability

**Конфигурация:**
```json
{
  "name": "cloud-native",
  "description": "Конфигурация для облачного развертывания",

  "safety": {
    "SAFETY_MODE": "external",
    "STREAM_GUARD_MODE": "hybrid",
    "SAFETY_LLM_API_KEY": "${SAFETY_LLM_API_KEY}",
    "SAFETY_LLM_MODEL": "anthropic/claude-3-haiku-20240307"
  },

  "rag": {
    "RAG_THRESHOLD": 0.75,
    "RERANK_ENABLED": true,
    "RERANK_CANDIDATE_COUNT": 15
  },

  "cache": {
    "CACHE_BACKEND": "redis",
    "CACHE_TTL": 3600,
    "REDIS_URL": "${REDIS_CLOUD_URL}"
  },

  "vector_db": {
    "VECTOR_DB_PROVIDER": "qdrant",
    "QDRANT_HOST": "${QDRANT_CLOUD_URL}",
    "QDRANT_PORT": 6333,
    "QDRANT_API_KEY": "${QDRANT_CLOUD_API_KEY}"
  },

  "llm": {
    "roles": ["main", "safety"],
    "MAIN_LLM_API_BASE": "https://api.anthropic.com",
    "MAIN_LLM_MODEL": "claude-3-5-sonnet-20241022",
    "SAFETY_LLM_API_BASE": "https://api.anthropic.com",
    "SAFETY_LLM_MODEL": "claude-3-haiku-20240307"
  },

  "monitoring": {
    "PROMETHEUS_ENABLED": true,
    "OTEL_ENABLED": true,
    "OTEL_EXPORTER_OTLP_ENDPOINT": "${OTEL_ENDPOINT}",
    "ENABLE_MLFLOW": false,
    "ENABLE_WANDB": false
  },

  "rate_limiting": {
    "RATE_LIMIT_ENABLED": true,
    "RATE_LIMIT_DEFAULT": "200/minute",
    "RATE_LIMIT_QUERY": "50/minute",
    "REDIS_URL": "${REDIS_CLOUD_URL}"
  },

  "environment": {
    "ENVIRONMENT": "production",
    "DEBUG": false,
    "REQUIRE_API_KEY": true
  }
}
```

**Performance Characteristics:**
- Latency overhead: ~120-600ms
- Auto-scaling на основе load
- Throughput: Зависит от scaling

**Cloud Services:**
- **AWS:** ECS/EKS + ElastiCache + Managed Qdrant
- **GCP:** GKE + Memorystore + Managed Qdrant
- **Azure:** AKS + Azure Cache + Managed Qdrant

**Преимущества:**
- ✅ Auto-scaling
- ✅ High availability
- ✅ Managed services
- ✅ Easy deployment

---

## 4. Сравнительная таблица

### 4.1 Безопасность vs Производительность

| Конфигурация | Security Level | Latency (ms) | Throughput (req/min) | Cost | Complexity |
|--------------|----------------|--------------|----------------------|------|------------|
| Minimal | ⭐ Low | 10-50 | 50-100 | $ | ⭐ Simple |
| Lightweight | ⭐⭐ Medium-Low | 10-50 | 30-50 | $$ | ⭐⭐ Easy |
| Recommended | ⭐⭐⭐ Medium-High | 110-550 | 20-40 | $$$ | ⭐⭐⭐ Medium |
| High-Security | ⭐⭐⭐⭐ Very High | 150-700 | 10-20 | $$$$ | ⭐⭐⭐⭐ Complex |
| High-Performance | ⭐ Very Low | 10-30 | 100-200 | $$ | ⭐⭐ Easy |
| Balanced | ⭐⭐⭐ Medium | 80-400 | 25-50 | $$$ | ⭐⭐⭐ Medium |
| Research | ⭐⭐⭐ Medium-High | 150-800 | 10-20 | $$$$$ | ⭐⭐⭐⭐⭐ Very Complex |
| Cloud-Native | ⭐⭐⭐⭐ High | 120-600 | Auto-scale | $$$$ | ⭐⭐⭐⭐ Complex |

### 4.2 Требования к ресурсам

| Конфигурация | CPU (cores) | RAM (GB) | Disk (GB) | Network Dependencies |
|--------------|-------------|----------|-----------|---------------------|
| Minimal | 2 | 2 | 5 | Нет |
| Lightweight | 2 | 4 | 10 | Safety service |
| Recommended | 4 | 8 | 20 | Redis, Safety, LLM API, Tempo |
| High-Security | 8 | 16 | 50 | Qdrant, Redis, LLM API, MLflow |
| High-Performance | 4 | 8 | 20 | Redis, LLM API |
| Balanced | 4 | 8 | 20 | Safety, LLM API |
| Research | 8 | 16 | 100 | All services |
| Cloud-Native | Auto | Auto | Auto | All cloud services |

### 4.3 Функциональность

| Feature | Minimal | Lightweight | Recommended | High-Sec | High-Perf | Balanced | Research | Cloud |
|---------|---------|-------------|-------------|----------|-----------|----------|----------|-------|
| Vector Rules | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| LLM Safety | ❌ | ✅ Local | ✅ Hybrid | ✅ External | ❌ | ✅ Hybrid | ✅ Hybrid | ✅ External |
| Stream Guard | ❌ Bypass | ⚠️ Rule-only | ✅ Hybrid | ✅ Hybrid | ❌ Bypass | ✅ Hybrid | ✅ Hybrid | ✅ Hybrid |
| RAG Reranking | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| Distributed Cache | ❌ | ❌ | ✅ Redis | ✅ Redis | ✅ Redis | ❌ | ✅ Redis | ✅ Cloud |
| Vector DB | ChromaDB | ChromaDB | ChromaDB | Qdrant | ChromaDB | ChromaDB | Qdrant | Qdrant Cloud |
| Prometheus | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OpenTelemetry | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| MLflow | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ |
| W&B | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Rate Limiting | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |

---

## 5. Рекомендации по выбору

### 5.1 По типу приложения

#### Internal Tools / Admin Dashboards
**Рекомендуется:** `Minimal` или `Lightweight`
- Низкий риск
- Ограниченная аудитория
- Приоритет: скорость разработки

#### Customer-Facing Chatbots (Low Risk)
**Рекомендуется:** `Balanced` или `Lightweight`
- Средний риск
- Приоритет: баланс security/performance
- Нужна базовая защита

#### Customer-Facing Chatbots (High Risk)
**Рекомендуется:** `Recommended` или `High-Security`
- Высокий риск
- Приоритет: безопасность
- Нужна полная защита + fallback

#### High-Traffic APIs
**Рекомендуется:** `High-Performance` или `Cloud-Native`
- Приоритет: throughput и latency
- Можно пожертвовать некоторой безопасностью
- Auto-scaling важен

#### Financial / Healthcare Applications
**Рекомендуется:** `High-Security`
- Критичная безопасность
- Регуляторные требования
- Audit trail необходим

#### Research / ML Experiments
**Рекомендуется:** `Research`
- Нужны метрики
- A/B testing
- Model evaluation

### 5.2 По стадии развертывания

#### Development / Local Testing
**Рекомендуется:** `Minimal`
- Быстрая настройка
- Минимум зависимостей
- Можно быстро итерировать

#### Staging / QA
**Рекомендуется:** `Balanced` или `Recommended`
- Приближено к production
- Тестирование с реальными настройками
- Но можно без некоторых сервисов (MLflow, etc.)

#### Production (Small Scale)
**Рекомендуется:** `Balanced`
- До 1000 req/hour
- Single instance deployment
- Memory cache достаточно

#### Production (Medium Scale)
**Рекомендуется:** `Recommended`
- 1000-10000 req/hour
- Multi-instance deployment
- Distributed cache обязателен

#### Production (Large Scale)
**Рекомендуется:** `Cloud-Native`
- 10000+ req/hour
- Auto-scaling
- Managed services

### 5.3 По latency требованиям

#### Ultra-Low Latency (<50ms overhead)
**Рекомендуется:** `Minimal` или `High-Performance`
- Только vector search
- Нет LLM санитизации
- Подходит для real-time applications

#### Low Latency (<200ms overhead)
**Рекомендуется:** `Lightweight` или `Balanced`
- Базовая защита
- Rule-only streaming guard
- Хороший компромисс

#### Medium Latency (<500ms overhead)
**Рекомендуется:** `Recommended`
- Полная защита
- Hybrid mode
- Подходит для большинства chatbots

#### Latency Not Critical (>500ms acceptable)
**Рекомендуется:** `High-Security` или `Research`
- Максимальная защита
- Все компоненты включены
- Приоритет: качество и безопасность

### 5.4 По бюджету

#### Минимальный бюджет ($)
**Рекомендуется:** `Minimal` или `Lightweight`
- Минимум LLM API calls
- Нет облачных сервисов
- Можно запустить на одном сервере

#### Средний бюджет ($$)
**Рекомендуется:** `Balanced` или `High-Performance`
- Умеренные LLM API calls
- Некоторые managed services
- Good value for money

#### Высокий бюджет ($$$)
**Рекомендуется:** `Recommended` или `High-Security`
- Полный набор функций
- Все managed services
- Можно позволить агрессивную фильтрацию

#### Неограниченный бюджет ($$$$)
**Рекомендуется:** `Research` или `Cloud-Native`
- Все возможности включены
- Best-in-class LLMs
- Полный мониторинг

---

## 6. Автоматизированное тестирование

### 6.1 Скрипт для тестирования конфигураций

Скрипт `scripts/test_configurations.py` позволяет:
- Загружать конфигурации из JSON файлов
- Применять их к системе
- Запускать тестовые запросы
- Измерять метрики (latency, throughput, качество)
- Генерировать отчеты

**Использование:**
```bash
# Тестирование одной конфигурации
python scripts/test_configurations.py --config data/configs/recommended.json

# Тестирование всех конфигураций
python scripts/test_configurations.py --all

# Сравнение двух конфигураций
python scripts/test_configurations.py --compare minimal recommended

# Benchmark всех конфигураций
python scripts/test_configurations.py --benchmark --output results.csv
```

### 6.2 Метрики тестирования

Для каждой конфигурации измеряются:

**Performance Metrics:**
- Average latency (ms)
- P50, P95, P99 latency
- Throughput (req/min)
- Error rate (%)
- Memory usage (MB)
- CPU usage (%)

**Quality Metrics:**
- Filter accuracy (TP, FP, FN, TN)
- RAG relevance score
- Safety coverage
- False positive rate

**Cost Metrics:**
- LLM API calls per request
- Estimated cost per 1000 requests
- Resource utilization

### 6.3 Тестовые сценарии

**Сценарий 1: Basic Query**
- Простой вопрос пользователя
- Нет срабатывания правил
- Измеряем baseline latency

**Сценарий 2: Filtered Query**
- Вопрос с потенциальным нарушением
- Срабатывание правил
- Измеряем filter overhead

**Сценарий 3: RAG Query**
- Вопрос с использованием linked documents
- Измеряем RAG latency

**Сценарий 4: Streaming Response**
- Streaming ответ с guard
- Измеряем streaming overhead

**Сценарий 5: Stress Test**
- Много параллельных запросов
- Измеряем throughput и stability

---

## 7. Дополнительные комбинации

### 7.1 Специализированные конфигурации

#### Debugging Configuration
**Use Case:** Debugging, troubleshooting, development

```json
{
  "name": "debugging",
  "safety": {
    "SAFETY_MODE": "disabled",
    "STREAM_GUARD_MODE": "bypass"
  },
  "monitoring": {
    "DEBUG": true,
    "OTEL_ENABLED": true,
    "PROMETHEUS_ENABLED": true
  },
  "logging": {
    "LOG_LEVEL": "DEBUG",
    "LOG_SQL_QUERIES": true
  }
}
```

#### Demo Configuration
**Use Case:** Демонстрации, презентации

```json
{
  "name": "demo",
  "safety": {
    "SAFETY_MODE": "local",
    "STREAM_GUARD_MODE": "rule-only"
  },
  "rate_limiting": {
    "RATE_LIMIT_ENABLED": false
  },
  "cache": {
    "CACHE_BACKEND": "memory",
    "CACHE_TTL": 300
  }
}
```

#### Testing Configuration
**Use Case:** Automated testing, CI/CD

```json
{
  "name": "testing",
  "safety": {
    "SAFETY_MODE": "disabled",
    "STREAM_GUARD_MODE": "bypass"
  },
  "vector_db": {
    "VECTOR_DB_PROVIDER": "chroma",
    "VECTOR_DB_PATH": "./data/test/indexes"
  },
  "environment": {
    "ENVIRONMENT": "testing",
    "DEBUG": true
  }
}
```

### 7.2 Матрица всех возможных комбинаций

**Количество параметров:**
- Safety Mode: 4 варианта (disabled, local, external, hybrid)
- Stream Guard: 4 варианта (bypass, rule-only, llm-only, hybrid)
- RAG: 2 варианта (basic, advanced)
- Cache: 2 варианта (memory, redis)
- Vector DB: 2 варианта (chroma, qdrant)
- LLM Roles: 3 варианта (main, main+safety, main+safety+scoring)

**Общее число комбинаций:** 4 × 4 × 2 × 2 × 2 × 3 = **768 комбинаций**

**Валидных комбинаций:** ~400-500 (некоторые комбинации невозможны, например external safety без safety LLM)

**Практически используемых:** 8-15 (представленные выше предопределенные конфигурации)

---

## 8. Миграция между конфигурациями

### 8.1 Minimal → Recommended

**Шаги:**
1. Настроить Redis
2. Добавить safety LLM credentials
3. Настроить local safety service
4. Включить reranking
5. Включить OpenTelemetry

**Изменения в .env:**
```bash
# Было
SAFETY_MODE=disabled
STREAM_GUARD_MODE=bypass
CACHE_BACKEND=memory

# Стало
SAFETY_MODE=hybrid
STREAM_GUARD_MODE=hybrid
CACHE_BACKEND=redis
REDIS_URL=redis://redis:6379/0
SAFETY_SERVICE_URL=http://safety-service:8001
SAFETY_LLM_API_KEY=sk-...
SAFETY_LLM_MODEL=anthropic/claude-3-haiku-20240307
RERANK_ENABLED=true
OTEL_ENABLED=true
```

### 8.2 Recommended → High-Security

**Шаги:**
1. Переключить на Qdrant
2. Ужесточить thresholds
3. Добавить MLflow
4. Увеличить resources
5. Включить stricter rate limits

**Изменения:**
```bash
# Vector DB
VECTOR_DB_PROVIDER=qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# Thresholds
FILTER_DEFAULT_THRESHOLD=0.70
RAG_THRESHOLD=0.80
RERANK_SCORE_THRESHOLD=0.3

# Monitoring
ENABLE_MLFLOW=true
MLFLOW_TRACKING_URI=http://mlflow:5000

# Rate limiting
RATE_LIMIT_QUERY=20/minute
```

---

## 9. Выводы и рекомендации

### 9.1 Ключевые выводы

1. **Не существует универсальной конфигурации** - выбор зависит от use case, требований, бюджета

2. **Безопасность vs Производительность** - всегда есть trade-off, нужно найти баланс

3. **Начинайте с Minimal/Balanced** - затем масштабируйте по мере необходимости

4. **Production требует Hybrid mode** - для надежности и fallback

5. **High-Performance не означает небезопасный** - vector rules всё равно работают

### 9.2 Best Practices

1. **Development:** Используйте Minimal для быстрых итераций
2. **Staging:** Используйте ту же конфигурацию, что и в Production
3. **Production:** Начните с Recommended, адаптируйте под свои нужды
4. **Мониторинг:** Всегда включайте Prometheus, даже в dev
5. **Тестирование:** Тестируйте конфигурации перед deployment
6. **Документация:** Документируйте свою финальную конфигурацию
7. **Миграция:** Планируйте миграцию заранее, тестируйте на staging

### 9.3 Дальнейшие шаги

1. Создать JSON файлы для каждой предопределенной конфигурации ✅
2. Реализовать скрипт автоматического тестирования ✅
3. Провести benchmark всех конфигураций
4. Документировать результаты benchmark
5. Создать CI/CD pipeline для тестирования конфигураций

---

**Версия:** 1.0
**Дата:** 2025-11-14
**Авторы:** AVI Team
**Связанные документы:**
- `REFACTORING_PLAN.md` - План рефакторинга
- `FILTER_PERFORMANCE_ANALYSIS.md` - Анализ производительности фильтров
- `DEPLOYMENT_GUIDE.md` - Руководство по развертыванию (будет создано в задаче 4.2)
- `SYSTEM_REQUIREMENTS.md` - Системные требования (будет создано в задаче 4.2)
