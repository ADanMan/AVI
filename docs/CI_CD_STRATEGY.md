# CI/CD Strategy for AVI

## Обзор стратегии

Комплексная CI/CD стратегия для обеспечения качества, безопасности и надежности AVI.

## Матрица проверок

| Проверка | Когда | Блокирует PR | Приоритет | Время выполнения |
|----------|-------|--------------|-----------|------------------|
| Validation Pipeline | Push, PR | ✅ Да | 🔴 Критичный | ~30 сек |
| Linting & Formatting | Push, PR | ✅ Да | 🔴 Критичный | ~15 сек |
| Type Checking | Push, PR | ✅ Да | 🔴 Критичный | ~20 сек |
| Unit Tests | Push, PR | ✅ Да | 🔴 Критичный | ~2 мин |
| Integration Tests | PR | ✅ Да | 🟡 Высокий | ~5 мин |
| Security Scan | Push, PR | ⚠️ Опционально | 🟡 Высокий | ~1 мин |
| Dependency Check | Daily, PR | ⚠️ Опционально | 🟢 Средний | ~30 сек |
| Docker Build | PR, Main | ✅ Да | 🔴 Критичный | ~5 мин |
| UI Build | PR, Main | ✅ Да | 🔴 Критичный | ~1 мин |
| E2E Tests | Nightly, Main | ❌ Нет | 🟢 Средний | ~10 мин |
| Performance Tests | Weekly, Main | ❌ Нет | 🟢 Средний | ~15 мин |

## 1. Code Quality Checks

### 1.1. Linting & Formatting

**Инструменты:**
- Python: `ruff`, `black`, `isort`
- TypeScript: `eslint`, `prettier`

**Workflow:** `.github/workflows/lint.yml`

```yaml
name: Lint & Format

on: [push, pull_request]

jobs:
  python-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install ruff black isort
      - name: Ruff check
        run: ruff check src tests scripts
      - name: Black check
        run: black --check src tests scripts
      - name: Isort check
        run: isort --check-only src tests scripts

  typescript-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: ui/package-lock.json
      - name: Install dependencies
        run: cd ui && npm ci
      - name: ESLint
        run: cd ui && npm run lint
```

### 1.2. Type Checking

**Инструменты:**
- Python: `mypy`
- TypeScript: `tsc`

**Workflow:** `.github/workflows/typecheck.yml`

```yaml
name: Type Check

on: [push, pull_request]

jobs:
  python-types:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install mypy types-pyyaml types-redis
      - name: MyPy check
        run: mypy src --ignore-missing-imports

  typescript-types:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install dependencies
        run: cd ui && npm ci
      - name: TypeScript check
        run: cd ui && npm run type-check
```

## 2. Testing Strategy

### 2.1. Unit Tests

**Coverage:** Минимум 70% для новых изменений

**Workflow:** `.github/workflows/test-unit.yml`

```yaml
name: Unit Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev,testing]"

      - name: Run tests with coverage
        run: |
          pytest tests/unit --cov=src --cov-report=xml --cov-report=term

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: true

      - name: Check coverage threshold
        run: |
          coverage report --fail-under=70
```

### 2.2. Integration Tests

**Требования:** Docker, docker-compose

**Workflow:** `.github/workflows/test-integration.yml`

```yaml
name: Integration Tests

on:
  pull_request:
  push:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

      qdrant:
        image: qdrant/qdrant:v1.8.3
        ports:
          - 6333:6333

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -e ".[dev,testing]"

      - name: Run integration tests
        env:
          REDIS_URL: redis://localhost:6379/0
          QDRANT_HOST: localhost
          QDRANT_PORT: 6333
        run: pytest tests/integration -v
```

### 2.3. E2E Tests

**Инструменты:** Playwright для UI, pytest для API

**Workflow:** `.github/workflows/test-e2e.yml`

```yaml
name: E2E Tests

on:
  schedule:
    - cron: '0 2 * * *'  # Nightly at 2 AM
  workflow_dispatch:     # Manual trigger

jobs:
  e2e:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Start services
        run: docker-compose up -d

      - name: Wait for services
        run: |
          sleep 30
          curl --retry 10 --retry-delay 5 http://localhost:8000/health

      - name: Install Playwright
        run: |
          cd ui
          npm ci
          npx playwright install --with-deps

      - name: Run E2E tests
        run: cd ui && npm run test:e2e

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: e2e-results
          path: ui/test-results/
```

## 3. Security Checks

### 3.1. Dependency Scanning

**Инструменты:**
- Python: `safety`, `pip-audit`
- npm: `npm audit`
- GitHub: Dependabot

**Workflow:** `.github/workflows/security.yml`

```yaml
name: Security Scan

on:
  push:
    branches: [main, develop]
  pull_request:
  schedule:
    - cron: '0 0 * * *'  # Daily

jobs:
  python-security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install safety pip-audit

      - name: Safety check
        run: safety check --json
        continue-on-error: true

      - name: Pip audit
        run: pip-audit
        continue-on-error: true

  npm-security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: npm audit
        run: cd ui && npm audit --audit-level=moderate
        continue-on-error: true

  trivy-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'

      - name: Upload Trivy results to GitHub Security
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'
```

### 3.2. Secret Scanning

**Инструмент:** `gitleaks`

```yaml
name: Secret Scan

on: [push, pull_request]

jobs:
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Gitleaks scan
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 3.3. Code Security Analysis

**Инструмент:** CodeQL

```yaml
name: CodeQL Analysis

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  schedule:
    - cron: '0 0 * * 1'  # Weekly

jobs:
  analyze:
    runs-on: ubuntu-latest
    permissions:
      security-events: write

    strategy:
      matrix:
        language: ['python', 'javascript']

    steps:
      - uses: actions/checkout@v4

      - name: Initialize CodeQL
        uses: github/codeql-action/init@v2
        with:
          languages: ${{ matrix.language }}

      - name: Autobuild
        uses: github/codeql-action/autobuild@v2

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v2
```

## 4. Build & Deploy

### 4.1. Docker Build

**Проверка:** Успешная сборка образов

**Workflow:** `.github/workflows/docker.yml`

```yaml
name: Docker Build

on:
  pull_request:
  push:
    branches: [main, develop]
    tags: ['v*']

jobs:
  build:
    runs-on: ubuntu-latest

    strategy:
      matrix:
        target: [cpu, gpu]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile
          target: ${{ matrix.target }}
          push: false
          tags: avi-api:${{ matrix.target }}-test
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Test Docker image
        run: |
          docker run --rm avi-api:${{ matrix.target }}-test python -c "import src; print('OK')"
```

### 4.2. UI Build

**Workflow:** `.github/workflows/ui-build.yml`

```yaml
name: UI Build

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: ui/package-lock.json

      - name: Install dependencies
        run: cd ui && npm ci

      - name: Build UI
        run: cd ui && npm run build

      - name: Check bundle size
        run: |
          cd ui/dist
          SIZE=$(du -sb . | cut -f1)
          MAX_SIZE=$((10 * 1024 * 1024))  # 10 MB
          if [ $SIZE -gt $MAX_SIZE ]; then
            echo "Bundle too large: $SIZE bytes (max: $MAX_SIZE)"
            exit 1
          fi

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: ui-build
          path: ui/dist/
```

## 5. Performance & Monitoring

### 5.1. Performance Tests

**Инструменты:** `locust`, `k6`

**Workflow:** `.github/workflows/performance.yml`

```yaml
name: Performance Tests

on:
  schedule:
    - cron: '0 3 * * 0'  # Weekly on Sunday
  workflow_dispatch:

jobs:
  load-test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Start services
        run: docker-compose up -d

      - name: Wait for services
        run: sleep 30

      - name: Install k6
        run: |
          curl https://github.com/grafana/k6/releases/download/v0.47.0/k6-v0.47.0-linux-amd64.tar.gz -L | tar xvz
          sudo mv k6-*/k6 /usr/local/bin/

      - name: Run load tests
        run: k6 run tests/performance/load_test.js

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: performance-results
          path: performance-results/
```

### 5.2. Image Size Check

```yaml
name: Docker Image Size

on: [pull_request]

jobs:
  check-size:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: docker-compose build api

      - name: Check image size
        run: |
          SIZE=$(docker images avi-api:cpu --format "{{.Size}}")
          echo "Image size: $SIZE"
          # Add size limit check if needed
```

## 6. Documentation

### 6.1. Documentation Check

```yaml
name: Documentation

on: [pull_request]

jobs:
  docs:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Check for documentation updates
        run: |
          # Check if code changes include doc updates
          git diff --name-only origin/main... | grep -q '^docs/' || \
          echo "::warning::Consider updating documentation"

      - name: Validate Markdown
        uses: DavidAnson/markdownlint-action@v1
        with:
          globs: '**/*.md'
```

## 7. Pre-commit & Pre-push Hooks

### Pre-commit Hook

`.git/hooks/pre-commit`:

```bash
#!/bin/bash
set -e

echo "🔍 Running pre-commit checks..."

# Format check
echo "📝 Checking formatting..."
make lint || { echo "❌ Linting failed"; exit 1; }

# Type check
echo "🔤 Checking types..."
mypy src --ignore-missing-imports || { echo "❌ Type check failed"; exit 1; }

# Quick validation
echo "✅ Running quick validation..."
python validate.py --only api --format json || { echo "❌ API validation failed"; exit 1; }

echo "✅ Pre-commit checks passed!"
```

### Pre-push Hook

`.git/hooks/pre-push`:

```bash
#!/bin/bash
set -e

echo "🚀 Running pre-push checks..."

# Full validation
echo "🔍 Running validation pipeline..."
make validate || { echo "❌ Validation failed"; exit 1; }

# Unit tests
echo "🧪 Running unit tests..."
make test-smoke || { echo "❌ Tests failed"; exit 1; }

echo "✅ Pre-push checks passed!"
```

## 8. Приоритизация CI

### Fast Feedback (< 5 min)
1. Validation Pipeline
2. Linting & Formatting
3. Type Checking
4. Unit Tests (быстрые)

### Normal (5-15 min)
1. Integration Tests
2. Docker Build
3. UI Build
4. Security Scan

### Slow (> 15 min)
1. E2E Tests
2. Performance Tests
3. Full security audit

## 9. Branch Protection Rules

Рекомендуемые настройки для `main` и `develop`:

```yaml
Required status checks:
  - Validation Pipeline
  - Lint & Format (Python)
  - Lint & Format (TypeScript)
  - Type Check
  - Unit Tests
  - Integration Tests
  - Docker Build
  - UI Build

Additional settings:
  - Require pull request reviews: 1
  - Dismiss stale reviews: true
  - Require review from Code Owners: true
  - Require linear history: true
  - Include administrators: true
```

## 10. Мониторинг CI/CD

### Метрики для отслеживания

1. **Build Success Rate** - % успешных билдов
2. **Mean Time to Feedback** - среднее время до получения результата CI
3. **Flaky Tests Rate** - % нестабильных тестов
4. **Coverage Trend** - динамика покрытия тестами
5. **Security Vulnerabilities** - количество уязвимостей

### Дашборд

Использовать GitHub Insights или настроить Grafana для мониторинга:
- Время выполнения workflows
- Частота падений
- Размер артефактов
- Использование Actions minutes

## Итоговая архитектура CI/CD

```
┌─────────────────────────────────────────────────────────────┐
│                         Developer                            │
└────────────┬────────────────────────────────────┬───────────┘
             │                                    │
             │ git commit                         │ git push
             │                                    │
             ▼                                    ▼
      ┌──────────────┐                    ┌──────────────┐
      │ Pre-commit   │                    │  Pre-push    │
      │  - Lint      │                    │  - Validate  │
      │  - Type      │                    │  - Test      │
      └──────────────┘                    └──────────────┘
                                                  │
                                                  ▼
                                          ┌──────────────┐
                                          │   GitHub     │
                                          │   Actions    │
                                          └──────┬───────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    │                            │                            │
                    ▼                            ▼                            ▼
            ┌──────────────┐            ┌──────────────┐            ┌──────────────┐
            │ Fast Checks  │            │Normal Checks │            │ Slow Checks  │
            │ - Validation │            │ - Integration│            │ - E2E        │
            │ - Lint       │            │ - Docker     │            │ - Performance│
            │ - Type       │            │ - Security   │            │ - Full Audit │
            │ - Unit Tests │            │ - UI Build   │            │              │
            └──────┬───────┘            └──────┬───────┘            └──────┬───────┘
                   │                           │                           │
                   └───────────────────────────┼───────────────────────────┘
                                               │
                                               ▼
                                       ┌──────────────┐
                                       │   Deploy     │
                                       │ (if passed)  │
                                       └──────────────┘
```

## Следующие шаги

1. ✅ Создать workflow файлы в `.github/workflows/`
2. ✅ Настроить branch protection rules
3. ✅ Добавить pre-commit hooks
4. ✅ Настроить Dependabot
5. ✅ Настроить мониторинг CI/CD
