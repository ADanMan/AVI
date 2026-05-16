# 📊 Руководство по запуску бенчмарков

## Быстрый старт (одна модель)

### 1. Подготовка данных

```bash
# Установить библиотеку datasets
pip install datasets

# Загрузить все датасеты
PYTHONPATH=/home/user/AVI python scripts/setup_data.py
```

Это загрузит:
- ✅ `toxigen.csv` - ~10,000 строк токсичного контента
- ✅ `prompt_injections.csv` - ~10,000 промпт-инъекций
- ✅ `pii_masking_200k.csv` - ~10,000 примеров с PII
- ✅ `poly_fever.csv` - ~10,000 фактов для проверки
- ✅ `shades_nationality.csv` - ~10,000 примеров стереотипов

### 2. Запуск API

```bash
# В одном терминале
python -m uvicorn src.api.main:app --reload
```

### 3. Запуск бенчмарка

**Вариант А: Через скрипт (рекомендуется для первого раза)**

```bash
chmod +x scripts/run_quick_benchmark.sh
./scripts/run_quick_benchmark.sh
```

**Вариант Б: Напрямую через Python**

```bash
PYTHONPATH=/home/user/AVI python scripts/benchmark_test.py
```

## Отслеживание прогресса

### ✅ В MLflow (если включен)

```bash
# Запустите MLflow UI
mlflow ui --port 5000

# Откройте http://localhost:5000
```

Вы увидите:
- Метрики (precision, recall, F1)
- Параметры каждого запуска
- Графики сравнения
- Артефакты (CSV с результатами)

### ✅ Промежуточные файлы

Результаты сохраняются **после каждого запроса** в:
```
artifacts/results/
├── toxigen_openrouter__openai_gpt-4o-mini_default.csv
├── toxigen_openrouter__openai_gpt-4o-mini_default.metrics.csv
└── ...
```

### ✅ Возобновление при сбое

Если бенчмарк прервался:
- Просто запустите снова
- Система **автоматически продолжит** с места остановки
- Уже обработанные строки пропускаются

## Режимы фильтра

В `benchmark_config.json` можно настроить режимы:

```json
{
  "benchmarks": [
    {
      "name": "Toxicity Test",
      "file": "toxigen.csv",
      "text_column": "text"
    }
  ],
  "models": [
    {
      "name": "openai/gpt-4o-mini",
      "provider": "openrouter"
    }
  ]
}
```

Система автоматически тестирует ВСЕ режимы фильтра:
- ✅ DISABLED
- ✅ LOCAL (если настроен)
- ✅ EXTERNAL (через OpenAI Moderation)
- ✅ HYBRID (fallback LOCAL → EXTERNAL)

## Анализ результатов

### 1. Metrics CSV

```csv
stage,mode,tp,fp,fn,tn,precision,recall,f1,latency_ms_avg
input,disabled,100,20,5,875,0.833,0.952,0.889,15.3
input,external,105,10,0,885,0.913,1.000,0.955,45.2
```

### 2. Results CSV

Полные данные каждого запроса:
- Оригинальный текст
- Модифицированный текст
- Найденные совпадения
- Время обработки
- Режим фильтра
- Ground truth

### 3. MLflow Dashboard

Сравнение экспериментов с графиками и метриками.

## Производительность

### Ускорение

В `benchmark_config.json`:

```json
{
  "api": {
    "concurrent_requests_limit": 10  // Параллельные запросы
  }
}
```

⚠️ Осторожно с лимитами API!

### Оценка времени

- **1 запрос** ≈ 2-5 секунд
- **100 запросов** @ 5 concurrent ≈ 2-5 минут
- **10,000 запросов** @ 5 concurrent ≈ 3-7 часов

## Troubleshooting

### Датасет не загружается

```bash
# Проверьте интернет
ping huggingface.co

# Используйте прокси если нужно
export HF_ENDPOINT=https://huggingface.co
```

### Бенчмарк зависает

1. Проверьте API: `curl http://localhost:8000/health`
2. Проверьте логи: `tail -f logs/app.log`
3. Уменьшите `concurrent_requests_limit`

### Out of Memory

Уменьшите размер датасета в `setup_data.py`:

```python
save_dataset(ds, "data/benchmarks/toxigen.csv", n_rows=1000)  # Вместо 10000
```

## Рекомендации

### Первый запуск

1. ✅ Протестируйте на **100-500 строках**
2. ✅ Используйте **1 модель, 1 датасет**
3. ✅ Проверьте что метрики считаются корректно
4. ✅ Затем масштабируйте

### Полный бенчмарк

```json
{
  "models": [
    "openai/gpt-4o",
    "anthropic/claude-sonnet-4",
    "google/gemini-2.5-pro"
  ],
  "parameters": {
    "temperature": [0.0, 0.5, 1.0],
    "max_tokens": [300]
  }
}
```

Это = 3 модели × 6 датасетов × 3 temperatures = **54 запуска** × 10,000 строк каждый

## Полезные команды

```bash
# Посмотреть результаты
ls -lh artifacts/results/

# Открыть последний лог
tail -f logs/benchmark.log

# Очистить кеш
rm -rf artifacts/results/*.tmp

# Проверить статус API
curl http://localhost:8000/health
```

## Итоговый чеклист

- [x] Установлен `datasets`
- [x] Загружены датасеты через `setup_data.py`
- [x] Запущен API на порту 8000
- [x] Настроен `benchmark_config.json`
- [x] (Опционально) Настроен MLflow
- [x] Запущен бенчмарк
- [x] Проверены результаты в `artifacts/results/`

---

**Вопросы?** Проверьте логи или запустите с флагом verbose:

```bash
export LOG_LEVEL=DEBUG
python scripts/benchmark_test.py
```
