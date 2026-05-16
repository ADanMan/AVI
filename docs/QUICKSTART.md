# 🚀 Быстрый Старт AVI

Пошаговая инструкция по запуску системы AVI с нуля.

---

## Минимальные требования

- Python 3.11+
- 500 MB свободного места
- API ключ для LLM (OpenRouter, OpenAI, или другой совместимый провайдер)

---

## Вариант 1: Быстрый запуск (CPU, минимальная конфигурация)

**Время установки:** ~5 минут

### Шаг 1: Клонируйте репозиторий

```bash
git clone https://github.com/ADanMan/AVI.git
cd AVI
```

### Шаг 2: Установите зависимости (CPU-only, экономия 3.2 GB!)

```bash
# Рекомендуется: создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate

# Установите CPU-only версию (быстро, экономит память)
make install-cpu

# Или вручную:
pip install -r requirements/base.txt
pip install -r requirements/ml-cpu.txt
```

### Шаг 3: Настройте конфигурацию

```bash
# Скопируйте шаблон конфигурации
cp .env.example .env

# Откройте .env в редакторе
nano .env  # или vim, code, notepad++
```

**Минимальная конфигурация для старта:**

```bash
# ОБЯЗАТЕЛЬНЫЕ настройки (только эти 2!)
MAIN_LLM_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxx  # ← Ваш API ключ
MAIN_LLM_MODEL=openai/gpt-4o-mini            # ← Или другая модель

# Все остальное работает с дефолтными значениями!
```

**Где взять API ключ:**
- [OpenRouter](https://openrouter.ai/) - поддерживает множество моделей (рекомендуется)
- [OpenAI](https://platform.openai.com/) - прямой доступ к GPT-4
- Любой другой OpenAI-совместимый провайдер

### Шаг 4: Подготовьте данные

```bash
# Скачает и подготовит все необходимые данные (правила фильтрации, документы)
python -m avi.cli setup-data
```

**Что происходит:**
- Создаются директории `data/raw/`, `data/benchmarks/`, `data/indexes/`
- Загружаются тестовые датасеты
- Создаются CSV с правилами фильтрации

### Шаг 5: Индексируйте данные в векторную БД

```bash
# Создает векторные индексы для RAG
python -m avi.cli index-data
```

**Что происходит:**
- Загружаются документы из `data/raw/vector_documents.csv`
- Создаются embeddings с помощью sentence-transformers
- Сохраняются в ChromaDB (по умолчанию) в `data/indexes/chroma/`

### Шаг 6: Запустите API сервер

```bash
# Запуск с hot-reload для разработки
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Или через make
make run
```

**Проверьте работу:**
- API документация: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Metrics: http://localhost:8000/metrics

### Шаг 7: (Опционально) Запустите Gradio Chat UI

```bash
# В отдельном терминале
python gradio_ui.py

# Или через make
make run-ui
```

**Chat UI доступен на:** http://localhost:7860

Интерфейс предоставляет:
- Простой чат с AI
- Переключатели для RAG и Safety фильтров
- Прямое подключение к API на порту 8000

---

## Вариант 2: Docker (рекомендуется для продакшена)

**Время установки:** ~10 минут

### Шаг 1: Настройте .env

```bash
cp .env.example .env
# Отредактируйте .env (минимум: MAIN_LLM_API_KEY и MAIN_LLM_MODEL)
```

### Шаг 2: CPU или GPU?

**CPU версия (экономит 3.2 GB):**
```bash
docker compose build
docker compose up
```

**GPU версия (для CUDA-совместимых GPU):**
```bash
docker compose -f docker-compose.yml build api-gpu
docker compose up api-gpu
```

### Шаг 3: Подготовьте данные внутри контейнера

```bash
# Setup данных
docker compose run --rm api python -m avi.cli setup-data

# Индексация
docker compose run --rm api python -m avi.cli index-data
```

### Шаг 4: Перезапустите сервисы

```bash
docker compose up
```

**Доступные сервисы:**
- Gradio Chat UI: http://localhost:7860
- API: http://localhost:8000
- Qdrant UI: http://localhost:6333/dashboard
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)
- MLflow: http://localhost:5000
- Jaeger: http://localhost:16686

---

## 🧪 Проверка установки

### Тест 1: Health Check

```bash
curl http://localhost:8000/health
```

**Ожидаемый ответ:**
```json
{
  "status": "healthy",
  "checks": {
    "disk_space": "healthy",
    "llm_config": "healthy",
    "vector_db_config": "healthy"
  }
}
```

### Тест 2: Простой запрос

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Что такое машинное обучение?",
    "mode": "llm"
  }'
```

### Тест 3: RAG запрос

```bash
curl -X POST http://localhost:8000/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain RAG architecture",
    "top_k": 5
  }'
```

---

## 📝 Расширенная конфигурация

### Включить Safety фильтрацию

```bash
# В .env добавьте:
SAFETY_MODE=llm
SAFETY_LLM_API_KEY=your-api-key
SAFETY_LLM_MODEL=openai/gpt-4o-mini
```

### Использовать Qdrant вместо ChromaDB

```bash
# В .env измените:
VECTOR_DB_PROVIDER=qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

**Миграция данных из ChromaDB в Qdrant:**
```bash
python scripts/migrate_vector_db.py --source chroma --target qdrant
```

### Включить Redis кеш

```bash
# В .env:
CACHE_BACKEND=redis
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Включить мониторинг (OTEL + Prometheus)

```bash
# В .env:
OTEL_ENABLED=true
PROMETHEUS_ENABLED=true
```

### 🔑 API аутентификация (автоматическая)

**С версии Docker:** API ключ создается автоматически при первом запуске!

При запуске через Docker Compose система автоматически:
1. Проверяет наличие admin API ключей
2. Если ключей нет - создает ключ по умолчанию с ролью ADMIN
3. Выводит ключ в логи при старте контейнера

**Найти ваш API ключ:**
```bash
# Простой способ (рекомендуется) - интерактивный помощник
./scripts/get_api_key.sh

# Или вручную:
# Посмотрите логи при первом запуске
docker compose logs api | grep "DEFAULT ADMIN API KEY"

# Проверьте сохранённый файл
docker compose exec api cat /app/data/.default_api_key

# Создайте новый ключ
docker compose exec api python scripts/bootstrap_admin_key.py
```

**Использовать API ключ:**
```bash
# Экспортируйте переменную окружения
export AVI_API_KEY=avi_xxxxxxxxxxxxxxxxx

# Используйте в запросах
curl -H "X-API-Key: $AVI_API_KEY" http://localhost:8000/api/v1/health
```

**Создать дополнительные ключи:**
```bash
# Через скрипт (интерактивно)
docker compose exec api python scripts/bootstrap_admin_key.py --name "My Key"

# Или через API (требуется существующий admin ключ)
curl -X POST http://localhost:8000/api/v1/admin/keys \
  -H "X-API-Key: $AVI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "New Key", "role": "user"}'
```

**Для локальной разработки:**
По умолчанию `REQUIRE_API_KEY=false` - аутентификация опциональна.
Для production установите `REQUIRE_API_KEY=true` в `.env`.

---

## 🔧 Полезные команды

### Makefile команды

```bash
make help              # Показать все доступные команды
make install-cpu       # Установить CPU версию (рекомендуется для dev)
make install-gpu       # Установить GPU версию (для production)
make run               # Запустить API сервер
make test              # Запустить все тесты
make test-smoke        # Быстрые smoke tests
make lint              # Проверить код (ruff + mypy)
make lint-fix          # Автофикс линтера
make type-check        # Проверка типов (mypy)
make docker-build-cpu  # Собрать Docker образ (CPU)
make docker-build-gpu  # Собрать Docker образ (GPU)
```

### CLI команды

```bash
python -m avi.cli setup-data          # Подготовка данных
python -m avi.cli index-data          # Индексация в vector DB
python -m avi.cli run-benchmarks      # Запуск бенчмарков
```

### Docker команды

```bash
docker compose up              # Запустить все сервисы
docker compose down            # Остановить
docker compose down -v         # Остановить + удалить volumes
docker compose logs api        # Логи API
docker compose exec api bash   # Shell внутри контейнера
```

---

## 🐛 Решение проблем

### Проблема: "MAIN_LLM_API_KEY is not set"

**Решение:**
```bash
# Проверьте, что .env создан и содержит ключ
cat .env | grep MAIN_LLM_API_KEY

# Убедитесь, что нет пробелов вокруг =
# Правильно:  MAIN_LLM_API_KEY=sk-xxx
# Неправильно: MAIN_LLM_API_KEY = sk-xxx
```

### Проблема: "No module named 'src'"

**Решение:**
```bash
# Убедитесь, что запускаете из корня проекта
cd /path/to/AVI

# Для pytest добавьте PYTHONPATH
PYTHONPATH=src pytest tests/
```

### Проблема: "Port 8000 already in use"

**Решение:**
```bash
# Найдите процесс
lsof -i :8000

# Убейте процесс
kill -9 <PID>

# Или запустите на другом порту
uvicorn main:app --port 8001
```

### Проблема: ChromaDB не создает индексы

**Решение:**
```bash
# Убедитесь, что директория существует
mkdir -p data/indexes/chroma

# Проверьте права доступа
chmod 755 data/indexes/chroma

# Переиндексируйте
python -m avi.cli index-data --force
```

### Проблема: Docker контейнер падает с OOM

**Решение:**
```bash
# Используйте CPU версию (экономит 3.2 GB памяти)
docker compose build --build-arg DEVICE=cpu api
docker compose up
```

---

## 📚 Следующие шаги

1. **Изучите API:** Откройте http://localhost:8000/docs
2. **Настройте правила фильтрации:** Отредактируйте `data/raw/filter_rules.csv`
3. **Добавьте свои документы:** `data/raw/vector_documents.csv`
4. **Запустите бенчмарки:** `python -m avi.cli run-benchmarks`
5. **Изучите React UI:** http://localhost:5173 (dev) или http://localhost:8000 (production build)

---

## 📖 Документация

- [API Reference](API.md) - Полное описание API endpoints
- [Architecture](ARCHITECTURE.md) - Архитектура системы
- [Deployment](deployment.md) - Production deployment
- [Runbook](runbook.md) - Operational runbook
- [Notebooks](notebooks.md) - Jupyter experiments

---

## 💡 Примеры использования

### Python клиент

```python
import httpx

async def query_avi(question: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/rag/query",
            json={
                "query": question,
                "top_k": 5,
                "mode": "hybrid"
            }
        )
        return response.json()

# Использование
result = await query_avi("Explain machine learning")
print(result["answer"])
```

### cURL примеры

```bash
# Hybrid mode (RAG + LLM)
curl -X POST http://localhost:8000/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG?", "mode": "hybrid"}'

# Streaming response
curl -X POST http://localhost:8000/rag/query/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Tell me a story", "mode": "llm"}' \
  --no-buffer

# Upload new rules
curl -X POST http://localhost:8000/upload/rules \
  -F "file=@my_rules.csv"

# Reindex
curl -X POST http://localhost:8000/reindex

# Stats
curl http://localhost:8000/stats
```

---

## 🎯 Рекомендации по выбору конфигурации

### Для разработки (локально)
```bash
VECTOR_DB_PROVIDER=chroma       # Простой file-based
CACHE_BACKEND=memory            # Не требует Redis
SAFETY_MODE=disabled            # Быстрее
OTEL_ENABLED=false              # Меньше overhead
```

### Для продакшена (Docker)
```bash
VECTOR_DB_PROVIDER=qdrant       # Масштабируемый
CACHE_BACKEND=redis             # Распределенный кеш
SAFETY_MODE=hybrid              # Максимальная защита
OTEL_ENABLED=true               # Полный мониторинг
PROMETHEUS_ENABLED=true
```

### Для экспериментов (Notebooks)
```bash
ENABLE_MLFLOW=true              # Трекинг экспериментов
ENABLE_WANDB=true               # Визуализация
RERANK_ENABLED=true             # Лучшее качество RAG
```

---

**Нужна помощь?** Создайте issue на GitHub или посмотрите [FAQ](FAQ.md)
