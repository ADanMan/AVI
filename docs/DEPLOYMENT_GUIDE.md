# Руководство по развертыванию AVI

## Обзор

Этот документ содержит пошаговые инструкции по развертыванию системы AVI в различных средах и конфигурациях. Руководство покрывает все этапы от локальной разработки до production deployment с высокой доступностью.

**Дата создания:** 2025-11-14
**Версия:** 1.0
**Связанные задачи:** REFACTORING_PLAN.md - Задача 4.2

---

## 📊 Содержание

- [1. Предварительные требования](#1-предварительные-требования)
- [2. Локальное развертывание (Development)](#2-локальное-развертывание-development)
- [3. Docker Compose развертывание](#3-docker-compose-развертывание)
- [4. Production развертывание (Single Server)](#4-production-развертывание-single-server)
- [5. Production развертывание (Distributed)](#5-production-развертывание-distributed)
- [6. Kubernetes развертывание](#6-kubernetes-развертывание)
- [7. Cloud-Native развертывание](#7-cloud-native-развертывание)
- [8. Конфигурация и настройка](#8-конфигурация-и-настройка)
- [9. Мониторинг и логирование](#9-мониторинг-и-логирование)
- [10. Резервное копирование и восстановление](#10-резервное-копирование-и-восстановление)
- [11. Безопасность](#11-безопасность)
- [12. Troubleshooting](#12-troubleshooting)

---

## 1. Предварительные требования

### 1.1 Общие требования

Перед началом развертывания убедитесь, что у вас есть:

**Software:**
- ✅ Python 3.11+ (для локального развертывания)
- ✅ Docker 24.0+ и Docker Compose 2.20+ (для контейнеризации)
- ✅ Git (для клонирования репозитория)
- ✅ curl или wget (для проверки здоровья)

**Credentials:**
- ✅ LLM API ключ (OpenRouter, Anthropic, или OpenAI)
- ✅ (Optional) Safety LLM API ключ
- ✅ (Optional) Qdrant Cloud API ключ
- ✅ (Optional) Redis Cloud credentials
- ✅ (Optional) W&B API ключ

**System:**
- ✅ Права sudo (для production установки)
- ✅ Открытые порты (см. таблицу ниже)
- ✅ Достаточно дискового пространства (см. SYSTEM_REQUIREMENTS.md)

### 1.2 Открываемые порты

| Port | Service | Public? | Required? |
|------|---------|---------|-----------|
| 8000 | AVI API | Yes | Yes |
| 6333 | Qdrant (HTTP) | No | If using Qdrant |
| 6334 | Qdrant (gRPC) | No | If using Qdrant |
| 6379 | Redis | No | If using Redis |
| 3000 | Grafana | No | If monitoring |
| 9090 | Prometheus | No | If monitoring |
| 5000 | MLflow | No | If ML tracking |

### 1.3 Клонирование репозитория

```bash
git clone https://github.com/your-org/AVI.git
cd AVI
```

---

## 2. Локальное развертывание (Development)

**Use case:** Локальная разработка и тестирование
**Configuration:** `minimal`
**Time:** 15-30 минут
**System:** 2 CPU, 4 GB RAM, 10 GB Disk

### 2.1 Установка зависимостей

#### Option A: Using venv

```bash
# Создать виртуальное окружение
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate  # Windows

# Установить зависимости
pip install --upgrade pip
pip install -r requirements.txt
```

#### Option B: Using conda

```bash
# Создать conda окружение
conda create -n avi python=3.11
conda activate avi

# Установить зависимости
pip install -r requirements.txt
```

### 2.2 Настройка конфигурации

```bash
# Скопировать пример конфигурации
cp .env.example .env

# Применить minimal конфигурацию
cat data/configs/minimal.json
# Вручную скопировать нужные переменные в .env
```

**Минимальная .env конфигурация:**

```bash
# .env
ENVIRONMENT=development
DEBUG=true

# Main LLM (required)
MAIN_LLM_API_KEY=your_openrouter_key_here
MAIN_LLM_API_BASE=https://openrouter.ai/api/v1
MAIN_LLM_MODEL=anthropic/claude-3-5-sonnet-20241022

# Safety (disabled for local dev)
SAFETY_MODE=disabled
STREAM_GUARD_MODE=bypass

# Storage
VECTOR_DB_PROVIDER=chroma
VECTOR_DB_PATH=./data/indexes/chroma

# Cache
CACHE_BACKEND=memory
CACHE_TTL=3600

# Monitoring
PROMETHEUS_ENABLED=false
OTEL_ENABLED=false
```

### 2.3 Индексация данных

```bash
# Создать директории
mkdir -p data/raw data/indexes/chroma data/feedback logs

# Поместить CSV файлы в data/raw/
# - vector_rules.csv
# - vector_documents.csv
# - links.csv

# Запустить индексацию
python scripts/index_data.py

# Проверить результат
ls -lh data/indexes/chroma/
```

**Пример структуры CSV:**

`data/raw/vector_rules.csv`:
```csv
id,text,category,threshold,action
1,"Password leak detected","security",0.8,"block"
2,"PII information found","privacy",0.7,"sanitize"
```

`data/raw/vector_documents.csv`:
```csv
id,content,metadata,source
1,"Security policy document","{}","internal"
2,"Privacy guidelines","{}","compliance"
```

`data/raw/links.csv`:
```csv
rule_id,document_id,link_type
1,1,"reference"
2,2,"reference"
```

### 2.4 Запуск сервера

```bash
# Запустить в режиме разработки
python main.py

# Или с uvicorn напрямую (с hot reload)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2.5 Проверка работоспособности

```bash
# Health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs

# Test query
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"text": "What is AVI?", "stream": false}'
```

---

## 3. Docker Compose развертывание

**Use case:** Быстрое развертывание с изоляцией
**Configuration:** `recommended` или custom
**Time:** 30-60 минут
**System:** 4 CPU, 8 GB RAM, 50 GB Disk

### 3.1 Подготовка конфигурации

```bash
# Скопировать пример
cp .env.example .env

# Применить recommended конфигурацию
# Использовать data/configs/recommended.json как reference
```

**Recommended .env для Docker Compose:**

```bash
# Environment
ENVIRONMENT=production
DEBUG=false
REQUIRE_API_KEY=true
API_KEYS=your_api_key_here

# Main LLM
MAIN_LLM_API_KEY=your_key
MAIN_LLM_API_BASE=https://openrouter.ai/api/v1
MAIN_LLM_MODEL=anthropic/claude-3-5-sonnet-20241022

# Safety
SAFETY_MODE=hybrid
STREAM_GUARD_MODE=hybrid
SAFETY_SERVICE_URL=http://safety-service:8001
SAFETY_LLM_API_KEY=your_safety_key
SAFETY_LLM_MODEL=anthropic/claude-3-haiku-20240307

# Vector DB
VECTOR_DB_PROVIDER=qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# Cache
CACHE_BACKEND=redis
REDIS_URL=redis://redis:6379/0

# RAG
RERANK_ENABLED=true
RAG_THRESHOLD=0.75

# Monitoring
PROMETHEUS_ENABLED=true
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4318/v1/traces
ENABLE_MLFLOW=false

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_QUERY=30/minute
```

### 3.2 Индексация данных

```bash
# Поместить данные в data/raw/
# ...

# Запустить индексацию через docker
docker-compose run --rm api python scripts/index_data.py

# Или локально, если Python установлен
python scripts/index_data.py
```

### 3.3 Запуск сервисов

```bash
# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps

# Проверить логи
docker-compose logs -f api

# Проверить здоровье
curl http://localhost:8000/health
```

### 3.4 Включение опциональных сервисов

**Safety Service:**

Раскомментировать в `docker-compose.yml`:
```yaml
  safety-service:
    build:
      context: .
      dockerfile: safety_service/Dockerfile
    # ... rest of config
```

Затем:
```bash
docker-compose up -d safety-service
```

**Мониторинг стек:**

```bash
# Уже включены по умолчанию:
# - Prometheus (http://localhost:9090)
# - Grafana (http://localhost:3000)
# - Tempo (tracing)

# Проверить дашборды
open http://localhost:3000
# Login: admin / admin (первый раз)
```

### 3.5 Обновление конфигурации

```bash
# Изменить .env
vim .env

# Пересоздать контейнеры
docker-compose up -d --force-recreate api

# Или перезапустить все
docker-compose down
docker-compose up -d
```

---

## 4. Production развертывание (Single Server)

**Use case:** Small production (до 100 req/min)
**Configuration:** `lightweight` или `balanced`
**Time:** 2-4 часа
**System:** 4 CPU, 8 GB RAM, 50 GB SSD

### 4.1 Подготовка сервера

**Recommended OS:** Ubuntu 22.04 LTS

```bash
# Обновить систему
sudo apt update && sudo apt upgrade -y

# Установить зависимости
sudo apt install -y \
  git \
  curl \
  build-essential \
  python3.11 \
  python3.11-venv \
  python3-pip \
  docker.io \
  docker-compose \
  nginx \
  certbot \
  python3-certbot-nginx

# Добавить пользователя в docker группу
sudo usermod -aG docker $USER
newgrp docker

# Включить Docker при загрузке
sudo systemctl enable docker
sudo systemctl start docker
```

### 4.2 Настройка firewall

```bash
# Установить UFW
sudo apt install -y ufw

# Разрешить SSH
sudo ufw allow 22/tcp

# Разрешить HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Включить firewall
sudo ufw enable

# Проверить статус
sudo ufw status
```

### 4.3 Клонирование и настройка

```bash
# Создать директорию для приложения
sudo mkdir -p /opt/avi
sudo chown $USER:$USER /opt/avi

# Клонировать репозиторий
cd /opt/avi
git clone https://github.com/your-org/AVI.git .

# Создать .env
cp .env.example .env
vim .env
# Заполнить production значения

# Установить права
chmod 600 .env
```

### 4.4 Настройка Nginx

```bash
# Создать конфигурацию
sudo vim /etc/nginx/sites-available/avi
```

**Nginx config:**

```nginx
# /etc/nginx/sites-available/avi
upstream avi_api {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL certificates (will be added by certbot)
    # ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Client body size (для file uploads)
    client_max_body_size 10M;

    # Timeouts
    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;

    # Proxy to API
    location / {
        proxy_pass http://avi_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # CORS (если нужно)
        # add_header Access-Control-Allow-Origin "*" always;
    }

    # Health check endpoint (для мониторинга)
    location /health {
        proxy_pass http://avi_api/health;
        access_log off;
    }

    # Metrics endpoint (только internal)
    location /metrics {
        allow 127.0.0.1;
        deny all;
        proxy_pass http://avi_api/metrics;
    }

    # Access log
    access_log /var/log/nginx/avi_access.log;
    error_log /var/log/nginx/avi_error.log;
}
```

```bash
# Включить конфигурацию
sudo ln -s /etc/nginx/sites-available/avi /etc/nginx/sites-enabled/

# Тест конфигурации
sudo nginx -t

# Перезапустить nginx
sudo systemctl restart nginx
```

### 4.5 Настройка SSL (Let's Encrypt)

```bash
# Получить сертификат
sudo certbot --nginx -d your-domain.com

# Автоматическое обновление уже настроено
# Проверить renewal
sudo certbot renew --dry-run
```

### 4.6 Запуск AVI

```bash
cd /opt/avi

# Индексировать данные
docker-compose run --rm api python scripts/index_data.py

# Запустить сервисы
docker-compose up -d

# Проверить статус
docker-compose ps

# Проверить логи
docker-compose logs -f api
```

### 4.7 Настройка systemd service (альтернатива)

Для автоматического запуска при загрузке:

```bash
# Создать service файл
sudo vim /etc/systemd/system/avi.service
```

```ini
[Unit]
Description=AVI API Service
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/avi
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
# Включить и запустить
sudo systemctl daemon-reload
sudo systemctl enable avi
sudo systemctl start avi

# Проверить статус
sudo systemctl status avi
```

### 4.8 Настройка логирования

```bash
# Настроить log rotation
sudo vim /etc/logrotate.d/avi
```

```
/opt/avi/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    missingok
    create 0640 root root
    sharedscripts
    postrotate
        docker-compose -f /opt/avi/docker-compose.yml restart api >/dev/null 2>&1 || true
    endscript
}
```

---

## 5. Production развертывание (Distributed)

**Use case:** Medium-large production (100-1000 req/min)
**Configuration:** `recommended` или `high-security`
**Time:** 1-2 дня
**System:** Multiple servers

### 5.1 Архитектура

```
                    Internet
                        |
                   [Load Balancer]
                        |
        +---------------+---------------+
        |               |               |
   [API Server 1] [API Server 2] [API Server 3]
        |               |               |
        +---------------+---------------+
                        |
            +-----------+-----------+
            |           |           |
        [Redis]    [Qdrant]    [Monitoring]
```

### 5.2 Требования к серверам

**Load Balancer:**
- 2 CPU, 2 GB RAM
- Nginx или HAProxy

**API Servers (x2-3):**
- 4 CPU, 8 GB RAM each
- SSD storage

**Services Server:**
- 8 CPU, 16 GB RAM
- Runs: Redis, Qdrant, Prometheus, Grafana, Tempo

### 5.3 Настройка Load Balancer

**HAProxy config:**

```bash
# /etc/haproxy/haproxy.cfg
global
    log /dev/log local0
    log /dev/log local1 notice
    chroot /var/lib/haproxy
    stats socket /run/haproxy/admin.sock mode 660 level admin
    stats timeout 30s
    user haproxy
    group haproxy
    daemon

defaults
    log global
    mode http
    option httplog
    option dontlognull
    timeout connect 5000
    timeout client 600000
    timeout server 600000

frontend avi_frontend
    bind *:80
    bind *:443 ssl crt /etc/ssl/certs/your-domain.pem

    # Redirect HTTP to HTTPS
    redirect scheme https if !{ ssl_fc }

    # Security headers
    http-response set-header Strict-Transport-Security "max-age=31536000; includeSubDomains"

    default_backend avi_backend

backend avi_backend
    balance roundrobin
    option httpchk GET /health
    http-check expect status 200

    server api1 10.0.1.10:8000 check inter 10s fall 3 rise 2
    server api2 10.0.1.11:8000 check inter 10s fall 3 rise 2
    server api3 10.0.1.12:8000 check inter 10s fall 3 rise 2

listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s
    stats auth admin:your_password
```

### 5.4 Настройка API серверов

На каждом API сервере:

```bash
# Установить Docker
# ... (см. раздел 4.1)

# Клонировать репозиторий
cd /opt/avi
git clone https://github.com/your-org/AVI.git .

# Настроить .env с указанием на внешние сервисы
vim .env
```

**API server .env:**
```bash
# Pointing to services server
REDIS_URL=redis://10.0.1.20:6379/0
QDRANT_HOST=10.0.1.20
QDRANT_PORT=6333

# No local services
CACHE_BACKEND=redis
VECTOR_DB_PROVIDER=qdrant

# Rest of config...
```

```bash
# Запустить только API (без services)
docker-compose up -d api
```

### 5.5 Настройка Services Server

```bash
# Создать docker-compose для services
vim docker-compose.services.yml
```

```yaml
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    container_name: avi_redis
    command: ["redis-server", "--appendonly", "yes", "--bind", "0.0.0.0"]
    volumes:
      - /data/redis:/data
    ports:
      - "0.0.0.0:6379:6379"
    restart: always

  qdrant:
    image: qdrant/qdrant:v1.8.3
    container_name: avi_qdrant
    volumes:
      - /data/qdrant:/qdrant/storage
    ports:
      - "0.0.0.0:6333:6333"
      - "0.0.0.0:6334:6334"
    restart: always

  prometheus:
    image: prom/prometheus:v2.53.0
    container_name: avi_prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - /data/prometheus:/prometheus
    ports:
      - "0.0.0.0:9090:9090"
    restart: always

  grafana:
    image: grafana/grafana:10.4.5
    container_name: avi_grafana
    environment:
      GF_SECURITY_ADMIN_PASSWORD: your_password
    volumes:
      - /data/grafana:/var/lib/grafana
    ports:
      - "0.0.0.0:3000:3000"
    restart: always

  tempo:
    image: grafana/tempo:2.5.0
    container_name: avi_tempo
    command: ["-config.file=/etc/tempo.yaml"]
    volumes:
      - ./tempo.yaml:/etc/tempo.yaml:ro
      - /data/tempo:/var/tempo
    ports:
      - "0.0.0.0:3200:3200"
      - "0.0.0.0:4317:4317"
      - "0.0.0.0:4318:4318"
    restart: always
```

**Prometheus config для scraping API servers:**

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'avi-api'
    static_configs:
      - targets:
        - '10.0.1.10:8000'
        - '10.0.1.11:8000'
        - '10.0.1.12:8000'
    metrics_path: '/metrics'
    scrape_interval: 10s
```

```bash
# Запустить сервисы
docker-compose -f docker-compose.services.yml up -d
```

### 5.6 Настройка сетевой безопасности

**Firewall rules (на API серверах):**
```bash
# Разрешить только от Load Balancer
sudo ufw allow from 10.0.1.5 to any port 8000

# Разрешить SSH
sudo ufw allow 22/tcp

sudo ufw enable
```

**Firewall rules (на Services сервере):**
```bash
# Разрешить от API серверов
sudo ufw allow from 10.0.1.0/24 to any port 6379  # Redis
sudo ufw allow from 10.0.1.0/24 to any port 6333  # Qdrant
sudo ufw allow from 10.0.1.0/24 to any port 6334  # Qdrant gRPC
sudo ufw allow from 10.0.1.0/24 to any port 9090  # Prometheus

# Разрешить Grafana только от admin IPs
sudo ufw allow from YOUR_ADMIN_IP to any port 3000

sudo ufw enable
```

---

## 6. Kubernetes развертывание

**Use case:** Large production, auto-scaling
**Configuration:** `cloud-native`
**Time:** 2-3 дня
**System:** K8s cluster (3-5 nodes)

### 6.1 Требования

- Kubernetes 1.28+
- kubectl настроен
- Helm 3.12+
- Persistent storage (StorageClass)
- Ingress controller (nginx-ingress)

### 6.2 Создание namespace

```bash
# Создать namespace
kubectl create namespace avi

# Установить как default
kubectl config set-context --current --namespace=avi
```

### 6.3 Создание secrets

```bash
# LLM API keys
kubectl create secret generic avi-llm-secrets \
  --from-literal=main-api-key='your_main_llm_key' \
  --from-literal=safety-api-key='your_safety_llm_key'

# Application secrets
kubectl create secret generic avi-app-secrets \
  --from-literal=api-key='your_api_key'
```

### 6.4 Deployment manifests

**ConfigMap:**

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: avi-config
  namespace: avi
data:
  ENVIRONMENT: "production"
  DEBUG: "false"
  SAFETY_MODE: "hybrid"
  STREAM_GUARD_MODE: "hybrid"
  VECTOR_DB_PROVIDER: "qdrant"
  QDRANT_HOST: "qdrant-service"
  QDRANT_PORT: "6333"
  CACHE_BACKEND: "redis"
  REDIS_URL: "redis://redis-service:6379/0"
  RERANK_ENABLED: "true"
  RAG_THRESHOLD: "0.75"
  PROMETHEUS_ENABLED: "true"
  OTEL_ENABLED: "true"
  RATE_LIMIT_ENABLED: "true"
```

**Redis:**

```yaml
# redis.yaml
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: avi
spec:
  selector:
    app: redis
  ports:
    - port: 6379
      targetPort: 6379
  type: ClusterIP
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: avi
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command: ["redis-server", "--appendonly", "yes"]
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: redis-data
          mountPath: /data
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 2Gi
      volumes:
      - name: redis-data
        persistentVolumeClaim:
          claimName: redis-pvc
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-pvc
  namespace: avi
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

**Qdrant:**

```yaml
# qdrant.yaml
apiVersion: v1
kind: Service
metadata:
  name: qdrant-service
  namespace: avi
spec:
  selector:
    app: qdrant
  ports:
    - name: http
      port: 6333
      targetPort: 6333
    - name: grpc
      port: 6334
      targetPort: 6334
  type: ClusterIP
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: qdrant
  namespace: avi
spec:
  serviceName: qdrant-service
  replicas: 3
  selector:
    matchLabels:
      app: qdrant
  template:
    metadata:
      labels:
        app: qdrant
    spec:
      containers:
      - name: qdrant
        image: qdrant/qdrant:v1.8.3
        ports:
        - containerPort: 6333
          name: http
        - containerPort: 6334
          name: grpc
        volumeMounts:
        - name: qdrant-data
          mountPath: /qdrant/storage
        resources:
          requests:
            cpu: 1000m
            memory: 2Gi
          limits:
            cpu: 4000m
            memory: 8Gi
  volumeClaimTemplates:
  - metadata:
      name: qdrant-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 50Gi
```

**AVI API:**

```yaml
# api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: avi-api
  namespace: avi
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: avi-api
  template:
    metadata:
      labels:
        app: avi-api
    spec:
      containers:
      - name: api
        image: your-registry/avi-api:latest
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: MAIN_LLM_API_KEY
          valueFrom:
            secretKeyRef:
              name: avi-llm-secrets
              key: main-api-key
        - name: SAFETY_LLM_API_KEY
          valueFrom:
            secretKeyRef:
              name: avi-llm-secrets
              key: safety-api-key
        envFrom:
        - configMapRef:
            name: avi-config
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
        resources:
          requests:
            cpu: 2000m
            memory: 4Gi
          limits:
            cpu: 4000m
            memory: 8Gi
        volumeMounts:
        - name: data
          mountPath: /app/data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: avi-data-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: avi-api-service
  namespace: avi
spec:
  selector:
    app: avi-api
  ports:
    - port: 8000
      targetPort: 8000
  type: ClusterIP
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: avi-data-pvc
  namespace: avi
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 20Gi
```

**Ingress:**

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: avi-ingress
  namespace: avi
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "600"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - your-domain.com
    secretName: avi-tls-cert
  rules:
  - host: your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: avi-api-service
            port:
              number: 8000
```

**HorizontalPodAutoscaler:**

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: avi-api-hpa
  namespace: avi
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: avi-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
      - type: Pods
        value: 2
        periodSeconds: 15
      selectPolicy: Max
```

### 6.5 Применение манифестов

```bash
# Создать все ресурсы
kubectl apply -f configmap.yaml
kubectl apply -f redis.yaml
kubectl apply -f qdrant.yaml
kubectl apply -f api-deployment.yaml
kubectl apply -f ingress.yaml
kubectl apply -f hpa.yaml

# Проверить статус
kubectl get pods
kubectl get svc
kubectl get ingress

# Проверить логи
kubectl logs -f deployment/avi-api

# Масштабирование (manual)
kubectl scale deployment avi-api --replicas=5
```

### 6.6 Мониторинг в K8s

**Prometheus Operator:**

```bash
# Установить prometheus-operator через Helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false
```

**ServiceMonitor для AVI:**

```yaml
# servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: avi-api-metrics
  namespace: avi
  labels:
    app: avi-api
spec:
  selector:
    matchLabels:
      app: avi-api
  endpoints:
  - port: http
    path: /metrics
    interval: 15s
```

---

## 7. Cloud-Native развертывание

### 7.1 AWS (ECS + Managed Services)

**Architecture:**
- ECS Fargate for API (auto-scaling)
- ElastiCache Redis
- Qdrant Cloud
- ALB for load balancing
- CloudWatch for monitoring

**Steps:**

1. **Create VPC:**
```bash
aws ec2 create-vpc --cidr-block 10.0.0.0/16
```

2. **Create ECS Cluster:**
```bash
aws ecs create-cluster --cluster-name avi-cluster
```

3. **Create Task Definition:**
```json
{
  "family": "avi-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "avi-api",
      "image": "your-ecr-repo/avi-api:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "ENVIRONMENT", "value": "production"},
        {"name": "REDIS_URL", "value": "redis://your-elasticache.cache.amazonaws.com:6379/0"}
      ],
      "secrets": [
        {
          "name": "MAIN_LLM_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:avi/llm-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/avi-api",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

4. **Create Service with Auto-Scaling:**
```bash
aws ecs create-service \
  --cluster avi-cluster \
  --service-name avi-api-service \
  --task-definition avi-api \
  --desired-count 3 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

### 7.2 GCP (Cloud Run + Managed Services)

**Architecture:**
- Cloud Run for API (auto-scaling)
- Memorystore for Redis
- Qdrant Cloud
- Cloud Load Balancing
- Cloud Monitoring

**Deploy command:**

```bash
gcloud run deploy avi-api \
  --image gcr.io/your-project/avi-api:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --min-instances 2 \
  --max-instances 10 \
  --set-env-vars ENVIRONMENT=production,REDIS_URL=redis://your-memorystore-ip:6379/0 \
  --set-secrets MAIN_LLM_API_KEY=avi-llm-key:latest
```

### 7.3 Azure (Container Apps + Managed Services)

**Architecture:**
- Azure Container Apps
- Azure Cache for Redis
- Qdrant Cloud
- Azure Front Door
- Application Insights

---

## 8. Конфигурация и настройка

### 8.1 Выбор конфигурации

См. `data/configs/README.md` для полного списка.

**Quick reference:**

| Use Case | Configuration | File |
|----------|---------------|------|
| Development | minimal | `data/configs/minimal.json` |
| Low-risk prod | lightweight | `data/configs/lightweight.json` |
| Standard prod | recommended | `data/configs/recommended.json` |
| High-security | high-security | `data/configs/high-security.json` |
| High-traffic | high-performance | `data/configs/high-performance.json` |

### 8.2 Применение конфигурации

```bash
# Метод 1: Ручное копирование в .env
cat data/configs/recommended.json
# Скопировать нужные значения в .env

# Метод 2: Использование jq для парсинга
jq -r '.safety.SAFETY_MODE' data/configs/recommended.json
# Output: hybrid

# Метод 3: Python скрипт для конвертации
python scripts/config_to_env.py data/configs/recommended.json > .env
```

### 8.3 Проверка конфигурации

```bash
# Запустить скрипт проверки
python scripts/test_configurations.py \
  --config data/configs/recommended.json \
  --validate-only

# Или через API
curl http://localhost:8000/api/v1/config/validate
```

---

## 9. Мониторинг и логирование

### 9.1 Metrics (Prometheus)

**Prometheus targets:**

Добавить в `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'avi'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

**Key metrics to monitor:**

- `avi_requests_total` - Total requests
- `avi_request_duration_seconds` - Request latency
- `avi_input_filter_latency_seconds` - Input filter latency
- `avi_output_filter_latency_seconds` - Output filter latency
- `avi_llm_requests_total` - LLM API calls
- `avi_cache_hits_total` / `avi_cache_misses_total` - Cache hit rate

### 9.2 Tracing (Tempo/Jaeger)

**Enable in .env:**
```bash
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4318/v1/traces
```

**View traces:**
- Jaeger UI: http://localhost:16686
- Grafana: http://localhost:3000 (with Tempo datasource)

### 9.3 Logs

**Log levels:**
```bash
# Development
LOG_LEVEL=DEBUG

# Production
LOG_LEVEL=INFO
```

**Log aggregation:**

**Option A: Loki (with Grafana)**
```bash
# Install promtail for log shipping
docker run -d --name promtail \
  -v /opt/avi/logs:/var/log/avi \
  -v /path/to/promtail-config.yaml:/etc/promtail/config.yaml \
  grafana/promtail:latest
```

**Option B: ELK Stack**
- Elasticsearch for storage
- Logstash for processing
- Kibana for visualization

**Option C: Cloud-native**
- AWS: CloudWatch Logs
- GCP: Cloud Logging
- Azure: Application Insights

### 9.4 Alerting

**Prometheus AlertManager rules:**

```yaml
# alerts.yaml
groups:
- name: avi_alerts
  interval: 30s
  rules:
  - alert: HighErrorRate
    expr: rate(avi_requests_total{status="error"}[5m]) > 0.05
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value }} errors/sec"

  - alert: HighLatency
    expr: histogram_quantile(0.95, rate(avi_request_duration_seconds_bucket[5m])) > 5
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High latency detected"
      description: "P95 latency is {{ $value }} seconds"

  - alert: ServiceDown
    expr: up{job="avi"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "AVI service is down"
```

---

## 10. Резервное копирование и восстановление

### 10.1 Что нужно бэкапить

**Critical data:**
- Vector DB data (`data/indexes/`)
- Configuration files (`.env`)
- Custom CSV data (`data/raw/`)

**Optional data:**
- Redis cache (ephemeral)
- Logs (`logs/`)
- Prometheus metrics (can be rebuilt)

### 10.2 Backup стратегии

**Daily backups:**

```bash
#!/bin/bash
# /opt/avi/scripts/backup.sh

BACKUP_DIR=/backup/avi
DATE=$(date +%Y-%m-%d)

# Создать директорию для бэкапа
mkdir -p $BACKUP_DIR/$DATE

# Backup vector DB
tar -czf $BACKUP_DIR/$DATE/vector_db.tar.gz \
  -C /opt/avi/data indexes/

# Backup raw data
tar -czf $BACKUP_DIR/$DATE/raw_data.tar.gz \
  -C /opt/avi/data raw/

# Backup config
cp /opt/avi/.env $BACKUP_DIR/$DATE/.env

# Cleanup old backups (keep 7 days)
find $BACKUP_DIR -type d -mtime +7 -exec rm -rf {} \;

# Optional: Upload to S3
# aws s3 sync $BACKUP_DIR s3://your-bucket/avi-backups/
```

**Cron schedule:**
```bash
# Run daily at 2 AM
0 2 * * * /opt/avi/scripts/backup.sh
```

### 10.3 Восстановление

```bash
#!/bin/bash
# restore.sh

BACKUP_DATE=$1  # e.g., 2025-11-14
BACKUP_DIR=/backup/avi/$BACKUP_DATE

# Stop services
docker-compose down

# Restore vector DB
tar -xzf $BACKUP_DIR/vector_db.tar.gz \
  -C /opt/avi/data

# Restore raw data
tar -xzf $BACKUP_DIR/raw_data.tar.gz \
  -C /opt/avi/data

# Restore config
cp $BACKUP_DIR/.env /opt/avi/.env

# Start services
docker-compose up -d

echo "Restore completed from backup: $BACKUP_DATE"
```

### 10.4 Disaster Recovery Plan

**RTO (Recovery Time Objective):** 1-4 hours
**RPO (Recovery Point Objective):** 24 hours (daily backups)

**Steps:**
1. Provision new infrastructure
2. Restore latest backup
3. Update DNS records
4. Verify functionality
5. Monitor for issues

---

## 11. Безопасность

### 11.1 API Key Authentication

**Enable in .env:**
```bash
REQUIRE_API_KEY=true
API_KEYS=key1,key2,key3
```

**Usage:**
```bash
curl -H "X-API-Key: key1" http://localhost:8000/api/v1/query
```

### 11.2 Rate Limiting

**Configure in .env:**
```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_QUERY=30/minute
RATE_LIMIT_UPLOAD=10/minute
```

### 11.3 TLS/SSL

**Production requirements:**
- ✅ TLS 1.2+ only
- ✅ Strong cipher suites
- ✅ HSTS header
- ✅ Certificate from trusted CA

### 11.4 Network Security

**Recommendations:**
- Use private networks for internal services
- Restrict access to admin interfaces (Grafana, Prometheus)
- Enable firewall rules
- Use security groups / Network ACLs
- Regular security audits

### 11.5 Secrets Management

**Options:**

**Option A: Environment variables (basic)**
```bash
# .env (with restricted permissions)
chmod 600 .env
```

**Option B: Docker secrets**
```bash
echo "my_secret" | docker secret create llm_api_key -
```

**Option C: Cloud secrets managers**
- AWS: Secrets Manager
- GCP: Secret Manager
- Azure: Key Vault
- HashiCorp Vault

**Option D: Kubernetes secrets**
```bash
kubectl create secret generic avi-secrets \
  --from-literal=api-key='xxx'
```

---

## 12. Troubleshooting

### 12.1 Common Issues

#### API не запускается

**Symptoms:** Container exits immediately

**Check:**
```bash
docker-compose logs api
```

**Common causes:**
- Missing environment variables
- Invalid LLM API key
- Port already in use

**Solution:**
```bash
# Check env vars
docker-compose config

# Check port
sudo lsof -i :8000

# Validate config
python -c "from config.settings import settings; print(settings.MAIN_LLM_API_KEY)"
```

#### High latency

**Symptoms:** Requests taking >5 seconds

**Check:**
```bash
# Check component latency
curl http://localhost:8000/metrics | grep latency

# Check LLM API status
curl https://status.openrouter.ai
```

**Common causes:**
- Slow LLM API response
- Safety checks enabled (adds 100-500ms)
- Reranking enabled (adds 50-200ms)
- Network issues

**Solution:**
- Use faster safety mode (local instead of external)
- Disable reranking for development
- Check network latency to LLM provider

#### Vector search not working

**Symptoms:** No results or errors

**Check:**
```bash
# Verify index exists
ls -lh data/indexes/chroma/

# Check vector DB logs
docker-compose logs qdrant
```

**Common causes:**
- Data not indexed
- Wrong VECTOR_DB_PROVIDER setting
- Qdrant not running

**Solution:**
```bash
# Reindex data
python scripts/index_data.py

# Verify
curl http://localhost:8000/api/v1/stats
```

#### Redis connection errors

**Symptoms:** Cache errors in logs

**Check:**
```bash
# Test Redis connection
redis-cli -h localhost -p 6379 ping

# Check Docker
docker-compose ps redis
```

**Solution:**
```bash
# Restart Redis
docker-compose restart redis

# Or fallback to memory cache
# In .env: CACHE_BACKEND=memory
```

### 12.2 Debug Mode

**Enable debug logging:**
```bash
# .env
DEBUG=true
LOG_LEVEL=DEBUG
```

**View detailed traces:**
```bash
docker-compose logs -f --tail=100 api
```

### 12.3 Health Checks

**API health:**
```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "checks": {
    "vector_db": "ok",
    "cache": "ok",
    "llm": "ok"
  }
}
```

**Component checks:**
```bash
# Qdrant
curl http://localhost:6333/healthz

# Redis
redis-cli -h localhost -p 6379 ping

# Prometheus
curl http://localhost:9090/-/healthy
```

---

## 13. Migration Guides

### 13.1 Migration between configurations

См. `docs/CONFIGURATION_MATRIX.md` секция "Migration Paths"

### 13.2 Upgrading AVI version

```bash
# Backup current installation
/opt/avi/scripts/backup.sh

# Pull latest code
cd /opt/avi
git pull origin main

# Rebuild images
docker-compose build

# Run migrations (if any)
docker-compose run --rm api python scripts/migrate.py

# Restart services
docker-compose up -d --force-recreate

# Verify
curl http://localhost:8000/health
```

---

## 14. Performance Tuning

### 14.1 API Server Tuning

**Uvicorn workers:**
```bash
# In docker-compose.yml
command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Formula:** `workers = (2 * CPU cores) + 1`

### 14.2 Vector DB Tuning

**ChromaDB:**
- Use SSD storage
- Increase RAM for larger indexes
- Batch queries when possible

**Qdrant:**
```yaml
# Optimize HNSW parameters
storage:
  hnsw_config:
    m: 16  # Lower = less memory, higher = faster search
    ef_construct: 100  # Higher = better index quality
    ef: 128  # Higher = better search quality
```

### 14.3 Cache Tuning

**Redis:**
```ini
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
```

**Cache TTL:**
```bash
# Shorter for development
CACHE_TTL=300  # 5 minutes

# Longer for production
CACHE_TTL=3600  # 1 hour
```

---

## 15. Related Documentation

- **System Requirements:** `docs/SYSTEM_REQUIREMENTS.md`
- **Configuration Matrix:** `docs/CONFIGURATION_MATRIX.md`
- **Configuration Files:** `data/configs/README.md`
- **API Documentation:** http://localhost:8000/docs
- **Performance Analysis:** `docs/FILTER_PERFORMANCE_ANALYSIS.md`

---

## 16. Support and Community

**Issues:** https://github.com/your-org/AVI/issues
**Discussions:** https://github.com/your-org/AVI/discussions
**Documentation:** https://docs.avi.example.com

---

**Version:** 1.0
**Last Updated:** 2025-11-14
**Maintainers:** AVI Team
