# Filter Benchmark Script

## Описание

`filter_benchmark.py` — интерактивный скрипт для прогона датасета с вопросами через фильтр AVI. Позволяет оценить работу фильтра на реальных данных с сохранением подробных метаданных.

## Возможности

- 📂 Загрузка CSV файлов с вопросами
- 🎯 Интерактивный выбор колонки с текстом
- 🔧 **Два режима работы:**
  - **Локальный** - прямой вызов ContentFilterService (быстрее, для разработки)
  - **Через API** - HTTP запросы к настраиваемому endpoint (для тестирования удалённого API)
- ⚙️ Настройка параметров фильтрации (safety mode, LLM, thresholds)
- 🔍 Прогон всех вопросов через фильтр с progress bar
- 💾 Сохранение результатов с метаданными (включая ответы LLM в API режиме)
- 📊 Автоматическая статистика и анализ результатов
- 🔐 Поддержка API ключей для защищённых endpoint'ов
- 🌐 Настраиваемый путь к API endpoint (по умолчанию `/query`)
- 💾 Управление кешированием на стороне API (можно отключить)
- 📝 Сохранение конфигурации для воспроизводимости

## Использование

### Базовый запуск

```bash
python scripts/filter_benchmark.py
```

### Пример интерактивной сессии

```
🔍 Бенчмарк фильтра AVI
======================================================================

Введите путь к CSV файлу с вопросами: data/benchmarks/my_questions.csv

📂 Загрузка файла: my_questions.csv
✅ Загружено 1000 строк

Доступные колонки в файле:

  1. question                     | Пример: Как работает фильтр?
  2. answer                       | Пример: Фильтр проверяет текст...
  3. category                     | Пример: Technical

Введите номер или название колонки с вопросами: 1
✅ Выбрана колонка: 'question'

⚙️  Настройки фильтрации
======================================================================

Доступные режимы безопасности:

  1. disabled     - Без LLM фильтрации (только vector rules)
  2. external     - Внешний LLM для санитизации
  3. local        - Локальный safety сервис
  4. hybrid       - Гибридный (local + external fallback)

Текущий режим из настроек: disabled

Выберите режим (1-4) или Enter для текущего [disabled]: 1
✅ Режим безопасности: disabled

🔧 Дополнительные параметры:

  Включить vector rules? (y/n) [y]: y
  Включить модификацию промпта при срабатывании? (y/n) [y]: y

Переопределить порог срабатывания? (y/n) [n]: n

🚀 Начать фильтрацию? (y/n) [y]: y

🔍 Прогон 1000 вопросов через фильтр...

Фильтрация: 100%|████████████████| 1000/1000 [00:45<00:00, 22.15it/s]

💾 Сохранение результатов
======================================================================

Директория для сохранения результатов [data/benchmarks/filter]:

✅ Результаты: data/benchmarks/filter/my_questions_filtered_20250125_143022.csv
✅ Конфигурация: data/benchmarks/filter/my_questions_config_20250125_143022.json

📊 Статистика результатов
======================================================================

Всего вопросов:           1000
Модифицировано:           123 (12.3%)
С срабатыванием правил:   156 (15.6%)

Категории срабатываний:
  • Toxicity           - 78 раз
  • PII                - 34 раз
  • Bias               - 44 раз

Уровни риска:
  • Risk Level 3:  89 вопросов
  • Risk Level 4:  45 вопросов
  • Risk Level 5:  22 вопроса

Средняя латентность детекции: 12.34 ms
```

## Формат выходных данных

### Результаты (CSV)

Каждая строка содержит:

| Колонка | Описание |
|---------|----------|
| `index` | Индекс вопроса в исходном датасете |
| **INPUT filter (фильтрация вопроса)** | |
| `original_text` | Исходный текст вопроса |
| `modified_text` | Модифицированный текст вопроса (если был изменён) |
| `was_modified` | Был ли вопрос модифицирован (True/False) |
| `matched_rules_count` | Количество сработавших правил |
| `max_risk_level` | Максимальный уровень риска среди сработавших правил |
| `max_relevance_score` | Максимальный relevance score |
| `rule_ids` | ID сработавших правил (разделены `\|`) |
| `rule_texts` | Тексты правил (разделены `\|`) |
| `categories` | Категории правил (разделены `\|`) |
| `risk_levels` | Уровни риска (разделены `\|`) |
| `relevance_scores` | Скоры релевантности (разделены `\|`) |
| `detection_latency_ms` | Время детекции в миллисекундах |
| `sanitization_latency_ms` | Время санитизации в миллисекундах (если использовался LLM) |
| `safety_mode` | Активный режим безопасности |
| `components_vector_rules` | Применялись ли vector rules |
| `components_safety_llm` | Применялся ли safety LLM |
| `components_prompt_mod` | Применялась ли модификация промпта |
| **LLM response** | |
| `llm_response` | Ответ LLM на вопрос (только в API режиме) |
| **OUTPUT filter (фильтрация ответа)** | |
| `output_modified_text` | Модифицированный ответ (если был исправлен) |
| `output_was_modified` | Был ли ответ модифицирован (True/False) |
| `output_matched_rules_count` | Количество сработавших правил на ответе |
| `output_max_risk_level` | Максимальный уровень риска в ответе |
| `output_rule_ids` | ID сработавших правил (разделены `\|`) |
| `output_categories` | Категории правил (разделены `\|`) |
| **Timing** | |
| `processed_at` | Timestamp обработки |
| `api_response_time_ms` | Время ответа API в миллисекундах (только API режим) |

### Конфигурация (JSON)

**Локальный режим:**

```json
{
  "timestamp": "2025-01-25T14:30:22.123456",
  "mode": "local",
  "safety_mode": "disabled",
  "requested_mode": "disabled",
  "default_threshold": 0.75,
  "safety_llm_enabled": false,
  "settings": {
    "FILTER_DEFAULT_THRESHOLD": 0.75,
    "FILTER_FALLBACK_THRESHOLD": 0.7,
    "VECTOR_SEARCH_TOP_K": 5,
    "SAFETY_MODE": "disabled",
    "STREAM_GUARD_MODE": "hybrid"
  },
  "extra_params": {
    "use_llm": false,
    "enable_vector_rules": true,
    "enable_prompt_modification": true,
    "dataset_file": "/home/user/AVI/data/benchmarks/my_questions.csv",
    "questions_column": "question",
    "total_questions": 1000
  }
}
```

**API режим:**

```json
{
  "timestamp": "2025-01-25T14:30:22.123456",
  "mode": "api",
  "extra_params": {
    "api_base": "http://localhost:8000",
    "api_endpoint": "/query",
    "api_key_provided": true,
    "use_llm_filter": true,
    "use_linked_docs": true,
    "use_cache": false,
    "dataset_file": "/home/user/AVI/data/benchmarks/my_questions.csv",
    "questions_column": "question",
    "total_questions": 1000
  }
}
```

## Примеры использования

### 1. Базовый тест без LLM

Проверка только vector rules:

```bash
python scripts/filter_benchmark.py
# Выберите режим: disabled (1)
# Включить vector rules: y
# Включить модификацию: y
```

### 2. Тест с external LLM

Полная фильтрация с санитизацией:

```bash
python scripts/filter_benchmark.py
# Выберите режим: external (2)
# Использовать LLM для санитизации: y
```

### 3. Тест с кастомным порогом

Более строгая фильтрация:

```bash
python scripts/filter_benchmark.py
# Переопределить порог: y
# Порог: 0.65
```

### 4. Тест через внешний API

Тестирование удалённого API:

```bash
python scripts/filter_benchmark.py
# Выберите режим: 2 (Через API)
# Base URL: http://your-api-server:8000
# Путь к endpoint: /query (или /filter, /check и т.д.)
# API ключ: ваш-ключ (или Enter если не нужен)
# Использовать кеширование: n (отключить для бенчмарка)
```

## Анализ результатов

### Python

```python
import pandas as pd

# Загрузить результаты
df = pd.read_csv("data/benchmarks/filter/my_questions_filtered_20250125_143022.csv")

# Основная статистика
print(f"Всего вопросов: {len(df)}")
print(f"С срабатыванием: {(df['matched_rules_count'] > 0).sum()}")
print(f"Модифицировано: {df['was_modified'].sum()}")

# Распределение по категориям
all_categories = []
for cats in df[df["categories"] != ""]["categories"]:
    all_categories.extend(cats.split("|"))

from collections import Counter
print("\nТоп категорий:")
for cat, count in Counter(all_categories).most_common(5):
    print(f"  {cat}: {count}")

# Латентность
print(f"\nСредняя латентность: {df['detection_latency_ms'].mean():.2f} ms")
print(f"P95 латентность: {df['detection_latency_ms'].quantile(0.95):.2f} ms")

# Вопросы с максимальным риском
high_risk = df[df["max_risk_level"] >= 4].sort_values("max_risk_level", ascending=False)
print(f"\nВопросы с высоким риском: {len(high_risk)}")
print(high_risk[["original_text", "max_risk_level", "categories"]].head())
```

### SQL (если загружено в БД)

```sql
-- Топ категорий срабатываний
SELECT
    category,
    COUNT(*) as count
FROM (
    SELECT
        UNNEST(STRING_TO_ARRAY(categories, '|')) as category
    FROM filter_results
    WHERE categories != ''
) sub
GROUP BY category
ORDER BY count DESC;

-- Средняя латентность по категориям
SELECT
    category,
    AVG(detection_latency_ms) as avg_latency,
    COUNT(*) as count
FROM (
    SELECT
        UNNEST(STRING_TO_ARRAY(categories, '|')) as category,
        detection_latency_ms
    FROM filter_results
    WHERE categories != ''
) sub
GROUP BY category
ORDER BY avg_latency DESC;
```

## Требования

### Python пакеты

- `pandas` - для работы с CSV
- `tqdm` - для progress bar
- `asyncio` - для асинхронной обработки

Все пакеты устанавливаются автоматически при установке AVI:

```bash
make install-dev
```

### Данные

Перед запуском убедитесь, что:

1. Vector DB проиндексирована:
   ```bash
   python scripts/index_data.py
   ```

2. Есть CSV файл с вопросами (любая колонка с текстом)

3. Настроены LLM ключи в `.env` (если используете LLM режим):
   ```bash
   MAIN_LLM_API_KEY=sk-xxx
   SAFETY_LLM_API_KEY=sk-xxx  # Если используете external/hybrid
   ```

## Troubleshooting

### Ошибка: "Vector DB пустая"

```
❌ Ошибка инициализации фильтра: No rules found in vector DB
```

**Решение**: Проиндексируйте данные:
```bash
python scripts/index_data.py
```

### Ошибка: "LLM API key not set"

```
❌ Ошибка: MAIN_LLM_API_KEY not set
```

**Решение**: Добавьте ключ в `.env`:
```bash
echo "MAIN_LLM_API_KEY=sk-your-key" >> .env
```

### Медленная обработка

Если фильтрация идёт медленно (< 5 вопросов/сек):

1. Проверьте латентность Vector DB
2. Отключите LLM санитизацию (если не нужна)
3. Используйте batch processing (будущая feature)

### Encoding ошибки

Если CSV не загружается:

```python
# Скрипт автоматически пробует utf-8 и cp1251
# Если нужна другая кодировка, укажите вручную:
df = pd.read_csv("file.csv", encoding="latin1")
```

## Roadmap

- [ ] Batch processing для больших датасетов
- [ ] Поддержка JSON/JSONL форматов
- [ ] Параллельная обработка (multiprocessing)
- [ ] Сравнение разных конфигураций фильтра
- [ ] Визуализация результатов (графики, charts)
- [ ] Экспорт в Weights & Biases / MLflow

## См. также

- [CLAUDE.md](../CLAUDE.md) - Основная документация проекта
- [API.md](API.md) - API документация
- [TESTING.md](../TESTING.md) - Тестирование

## Автор

AVI Team

## Лицензия

MIT
