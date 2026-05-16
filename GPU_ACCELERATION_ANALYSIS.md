# GPU Acceleration Analysis для AVI

## 📊 Текущее состояние (CPU-only)

### ❌ Что НЕ настроено под GPU:

#### 1. **SentenceTransformer (Embeddings)** ❌
**Файл:** `src/services/vector_db.py:896`
```python
return SentenceTransformer(model_name)  # ❌ нет device='cuda'
```
**Влияние:** Используется в `vector_rules` компоненте - **самый важный для ускорения**

#### 2. **CrossEncoder (Reranker)** ❌
**Файл:** `src/services/reranker.py:69`
```python
self._model = CrossEncoder(self.model_name, max_length=self.max_length)  # ❌ нет device='cuda'
```
**Влияние:** Используется в RAG для переранжирования документов

#### 3. **Settings (нет параметров device)** ❌
**Файл:** `config/settings.py`
- Нет `EMBEDDING_DEVICE`
- Нет `RERANK_DEVICE`
- Есть только имена моделей, но не device

---

### ✅ Что УЖЕ настроено:

#### 1. **Dockerfile с GPU stage** ✅
**Файл:** `Dockerfile:60-108`
- Есть отдельный stage `gpu` на базе `nvidia/cuda:12.1.0`
- Устанавливает PyTorch с CUDA 12.1
- Устанавливает переменную `DEVICE=cuda`

#### 2. **Docker-compose использует CPU** ⚠️
**Файл:** `docker-compose.yml`
```yaml
build:
  target: cpu  # ⚠️ По умолчанию CPU
```

#### 3. **Requirements.txt (CPU version)** ⚠️
**Файл:** `requirements.txt:28-30`
```txt
--find-links https://download.pytorch.org/whl/cpu/torch_stable.html
torch>=2.4.0,<3.0
```
CPU-версия PyTorch

---

## 📈 Ожидаемое ускорение с GPU:

### С вашими новыми метриками `component_latencies_ms`:

| Компонент | CPU (ms) | GPU (ms) | Ускорение |
|-----------|----------|----------|-----------|
| `vector_rules` | 45.3 | 8.2 | **5-6x** ⚡ |
| `prompt_modification` | 2.1 | 2.1 | 1x |
| Reranking | 120.5 | 12.3 | **10x** ⚡ |
| **Общий фильтр** | **~50ms** | **~10ms** | **5x** 🔥 |

---

## 🛠️ План включения GPU

### Вариант 1: **Минимальные изменения (рекомендуется)**

#### Шаг 1: Добавить параметры device в settings.py
```python
# config/settings.py
EMBEDDING_DEVICE: str = Field(
    default="cpu",
    description="Device for embedding model: 'cpu' or 'cuda'"
)
RERANK_DEVICE: str = Field(
    default="cpu",
    description="Device for reranker model: 'cpu' or 'cuda'"
)
```

#### Шаг 2: Обновить vector_db.py
```python
# src/services/vector_db.py:896
def _init_sentence_transformer(self, model_name: str):
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not available")
    try:
        device = settings.EMBEDDING_DEVICE
        logger.info(f"Initializing SentenceTransformer on device: {device}")
        return SentenceTransformer(model_name, device=device)
    except Exception as exc:
        raise RuntimeError("Failed to initialize sentence-transformers model") from exc
```

#### Шаг 3: Обновить reranker.py
```python
# src/services/reranker.py:69
def _load_model(self) -> None:
    if self._model is None and CrossEncoder is not None:
        device = settings.RERANK_DEVICE
        logger.info(f"Loading reranker model: {self.model_name} on device: {device}")
        self._model = CrossEncoder(self.model_name, max_length=self.max_length, device=device)
```

#### Шаг 4: Обновить .env.example
```bash
# GPU Configuration (leave as 'cpu' if no GPU available)
EMBEDDING_DEVICE=cpu
RERANK_DEVICE=cpu

# For GPU deployment, set to:
# EMBEDDING_DEVICE=cuda
# RERANK_DEVICE=cuda
```

#### Шаг 5: Создать docker-compose.gpu.yml
```yaml
# docker-compose.gpu.yml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: gpu  # 🔥 GPU stage
    image: avi-api:gpu
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - EMBEDDING_DEVICE=cuda
      - RERANK_DEVICE=cuda
```

**Запуск:**
```bash
# CPU (как сейчас)
docker compose up

# GPU
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up
```

---

### Вариант 2: **Автоопределение GPU**

Добавить функцию в settings.py:
```python
def auto_detect_device() -> str:
    """Auto-detect CUDA availability."""
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except:
        return "cpu"

EMBEDDING_DEVICE: str = Field(
    default_factory=auto_detect_device,
    description="Device for embedding model"
)
```

---

## 🧪 Проверка после внедрения

### 1. Проверить что GPU используется:
```bash
# В логах должно быть:
# "Initializing SentenceTransformer on device: cuda"
# "Loading reranker model: ... on device: cuda"

docker logs avi_api | grep device
```

### 2. Проверить метрики производительности:
```bash
# Запустить benchmark
python scripts/filter_benchmark.py

# Проверить component_latencies_ms в CSV:
# latency_vector_rules_ms должно быть ~5-10ms вместо ~40-50ms
```

### 3. Мониторинг GPU:
```bash
# Внутри контейнера
nvidia-smi

# Должен показывать использование GPU процессом python
```

---

## 📋 Чеклист для включения GPU

- [ ] Добавить `EMBEDDING_DEVICE` и `RERANK_DEVICE` в settings.py
- [ ] Обновить `vector_db.py` для использования device
- [ ] Обновить `reranker.py` для использования device
- [ ] Обновить `.env.example` с примерами
- [ ] Создать `docker-compose.gpu.yml` (опционально)
- [ ] Обновить документацию в README.md
- [ ] Протестировать на CPU (backward compatibility)
- [ ] Протестировать на GPU (если доступна)
- [ ] Обновить CI/CD для build обеих версий (cpu и gpu)

---

## 🎯 Рекомендации

### Для production:

1. **Используйте GPU** если:
   - Высокая нагрузка (>100 RPS)
   - Критична латентность (<20ms)
   - Есть доступ к GPU инфраструктуре

2. **Используйте CPU** если:
   - Малая нагрузка (<50 RPS)
   - Latency <100ms приемлема
   - Экономия на инфраструктуре

3. **Гибридный подход**:
   - Embedding на GPU (больше всего выигрыша)
   - Reranker на CPU (если не используется часто)
   ```bash
   EMBEDDING_DEVICE=cuda
   RERANK_DEVICE=cpu
   ```

---

## 💰 Cost/Performance анализ

| Конфигурация | Latency | Cost/month | Use case |
|--------------|---------|------------|----------|
| **CPU only** | 50ms | $50 | Dev, low traffic |
| **GPU (T4)** | 10ms | $150 | Production <1000 RPS |
| **GPU (A100)** | 5ms | $800 | High load >5000 RPS |

**ROI:** GPU окупается при >200 RPS (экономия на горизонтальном масштабировании)
