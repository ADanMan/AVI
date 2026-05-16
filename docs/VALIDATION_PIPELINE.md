# Validation Pipeline - Руководство пользователя

## Обзор

Validation Pipeline - это комплексная система автоматической проверки кода AVI, которая обеспечивает:

1. **Согласованность API** между backend и frontend
2. **Качество кода** (дубликаты, сложность, размеры файлов)
3. **Корректность Docker** конфигурации

## Быстрый старт

### Локальный запуск

```bash
# Полная валидация
make validate

# Только API
make validate-api

# Только код
make validate-code

# Только Docker
make validate-docker
```

### Прямой запуск

```bash
# Полная валидация
python validate.py

# С параметрами
python validate.py --only api
python validate.py --skip docker
python validate.py --format json markdown
```

## Валидаторы

### 1. API Consistency Validator

Проверяет согласованность между backend API endpoints и frontend API вызовами.

**Что проверяет:**
- Frontend вызывает несуществующие endpoints
- Неиспользуемые backend endpoints
- Дублирующиеся определения endpoints
- Нормализация путей с параметрами

**Примеры проблем:**
```
❌ Frontend вызывает POST /api/v1/settings/monitoring, но этот endpoint не найден в backend
⚠️  Endpoint GET /health определен в нескольких файлах
ℹ️  Endpoint POST /api/admin/users не используется во frontend
```

### 2. Code Quality Validator

Анализирует качество кода и находит дубликаты.

**Что проверяет:**
- Дубликаты функций, классов, интерфейсов, типов
- Сложность функций (длина > 150 строк)
- Размеры файлов (> 1000 строк)
- Python и TypeScript код

**Примеры проблем:**
```
❌ Класс 'User' определен в 3 файлах
⚠️  Интерфейс 'Config' определен в 2 файлах
ℹ️  Функция 'process_data' слишком длинная (245 строк)
ℹ️  Файл routes.py слишком большой (1523 строк)
```

### 3. Docker Validator

Проверяет корректность Docker конфигурации.

**Что проверяет:**
- Наличие docker-compose.yml, Dockerfile, .env.example
- Корректность определения сервисов
- Зависимости между сервисами
- Volumes и порты
- Переменные окружения
- Безопасность (пароли, секреты)

**Примеры проблем:**
```
❌ Сервис api зависит от несуществующего сервиса database
❌ Порт 8000 используется несколькими сервисами
⚠️  Рекомендуется добавить healthcheck для сервиса redis
ℹ️  Переменная BENCHMARK_TRACKER не документирована в .env.example
```

## Форматы отчетов

### Console (по умолчанию)

Цветной отчет в терминале с группировкой по важности:
- 🔴 Высокая важность (блокируют CI/CD)
- 🟡 Средняя важность (предупреждения)
- ⚪ Низкая важность (рекомендации)

### JSON

Структурированный формат для интеграции с CI/CD:

```json
{
  "timestamp": "2025-11-15T10:00:00",
  "summary": {
    "total_issues": 119,
    "high_severity": 34,
    "medium_severity": 2,
    "low_severity": 83,
    "all_passed": false
  },
  "validators": {
    "api_consistency": { ... },
    "code_quality": { ... },
    "docker_config": { ... }
  }
}
```

### Markdown

Читаемый формат для документации и code review.

## Использование в разработке

### Pre-commit hook

Добавьте в `.git/hooks/pre-commit`:

```bash
#!/bin/bash
echo "Running validation pipeline..."
python validate.py --only api --format json

if [ $? -ne 0 ]; then
    echo "❌ Validation failed. Fix issues before committing."
    exit 1
fi
```

### Pre-push hook

Добавьте в `.git/hooks/pre-push`:

```bash
#!/bin/bash
echo "Running full validation..."
python validate.py --format json

if [ $? -ne 0 ]; then
    echo "❌ Validation failed. Fix high severity issues before pushing."
    exit 1
fi
```

## CI/CD интеграция

### GitHub Actions

Пайплайн автоматически запускается при:
- Push в ветки `main`, `develop`, `claude/**`
- Pull requests в `main`, `develop`

Workflow файл: `.github/workflows/validation.yml`

**Что делает:**
1. Запускает валидацию
2. Создает отчеты
3. Публикует комментарий в PR с результатами
4. Сохраняет артефакты (отчеты) на 30 дней
5. Блокирует PR при наличии критичных проблем

### Просмотр результатов CI/CD

1. Перейдите в Actions вашего репозитория
2. Выберите последний workflow "Validation Pipeline"
3. Скачайте артефакт "validation-reports"
4. Откройте `validation_report.md` или `validation_report.json`

## Настройка

### Конфигурация пайплайна

Файл: `validation_pipeline/config.py`

```python
# Пороги валидации
THRESHOLDS = {
    "code_similarity": 0.85,      # Порог схожести кода
    "max_function_length": 150,    # Максимальная длина функции
    "max_file_length": 1000,       # Максимальная длина файла
}

# Игнорируемые пути
IGNORE_PATHS = [
    "__pycache__",
    "node_modules",
    ".git",
    # ...
]
```

### Добавление файлов для проверки

```python
# Backend роутеры
BACKEND_ROUTES_FILES = [
    "routes.py",
    "admin_routes.py",
    # ... добавьте свои
]

# Frontend API клиенты
FRONTEND_API_FILES = [
    "indexing.ts",
    "filters.ts",
    # ... добавьте свои
]
```

## Интерпретация результатов

### Exit codes

- `0` - Все проверки пройдены (нет проблем высокой важности)
- `1` - Есть критичные проблемы (проблемы высокой важности)

### Уровни важности

**🔴 Высокая важность (High Severity)**
- Блокируют CI/CD
- Требуют немедленного исправления
- Примеры: несуществующие API endpoints, дублирующиеся классы

**🟡 Средняя важность (Medium Severity)**
- Предупреждения
- Рекомендуется исправить до мержа
- Примеры: дублирующиеся интерфейсы, отсутствие healthcheck

**⚪ Низкая важность (Low Severity)**
- Рекомендации
- Можно исправить позже
- Примеры: длинные функции, большие файлы, неиспользуемые endpoints

## Частые вопросы

### Q: Как часто запускать валидацию?

**A:** Рекомендуется:
- При каждом коммите: `make validate-api` (быстро)
- Перед push: `make validate` (полная проверка)
- Автоматически в CI/CD при PR

### Q: Можно ли игнорировать определенные проблемы?

**A:** Да, настройте `config.py`:
- Добавьте пути в `IGNORE_PATHS`
- Измените пороги в `THRESHOLDS`
- Закомментируйте файлы в `BACKEND_ROUTES_FILES` или `FRONTEND_API_FILES`

### Q: Валидация нашла ложное срабатывание, что делать?

**A:**
1. Проверьте, действительно ли это ложное срабатывание
2. Если да, улучшите парсер в `validation_pipeline/utils/parsers.py`
3. Или добавьте исключение в конфигурацию

### Q: Как добавить свой валидатор?

**A:** См. раздел "Расширение пайплайна" в `validation_pipeline/README.md`

### Q: Валидация занимает слишком много времени

**A:**
- Используйте `--only` для проверки только нужного валидатора
- Добавьте больше путей в `IGNORE_PATHS`
- В CI/CD используйте кеширование

### Q: Почему найдено много несоответствий API?

**A:** Это нормально на этапе разработки, когда:
- Frontend опережает backend
- Backend API еще не реализован
- Идет рефакторинг

Используйте результаты для планирования работ.

## Примеры использования

### Проверка перед коммитом

```bash
# Быстрая проверка API
make validate-api

# Если все ОК, коммит
git add .
git commit -m "feat: add new feature"
```

### Проверка перед PR

```bash
# Полная проверка
make validate-report

# Просмотр отчетов
cat validation_pipeline/reports/output/validation_report.md

# Исправить проблемы высокой важности
# Затем создать PR
```

### Анализ технического долга

```bash
# Генерировать отчет
make validate-report

# Анализировать JSON для метрик
python -c "
import json
with open('validation_pipeline/reports/output/validation_report.json') as f:
    data = json.load(f)
    print(f'Технический долг: {data['summary']['total_issues']} проблем')
"
```

### Мониторинг прогресса

```bash
# Запускать периодически и сохранять результаты
python validate.py --format json --output ./reports/$(date +%Y-%m-%d)

# Сравнивать динамику
```

## Дополнительная информация

- Полная документация: `validation_pipeline/README.md`
- Исходный код валидаторов: `validation_pipeline/validators/`
- Конфигурация: `validation_pipeline/config.py`
- GitHub Actions: `.github/workflows/validation.yml`

## Поддержка

При возникновении проблем:
1. Проверьте логи валидации
2. Убедитесь, что установлены зависимости: `pip install -r validation_pipeline/requirements.txt`
3. Создайте issue в репозитории с отчетом и логами
