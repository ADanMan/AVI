# 🧪 Тестирование автоматического создания API ключа

## Быстрый тест

### Вариант A: Минимальный тест (рекомендуется для быстрой проверки)

```bash
./test-minimal.sh
```

Запускает только необходимые сервисы (API, Redis, Qdrant) с отключенным мониторингом.
Быстрее и легче.

### Вариант B: Полный тест с мониторингом

```bash
./test-fresh-docker-start.sh
```

Запускает все сервисы включая Jaeger, MLflow, Prometheus.
Симулирует полное production окружение.

---

## Ручное тестирование

### Шаг 1: Полная очистка

```bash
# Остановить все контейнеры и удалить volumes (чтобы начать с чистого состояния)
docker compose down -v

# Опционально: удалить локальные данные
rm -rf data/security/api_keys.json data/.default_api_key
```

### Шаг 2: Пересобрать образы

```bash
# Пересобрать с новыми изменениями
docker compose build api
```

### Шаг 3: Запустить сервисы

```bash
# Запустить в фоне
docker compose up -d

# ИЛИ запустить с логами (чтобы видеть создание ключа)
docker compose up
```

### Шаг 4: Найти созданный API ключ

**Вариант A: В логах при старте**
```bash
docker compose logs api | grep -A 15 "DEFAULT ADMIN API KEY"
```

Вы увидите что-то вроде:
```
================================================================================
🔑 DEFAULT ADMIN API KEY CREATED
================================================================================

API Key Name: Docker Default Admin
API Key Role: ADMIN

Your API Key (save this, it won't be shown again):

    avi_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

================================================================================
```

**Вариант B: Из файла**
```bash
docker compose exec api cat /app/data/.default_api_key
```

### Шаг 5: Протестировать API

**Без аутентификации** (работает если `REQUIRE_API_KEY=false`):
```bash
curl http://localhost:8000/api/v1/health
```

**С API ключом**:
```bash
# Замените на ваш ключ
export AVI_API_KEY="avi_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

curl -H "X-API-Key: $AVI_API_KEY" http://localhost:8000/api/v1/health
```

### Шаг 6: Проверить Swagger UI

Откройте в браузере:
```
http://localhost:8000/docs
```

1. Нажмите кнопку **"Authorize"** 🔓
2. Введите ваш API ключ
3. Нажмите "Authorize"
4. Теперь вы можете делать запросы через Swagger!

---

## Что должно произойти

✅ При первом запуске:
- Скрипт `init_default_api_key.py` запускается через `docker-entrypoint.sh`
- Проверяется наличие admin API ключей
- Если ключей нет - создаётся новый с именем "Docker Default Admin"
- Ключ выводится в логи
- Ключ сохраняется в `/app/data/.default_api_key`

✅ При повторных запусках:
- Скрипт проверяет наличие admin ключей
- Если ключ уже есть - выводит сообщение "Admin API keys already exist"
- Новый ключ НЕ создаётся

---

## Устранение проблем

### Проблема: Ключ не создался

**Проверьте логи:**
```bash
docker compose logs api | grep -i "api key"
```

**Возможные причины:**
1. Admin ключ уже существует из предыдущего запуска
2. Ошибка при инициализации (смотрите traceback в логах)
3. Volume с данными не был удалён (`docker compose down -v`)

### Проблема: "404 Not Found" при обращении к `/health`

**Решение:** Используйте правильный путь:
```bash
# ✗ Неправильно
http://localhost:8000/health

# ✓ Правильно
http://localhost:8000/api/v1/health
```

### Проблема: Swagger UI не открывается

**Проверьте:**
1. API сервис запущен: `docker compose ps`
2. Порт 8000 доступен: `curl http://localhost:8000/docs`
3. Нет конфликта портов: `lsof -i :8000`

**Правильный URL для Swagger:**
```
http://localhost:8000/docs  (не просто /)
```

### Проблема: "Module not found" при локальном запуске скрипта

Это нормально - скрипт `init_default_api_key.py` требует зависимости из `requirements.txt`. Он предназначен для запуска внутри Docker контейнера, где все зависимости установлены.

---

## Проверка успешности

Тест прошёл успешно, если:

1. ✅ API ключ создан и виден в логах
2. ✅ Файл `/app/data/.default_api_key` содержит ключ
3. ✅ Healthcheck проходит: `curl http://localhost:8000/api/v1/health`
4. ✅ Swagger UI доступен: `http://localhost:8000/docs`
5. ✅ Аутентифицированный запрос работает с ключом
6. ✅ При повторном запуске новый ключ НЕ создаётся (т.к. уже есть admin)

---

## Симуляция нового пользователя

Чтобы максимально точно симулировать опыт нового пользователя:

```bash
# 1. Полная очистка
docker compose down -v
docker rmi avi-api:cpu 2>/dev/null || true
rm -rf data/

# 2. Клонировать .env.example (как новый пользователь)
cp .env.example .env
# Отредактируйте .env и установите MAIN_LLM_API_KEY

# 3. Запустить как в README
docker compose up --build

# 4. Проверить что система работает
curl http://localhost:8000/docs  # Должен вернуть HTML
docker compose logs api | grep "DEFAULT ADMIN API KEY"  # Должен показать ключ
```

Это полностью симулирует процесс, описанный в `README.md` и `docs/QUICKSTART.md`!
