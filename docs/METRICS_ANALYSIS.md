# Анализ метрик системы AVI

**Дата создания:** 2025-11-13
**Версия:** 1.0
**Задача:** 1.4 из REFACTORING_PLAN.md

---

## Содержание

1. [Обзор](#обзор)
2. [Текущие метрики](#текущие-метрики)
3. [Формулы и расчеты](#формулы-и-расчеты)
4. [Предложенные новые метрики](#предложенные-новые-метрики)
5. [План имплементации](#план-имплементации)
6. [Архитектура метрик](#архитектура-метрик)

---

## Обзор

Система AVI собирает метрики на разных уровнях:
- **Content Filtering** - метрики фильтрации контента (confusion matrix, latency)
- **HTTP API** - метрики запросов (latency, throughput)
- **Cache** - метрики кеширования (hits, misses, hit rate)
- **RAG** - метрики поиска и reranking
- **Streaming** - метрики потоковой обработки

### Системы сбора метрик

AVI поддерживает три системы сбора метрик:

1. **Prometheus** - основная система для production мониторинга
   - Настройка: `PROMETHEUS_ENABLED=True`
   - Endpoint: `/metrics` (по умолчанию)
   - Namespace: `avi` (настраивается через `METRICS_NAMESPACE`)

2. **MLflow** - для ML экспериментов и tracking
   - Настройка: `ENABLE_MLFLOW=True`
   - Tracking URI: `MLFLOW_TRACKING_URI`
   - Experiment: `MLFLOW_EXPERIMENT_NAME` (default: "content_filter_metrics")

3. **Weights & Biases (W&B)** - для ML экспериментов
   - Настройка: `ENABLE_WANDB=True`
   - Project: `WANDB_PROJECT`
   - Entity: `WANDB_ENTITY`

---

## Текущие метрики

### 1. Content Filter Metrics

**Файл:** `src/monitoring/metrics.py`

#### 1.1 Confusion Matrix метрики

Отслеживают качество детекции контента по safety mode.

| Метрика | Prometheus название | Тип | Описание |
|---------|---------------------|-----|----------|
| True Positives (TP) | `avi_content_filter_true_positives_total` | Counter | Правильно обнаружен небезопасный контент |
| False Positives (FP) | `avi_content_filter_false_positives_total` | Counter | Безопасный контент ошибочно помечен как небезопасный |
| False Negatives (FN) | `avi_content_filter_false_negatives_total` | Counter | Небезопасный контент пропущен |
| True Negatives (TN) | `avi_content_filter_true_negatives_total` | Counter | Правильно определен безопасный контент |

**Labels:** `mode` (disabled, local, external, hybrid)

**Как собираются:**
```python
# В src/core/content_filter.py:check_content()
content_filter_metrics.record(
    mode=self.active_mode,
    predicted_positive=bool(result.matches),  # Система предсказала опасность
    actual_positive=ground_truth,              # Реальная метка (optional)
    detection_latency_seconds=detection_latency_seconds,
    sanitization_latency_seconds=sanitization_latency_seconds,
)
```

**Логика записи:**
- `predicted_positive=True, actual_positive=True` → TP++
- `predicted_positive=True, actual_positive=False` → FP++
- `predicted_positive=False, actual_positive=True` → FN++
- `predicted_positive=False, actual_positive=False` → TN++
- Если `actual_positive=None`, confusion matrix не обновляется

#### 1.2 Latency метрики

| Метрика | Prometheus название | Тип | Описание |
|---------|---------------------|-----|----------|
| Detection Latency | `avi_content_filter_detection_latency_seconds` | Histogram | Время на поиск совпадений с правилами в vector DB |
| Sanitization Latency | `avi_content_filter_sanitization_latency_seconds` | Histogram | Время на санитизацию через Safety LLM (optional) |

**Labels:** `mode` (disabled, local, external, hybrid)

**Как измеряются:**
```python
# Detection latency
start_time = time.perf_counter()
# ... vector search for matching rules ...
detection_latency_seconds = time.perf_counter() - start_time

# Sanitization latency (optional)
sanitization_start = time.perf_counter()
llm_response = await self._try_generate_safe_text(text, context)
sanitization_latency_seconds = time.perf_counter() - sanitization_start
```

**Важно:** Detection latency измеряется всегда, sanitization latency - только если:
- `use_llm=True`
- `result.matches` не пусто (есть совпадения)
- `self.safety_llm` доступен

#### 1.3 Component-Level метрики

Метрики для гранулярного контроля фильтрации (добавлены недавно).

| Метрика | Prometheus название | Тип | Описание |
|---------|---------------------|-----|----------|
| Component Applied | `avi_content_filter_component_applied_total` | Counter | Количество применений компонента |
| Component Modified | `avi_content_filter_component_modified_total` | Counter | Количество модификаций контента компонентом |

**Labels:**
- `component` (vector_rules, safety_llm, prompt_modification, output_cleaning)
- `stage` (input, output)

**Компоненты фильтрации:**
1. **vector_rules** - поиск совпадений с правилами через vector search
2. **safety_llm** - санитизация через Safety LLM
3. **prompt_modification** - модификация промпта при обнаружении совпадений (INPUT only)
4. **output_cleaning** - очистка вывода от system prompts (OUTPUT only)

**Как собираются:**
```python
components_applied = {
    "vector_rules": enable_vector_rules,
    "safety_llm": use_llm and self.safety_llm is not None,
    "prompt_modification": result.matches and enable_prompt_modification,
    "output_cleaning": not is_input and enable_output_cleaning,
}

content_filter_metrics.record_component_usage(
    components_applied=components_applied,
    was_modified=result.was_modified,
    is_input=is_input,
)
```

### 2. Observability Metrics

**Файл:** `src/monitoring/observability.py`

#### 2.1 HTTP Request Latency

| Метрика | Prometheus название | Тип | Описание |
|---------|---------------------|-----|----------|
| Request Latency | `avi_http_request_latency_seconds` | Histogram | Время обработки HTTP запроса |

**Labels:** `method`, `route`, `status_code`

**Как измеряется:**
```python
# В src/api/middleware.py:RequestMetricsMiddleware
start_time = time.perf_counter()
response = await call_next(request)
duration = time.perf_counter() - start_time
observe_request_latency(request.method, route, status_code, duration)
```

#### 2.2 Cache Metrics

| Метрика | Prometheus название | Тип | Описание |
|---------|---------------------|-----|----------|
| Cache Hits | `avi_cache_hits_total` | Counter | Количество cache hits |
| Cache Misses | `avi_cache_misses_total` | Counter | Количество cache misses |

**Labels:** `backend` (memory, redis)

**Как собираются:**
```python
# В src/core/cache_system.py
# При cache hit:
record_cache_hit("memory")  # или "redis"

# При cache miss:
record_cache_miss("memory")  # или "redis"
```

**Cache hit rate (расчетный):**
```python
hit_rate = (hits / (hits + misses)) * 100
```

#### 2.3 Safety Intervention Metrics

| Метрика | Prometheus название | Тип | Описание |
|---------|---------------------|-----|----------|
| Safety Interventions | `avi_safety_interventions_total` | Counter | Количество случаев модификации контента |

**Labels:** `stage` (input, output), `mode` (safety mode)

**Когда записывается:**
- При модификации контента через prompt modification (INPUT)
- При очистке output контента (OUTPUT)
- При санитизации через Safety LLM

```python
# В src/core/content_filter.py
if result.was_modified:
    record_safety_intervention(stage, self.active_mode.value)
```

#### 2.4 Rerank Latency

| Метрика | Prometheus название | Тип | Описание |
|---------|---------------------|-----|----------|
| Rerank Latency | `avi_rerank_latency_seconds` | Histogram | Время на reranking документов |

**Labels:** `model` (название cross-encoder модели)

**Как измеряется:**
```python
# В src/services/reranker.py:rerank()
start_time = perf_counter()
# ... cross-encoder scoring ...
elapsed = perf_counter() - start_time
observe_rerank_latency(self.model_name, elapsed)
```

### 3. Streaming Guard Metrics

**Файл:** `src/core/streaming_guard.py`

Эти метрики собираются в памяти и возвращаются в ответе, но **не экспортируются в Prometheus**.

| Метрика | Поле в StreamingGuardMetrics | Описание |
|---------|------------------------------|----------|
| Processed Chunks | `processed_chunks` | Всего обработано чанков |
| Flagged Chunks | `flagged_chunks` | Помечено как опасные |
| Sanitized Chunks | `sanitized_chunks` | Санитизировано через LLM |
| Blocked Chunks | `blocked_chunks` | Заблокировано (не отправлено клиенту) |
| LLM Calls | `llm_calls` | Количество вызовов Safety LLM |

**Как собираются:**
```python
# В StreamingGuard
self.metrics.processed_chunks += 1
if decision.filtered:
    self.metrics.flagged_chunks += 1
# и т.д.
```

### 4. In-Memory Statistics

Некоторые статистики хранятся только в памяти и доступны через API:

#### 4.1 Content Filter In-Memory Stats

```python
# Доступно через content_filter_metrics.snapshot()
{
    "mode_name": {
        "true_positive": 10,
        "false_positive": 2,
        "false_negative": 1,
        "true_negative": 100,
        "detection_latency": {
            "count": 113,
            "total": 5.67,
            "min": 0.012,
            "max": 0.234,
            "avg": 0.050
        },
        "sanitization_latency": {...}
    }
}
```

#### 4.2 Cache Stats

```python
# Доступно через cache.get_stats()
{
    "size": 512,          # Количество записей в кеше
    "hits": 340,          # Количество cache hits
    "misses": 120,        # Количество cache misses
    "hit_rate": 73.9      # Hit rate в процентах
}
```

---

## Формулы и расчеты

### Confusion Matrix метрики

#### Precision (точность)
Доля правильно определенных положительных случаев среди всех положительных предсказаний.

```
Precision = TP / (TP + FP)
```

**Интерпретация:** Если Precision = 0.9, то 90% случаев, которые система пометила как опасные, действительно опасны.

#### Recall (полнота, чувствительность)
Доля правильно обнаруженных положительных случаев среди всех реальных положительных.

```
Recall = TP / (TP + FN)
```

**Интерпретация:** Если Recall = 0.85, то система обнаруживает 85% всех опасных случаев.

#### F1-Score
Гармоническое среднее между Precision и Recall.

```
F1 = 2 * (Precision * Recall) / (Precision + Recall)
```

**Интерпретация:** Балансирует между точностью и полнотой.

#### Accuracy (точность классификации)
Доля правильных предсказаний (как положительных, так и отрицательных).

```
Accuracy = (TP + TN) / (TP + TN + FP + FN)
```

#### False Positive Rate (FPR)
Доля ложных срабатываний среди всех отрицательных случаев.

```
FPR = FP / (FP + TN)
```

**Важно:** Высокий FPR означает много ложных тревог, что ухудшает user experience.

#### False Negative Rate (FNR)
Доля пропущенных опасных случаев.

```
FNR = FN / (FN + TP)
```

**Важно:** Высокий FNR означает, что система пропускает опасный контент.

### Latency метрики

#### Average Latency
```
Average = Total Time / Count
```

#### Percentiles
Prometheus Histogram автоматически вычисляет percentiles (p50, p90, p95, p99):
- **p50 (median):** 50% запросов быстрее этого значения
- **p90:** 90% запросов быстрее этого значения
- **p99:** 99% запросов быстрее этого значения

#### Latency Distribution
Histogram buckets позволяют построить распределение latency.

### Cache метрики

#### Hit Rate
```
Hit Rate = (Hits / (Hits + Misses)) * 100%
```

**Интерпретация:** Если Hit Rate = 80%, то 80% запросов обслуживаются из кеша.

#### Miss Rate
```
Miss Rate = (Misses / (Hits + Misses)) * 100%
```

#### Cache Effectiveness (влияние на latency)
```
Average Latency without Cache = L_miss
Average Latency with Cache = (Hits * L_hit + Misses * L_miss) / (Hits + Misses)

Speedup = L_miss / Average Latency with Cache
```

### Throughput метрики

#### Requests per Second (RPS)
```
RPS = Total Requests / Time Period (seconds)
```

#### Average Processing Time
```
Average Processing Time = Total Processing Time / Total Requests
```

### Component Performance

#### Component Overhead
```
Component Overhead = (Total Latency with Component - Total Latency without Component) / Total Requests
```

#### Component Modification Rate
```
Modification Rate = (Modifications / Applications) * 100%
```

---

## Предложенные новые метрики

### 1. Derived Confusion Matrix Metrics

**Приоритет:** Высокий
**Сложность:** Низкая (расчетные метрики из существующих)

#### Метрики для добавления:

1. **Precision** - `avi_content_filter_precision`
   - Тип: Gauge
   - Labels: `mode`
   - Формула: `TP / (TP + FP)`
   - Обоснование: Важна для понимания quality of detections

2. **Recall** - `avi_content_filter_recall`
   - Тип: Gauge
   - Labels: `mode`
   - Формула: `TP / (TP + FN)`
   - Обоснование: Важна для оценки coverage

3. **F1-Score** - `avi_content_filter_f1_score`
   - Тип: Gauge
   - Labels: `mode`
   - Формула: `2 * (Precision * Recall) / (Precision + Recall)`
   - Обоснование: Балансирует Precision и Recall

4. **Accuracy** - `avi_content_filter_accuracy`
   - Тип: Gauge
   - Labels: `mode`
   - Формула: `(TP + TN) / (TP + TN + FP + FN)`
   - Обоснование: Общая точность классификации

5. **False Positive Rate** - `avi_content_filter_fpr`
   - Тип: Gauge
   - Labels: `mode`
   - Формула: `FP / (FP + TN)`
   - Обоснование: Критично для UX (ложные срабатывания)

6. **False Negative Rate** - `avi_content_filter_fnr`
   - Тип: Gauge
   - Labels: `mode`
   - Формула: `FN / (FN + TP)`
   - Обоснование: Критично для безопасности

**Имплементация:**
- Добавить метод `ContentFilterMetrics.compute_derived_metrics()` → dict
- Вызывать периодически (например, каждые 60 секунд) из background task
- Публиковать как Prometheus Gauges

### 2. Throughput Metrics

**Приоритет:** Высокий
**Сложность:** Низкая

#### Метрики для добавления:

1. **HTTP Requests Rate** - `avi_http_requests_per_second`
   - Тип: Gauge (вычисляется из Counter)
   - Labels: `method`, `route`
   - Описание: Количество запросов в секунду
   - Обоснование: Важно для capacity planning

2. **Content Filter Rate** - `avi_content_filter_requests_per_second`
   - Тип: Gauge
   - Labels: `mode`, `stage` (input/output)
   - Описание: Количество фильтраций в секунду
   - Обоснование: Понимание нагрузки на фильтр

3. **LLM Requests Rate** - `avi_llm_requests_per_second`
   - Тип: Gauge
   - Labels: `role` (main, safety, scoring)
   - Описание: Количество LLM вызовов в секунду
   - Обоснование: Мониторинг usage и costs

**Имплементация:**
- Использовать `rate()` функцию Prometheus для вычисления из Counter
- Или добавить отдельные Gauge метрики, обновляемые background task

### 3. Token Usage Metrics

**Приоритет:** Высокий
**Сложность:** Средняя

#### Метрики для добавления:

1. **Input Tokens** - `avi_llm_tokens_input_total`
   - Тип: Counter
   - Labels: `role` (main, safety, scoring), `model`
   - Описание: Количество input tokens
   - Обоснование: Tracking costs

2. **Output Tokens** - `avi_llm_tokens_output_total`
   - Тип: Counter
   - Labels: `role`, `model`
   - Описание: Количество output tokens
   - Обоснование: Tracking costs

3. **Total Cost Estimate** - `avi_llm_cost_usd_total`
   - Тип: Counter
   - Labels: `role`, `model`
   - Описание: Оценка стоимости в USD
   - Обоснование: Budget tracking

**Имплементация:**
- Интегрировать в `LLMAdapter.generate_response()`
- Парсить `usage` из ответа LLM API
- Хранить pricing table для моделей

### 4. Cache Impact on Latency

**Приоритет:** Средний
**Сложность:** Средняя

#### Метрики для добавления:

1. **Cache Hit Latency** - `avi_cache_hit_latency_seconds`
   - Тип: Histogram
   - Labels: `backend`
   - Описание: Latency при cache hit
   - Обоснование: Понимание overhead кеша

2. **Cache Miss Latency** - `avi_cache_miss_latency_seconds`
   - Тип: Histogram
   - Labels: `backend`
   - Описание: Latency при cache miss (включая fallback)
   - Обоснование: Понимание impact cache miss

3. **Cache Speedup Factor** - `avi_cache_speedup_factor`
   - Тип: Gauge
   - Labels: `backend`
   - Формула: `Average Miss Latency / Average Hit Latency`
   - Обоснование: Эффективность кеша

**Имплементация:**
- Добавить timing в `CacheSystem.get()`
- Публиковать latency для hits и misses отдельно

### 5. RAG Relevance Score Distribution

**Приоритет:** Средний
**Сложность:** Низкая

#### Метрики для добавления:

1. **RAG Relevance Scores** - `avi_rag_relevance_score`
   - Тип: Histogram
   - Labels: нет (или `source`: vector_search, rerank)
   - Описание: Распределение relevance scores
   - Обоснование: Понимание quality of retrieval

2. **RAG Documents Retrieved** - `avi_rag_documents_retrieved`
   - Тип: Histogram
   - Labels: `retrieval_mode` (vector_search, linked_docs)
   - Описание: Количество извлеченных документов
   - Обоснование: Понимание context size

3. **RAG Retrieval Latency** - `avi_rag_retrieval_latency_seconds`
   - Тип: Histogram
   - Labels: `retrieval_mode`
   - Описание: Время на извлечение документов
   - Обоснование: Bottleneck analysis

**Имплементация:**
- Интегрировать в `RAGService.retrieve_context()`
- Логировать relevance scores через Histogram

### 6. Filter Mode Performance Comparison

**Приоритет:** Средний
**Сложность:** Низкая (уже частично реализовано)

#### Метрики для добавления:

1. **Filter Mode Latency Comparison**
   - Уже есть: `avi_content_filter_detection_latency_seconds{mode=...}`
   - Улучшение: Добавить breakdown по компонентам

2. **Component Latency** - `avi_content_filter_component_latency_seconds`
   - Тип: Histogram
   - Labels: `component`, `stage`
   - Описание: Latency каждого компонента фильтрации
   - Обоснование: Детальный bottleneck analysis

**Имплементация:**
- Обернуть каждый компонент в timing block
- Публиковать отдельные latency метрики

### 7. Streaming Guard Metrics (Prometheus Export)

**Приоритет:** Низкий
**Сложность:** Средняя

Сейчас метрики streaming guard не экспортируются в Prometheus.

#### Метрики для добавления:

1. **Streaming Chunks Processed** - `avi_streaming_chunks_processed_total`
   - Тип: Counter
   - Labels: `guard_mode`
   - Описание: Всего обработано чанков

2. **Streaming Chunks Flagged** - `avi_streaming_chunks_flagged_total`
   - Тип: Counter
   - Labels: `guard_mode`
   - Описание: Помечено как опасные

3. **Streaming Chunks Blocked** - `avi_streaming_chunks_blocked_total`
   - Тип: Counter
   - Labels: `guard_mode`
   - Описание: Заблокировано

4. **Streaming LLM Calls** - `avi_streaming_llm_calls_total`
   - Тип: Counter
   - Labels: `guard_mode`
   - Описание: Вызовы Safety LLM

**Имплементация:**
- Интегрировать Prometheus counters в `StreamingGuard`

### 8. Error Rate Metrics

**Приоритет:** Высокий
**Сложность:** Низкая

#### Метрики для добавления:

1. **HTTP Error Rate** - уже есть через `status_code` label
   - Улучшение: Добавить отдельный counter для errors

2. **LLM Error Rate** - `avi_llm_errors_total`
   - Тип: Counter
   - Labels: `role`, `error_type` (timeout, rate_limit, api_error)
   - Описание: Количество ошибок LLM
   - Обоснование: Reliability monitoring

3. **Filter Error Rate** - `avi_content_filter_errors_total`
   - Тип: Counter
   - Labels: `mode`, `stage`, `error_type`
   - Описание: Ошибки фильтрации
   - Обоснование: Quality assurance

**Имплементация:**
- Добавить error tracking в try-except блоки
- Публиковать как Counter

### 9. Vector DB Performance Metrics

**Приоритет:** Средний
**Сложность:** Средняя

#### Метрики для добавления:

1. **Vector Search Latency** - `avi_vector_search_latency_seconds`
   - Тип: Histogram
   - Labels: `collection` (documents, rules, rule_links)
   - Описание: Latency vector search
   - Обоснование: Bottleneck в filter

2. **Vector Search Results Count** - `avi_vector_search_results_count`
   - Тип: Histogram
   - Labels: `collection`
   - Описание: Количество результатов
   - Обоснование: Understanding retrieval

**Имплементация:**
- Интегрировать в `VectorDBClient.find_matching_rules()`

### 10. Rate Limiting Metrics

**Приоритет:** Низкий
**Сложность:** Низкая

#### Метрики для добавления:

1. **Rate Limit Hits** - `avi_rate_limit_hits_total`
   - Тип: Counter
   - Labels: `endpoint`, `limit_type`
   - Описание: Сколько раз сработал rate limit
   - Обоснование: Capacity planning

2. **Rate Limit Rejections** - `avi_rate_limit_rejections_total`
   - Тип: Counter
   - Labels: `endpoint`
   - Описание: Отклоненные запросы
   - Обоснование: User experience

**Имплементация:**
- Интегрировать в rate limiting middleware

---

## План имплементации

### Фаза 1: Расчетные метрики (1-2 часа)

**Цель:** Добавить derived metrics из существующих данных.

**Задачи:**
1. ✅ Добавить метод `ContentFilterMetrics.compute_derived_metrics()`
2. ✅ Создать Prometheus Gauge метрики для Precision, Recall, F1, Accuracy, FPR, FNR
3. ✅ Добавить background task для периодического вычисления
4. ✅ Добавить в Swagger endpoint `/metrics/derived` для просмотра

**Файлы для изменения:**
- `src/monitoring/metrics.py` - добавить compute_derived_metrics()
- `src/api/routes.py` - добавить endpoint
- `main.py` - добавить background task

### Фаза 2: Token Usage Metrics (2-3 часа)

**Цель:** Отслеживать token usage и costs.

**Задачи:**
1. ✅ Добавить Prometheus Counter для input/output tokens
2. ✅ Парсить `usage` из LLM API responses
3. ✅ Создать pricing table для моделей
4. ✅ Добавить cost estimation

**Файлы для изменения:**
- `src/monitoring/metrics.py` - добавить token metrics
- `src/services/llm_adapter.py` - интегрировать tracking
- `config/pricing.py` - новый файл с pricing table

### Фаза 3: Cache Impact Metrics (1-2 часа)

**Цель:** Понять влияние кеша на latency.

**Задачи:**
1. ✅ Добавить timing в `CacheSystem.get()`
2. ✅ Добавить Histogram для cache hit/miss latency
3. ✅ Вычислять speedup factor

**Файлы для изменения:**
- `src/core/cache_system.py` - добавить timing
- `src/monitoring/observability.py` - добавить метрики

### Фаза 4: Component Latency Breakdown (2-3 часа)

**Цель:** Детальный анализ bottlenecks в фильтрации.

**Задачи:**
1. ✅ Обернуть каждый компонент фильтрации в timing
2. ✅ Добавить Histogram для component latency
3. ✅ Интегрировать в `check_content()`

**Файлы для изменения:**
- `src/core/content_filter.py` - добавить component timing
- `src/monitoring/metrics.py` - добавить histogram

### Фаза 5: RAG и Vector DB Metrics (2-3 часа)

**Цель:** Мониторинг RAG performance.

**Задачи:**
1. ✅ Добавить relevance score histogram
2. ✅ Добавить retrieval latency
3. ✅ Добавить vector search metrics

**Файлы для изменения:**
- `src/services/rag_service.py` - добавить metrics
- `src/services/vector_db.py` - добавить timing
- `src/monitoring/observability.py` - добавить метрики

### Фаза 6: Error Rate Metrics (1-2 часа)

**Цель:** Отслеживать ошибки системы.

**Задачи:**
1. ✅ Добавить error counters для LLM
2. ✅ Добавить error counters для filter
3. ✅ Интегрировать в exception handlers

**Файлы для изменения:**
- `src/services/llm_adapter.py` - error tracking
- `src/core/content_filter.py` - error tracking
- `src/monitoring/metrics.py` - error counters

### Фаза 7: Streaming Guard Export (опционально, 1-2 часа)

**Цель:** Экспорт streaming metrics в Prometheus.

**Задачи:**
1. ✅ Добавить Prometheus counters в StreamingGuard
2. ✅ Интегрировать в chunk processing

**Файлы для изменения:**
- `src/core/streaming_guard.py` - добавить Prometheus
- `src/monitoring/metrics.py` - добавить streaming metrics

### Фаза 8: Dashboard и Visualization (3-4 часа)

**Цель:** Обновить Grafana dashboard.

**Задачи:**
1. ✅ Создать Grafana dashboard с новыми метриками
2. ✅ Добавить панели для derived metrics
3. ✅ Добавить панели для token usage
4. ✅ Добавить сравнительные графики

**Файлы для создания:**
- `config/grafana/dashboards/avi-metrics.json`

---

## Архитектура метрик

### Поток данных метрик

```
┌─────────────────────────────────────────────────────────────────┐
│                         AVI Application                          │
│                                                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐ │
│  │  HTTP API  │  │   Filter   │  │    RAG     │  │   Cache    │ │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘ │
│        │               │               │               │         │
│        └───────────────┴───────────────┴───────────────┘         │
│                              ▼                                    │
│                    ┌─────────────────────┐                        │
│                    │  Metrics Collectors │                        │
│                    │  - ContentFilterM.  │                        │
│                    │  - Observability    │                        │
│                    │  - In-Memory Stats  │                        │
│                    └──────────┬──────────┘                        │
└───────────────────────────────┼───────────────────────────────────┘
                                ▼
              ┌─────────────────────────────────┐
              │    Metrics Export Systems       │
              │                                  │
              │  ┌──────────┐  ┌──────────┐    │
              │  │Prometheus│  │  MLflow  │    │
              │  │  /metrics│  │          │    │
              │  └─────┬────┘  └────┬─────┘    │
              │        │            │           │
              │  ┌─────┴────────────┴─────┐    │
              │  │   Weights & Biases     │    │
              │  └────────────────────────┘    │
              └─────────────────────────────────┘
                         ▼
              ┌─────────────────────┐
              │  Visualization      │
              │  - Grafana          │
              │  - MLflow UI        │
              │  - W&B Dashboard    │
              └─────────────────────┘
```

### Иерархия метрик

```
AVI Metrics
├── HTTP Layer
│   ├── Request Latency (histogram)
│   ├── Requests Total (counter)
│   └── Error Rate (calculated)
│
├── Content Filter
│   ├── Confusion Matrix
│   │   ├── True Positives (counter)
│   │   ├── False Positives (counter)
│   │   ├── False Negatives (counter)
│   │   └── True Negatives (counter)
│   ├── Derived Metrics
│   │   ├── Precision (gauge, calculated)
│   │   ├── Recall (gauge, calculated)
│   │   ├── F1-Score (gauge, calculated)
│   │   ├── Accuracy (gauge, calculated)
│   │   ├── FPR (gauge, calculated)
│   │   └── FNR (gauge, calculated)
│   ├── Latency
│   │   ├── Detection Latency (histogram)
│   │   └── Sanitization Latency (histogram)
│   ├── Component-Level
│   │   ├── Component Applied (counter)
│   │   ├── Component Modified (counter)
│   │   └── Component Latency (histogram, proposed)
│   └── Safety Interventions (counter)
│
├── Cache
│   ├── Hits/Misses (counter)
│   ├── Hit Rate (calculated)
│   ├── Hit Latency (histogram, proposed)
│   └── Miss Latency (histogram, proposed)
│
├── RAG
│   ├── Retrieval Latency (histogram, proposed)
│   ├── Rerank Latency (histogram)
│   ├── Relevance Scores (histogram, proposed)
│   └── Documents Retrieved (histogram, proposed)
│
├── LLM
│   ├── Request Latency (embedded in other metrics)
│   ├── Token Usage (counter, proposed)
│   │   ├── Input Tokens
│   │   └── Output Tokens
│   ├── Cost Estimate (counter, proposed)
│   └── Error Rate (counter, proposed)
│
├── Streaming Guard
│   ├── Chunks Processed (counter, proposed)
│   ├── Chunks Flagged (counter, proposed)
│   ├── Chunks Blocked (counter, proposed)
│   └── LLM Calls (counter, proposed)
│
└── Vector DB
    ├── Search Latency (histogram, proposed)
    └── Search Results Count (histogram, proposed)
```

### Метрики по двустороннему фильтру (Input/Output)

Уже реализовано частично через `stage` label:

```
Input Filter Pipeline:
1. Vector Rules Search → detection_latency_seconds{mode=...}
2. Prompt Modification → component_applied{component="prompt_modification", stage="input"}
3. Safety LLM → sanitization_latency_seconds{mode=...}

Output Filter Pipeline:
1. Vector Rules Search → detection_latency_seconds{mode=...}
2. Output Cleaning → component_applied{component="output_cleaning", stage="output"}
3. Safety LLM → sanitization_latency_seconds{mode=...}
```

**Предложенные улучшения:**
- Добавить `avi_content_filter_input_latency_seconds` и `avi_content_filter_output_latency_seconds` для полного e2e латентности
- Добавить `avi_content_filter_input_modifications_total` и `avi_content_filter_output_modifications_total` для подсчета модификаций

---

## Рекомендации

### 1. Приоритизация имплементации

**Высокий приоритет (необходимо для production):**
- Derived confusion matrix metrics (Precision, Recall, F1)
- Token usage metrics (для cost tracking)
- Error rate metrics (для reliability)
- Throughput metrics (для capacity planning)

**Средний приоритет (полезно для optimization):**
- Component latency breakdown
- Cache impact metrics
- RAG relevance metrics

**Низкий приоритет (nice to have):**
- Streaming guard Prometheus export
- Rate limiting metrics
- Vector DB detailed metrics

### 2. Минимальные системные требования

Для сбора всех предложенных метрик:
- **CPU:** +5-10% overhead для metric collection
- **Memory:** +50-100 MB для in-memory aggregation
- **Disk:** Prometheus storage ~1GB/day (зависит от cardinality)
- **Network:** Negligible (Prometheus pull model)

### 3. Cardinality Management

**Важно:** Избегать высокой cardinality в labels (explosion of time series).

**Правила:**
- Не добавлять user_id, request_id в labels
- Ограничивать количество уникальных значений: <100 для label
- Использовать aggregation для высоко-вариативных данных

**Текущая cardinality:**
- `mode`: 4 значения (disabled, local, external, hybrid)
- `component`: 4 значения (vector_rules, safety_llm, prompt_modification, output_cleaning)
- `stage`: 2 значения (input, output)
- **Total combinations:** 4 × 4 × 2 = 32 time series per metric

**С предложенными метриками:**
- Новых labels не добавляется
- Общая cardinality остается управляемой (<1000 time series)

### 4. Мониторинг метрик метрик

Добавить метрики для самой системы метрик:
- `avi_metrics_collection_latency_seconds` - overhead сбора
- `avi_metrics_export_errors_total` - ошибки экспорта
- `avi_metrics_time_series_count` - количество time series

### 5. Alerting Rules

Предложенные alerts для Prometheus:

```yaml
# High False Positive Rate
- alert: HighFalsePositiveRate
  expr: avi_content_filter_fpr > 0.1
  for: 5m
  annotations:
    summary: "High false positive rate detected"

# Low Recall (missing threats)
- alert: LowRecall
  expr: avi_content_filter_recall < 0.8
  for: 5m
  annotations:
    summary: "Low recall - threats being missed"

# High Latency
- alert: HighFilterLatency
  expr: histogram_quantile(0.95, avi_content_filter_detection_latency_seconds) > 0.5
  for: 5m
  annotations:
    summary: "95th percentile filter latency > 500ms"

# Low Cache Hit Rate
- alert: LowCacheHitRate
  expr: rate(avi_cache_hits_total[5m]) / (rate(avi_cache_hits_total[5m]) + rate(avi_cache_misses_total[5m])) < 0.5
  for: 10m
  annotations:
    summary: "Cache hit rate below 50%"
```

---

## Выводы

### Текущее состояние

AVI имеет **солидную базу метрик** для мониторинга:
- ✅ Confusion matrix для оценки quality
- ✅ Latency метрики для performance
- ✅ Component-level tracking для granular control
- ✅ Cache metrics для optimization
- ✅ Поддержка трех систем (Prometheus, MLflow, W&B)

### Пробелы

**Отсутствующие критичные метрики:**
- ❌ Derived metrics (Precision, Recall, F1) - требуют вычисления
- ❌ Token usage и cost tracking
- ❌ Component latency breakdown
- ❌ Error rate tracking

**Отсутствующие полезные метрики:**
- ⚠️ Throughput (RPS)
- ⚠️ Cache impact on latency
- ⚠️ RAG relevance distribution
- ⚠️ Streaming guard Prometheus export

### Roadmap

**Краткосрочный (1-2 недели):**
1. Реализовать derived confusion matrix metrics
2. Добавить token usage tracking
3. Добавить error rate metrics

**Среднесрочный (1 месяц):**
4. Добавить component latency breakdown
5. Добавить cache impact metrics
6. Создать Grafana dashboard

**Долгосрочный (2-3 месяца):**
7. Добавить RAG и Vector DB детальные метрики
8. Экспорт streaming guard metrics
9. Alerting rules и SLO/SLI definition

---

**Документ подготовлен:** 2025-11-13
**Автор:** Claude (AVI Refactoring Task 1.4)
**Версия:** 1.0
