# AVI — Agreement Validation Interface

[![DOI](https://img.shields.io/badge/DOI-10.3390%2Felectronics15102125-blue)](https://doi.org/10.3390/electronics15102125)
[![CI](https://github.com/ADanMan/AVI/actions/workflows/ci.yml/badge.svg)](https://github.com/ADanMan/AVI/actions/workflows/ci.yml)
[![Smoke Tests](https://github.com/ADanMan/AVI/actions/workflows/smoke-tests.yml/badge.svg)](https://github.com/ADanMan/AVI/actions/workflows/smoke-tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

Official implementation of **Dynamic Bilateral Alignment (DBA)** from the paper:

> **Decoupling Intelligence from Governance: A Dynamic Bilateral Architecture for Real-Time Enterprise AI Compliance**  
> Danila Katalshov, Olga Shvetsova, Sang-Kon Lee, Sviatlana Koltun  
> *Electronics* 2026, 15(10), 2125 · [https://doi.org/10.3390/electronics15102125](https://doi.org/10.3390/electronics15102125)

AVI is a modular governance middleware that sits between your application and any LLM. It enforces compliance policies at both **input** (what the user sends) and **output** (what the model returns) using vector-based semantic retrieval — no model retraining required.

---

## Key Results

Validated against [FinanceBench](https://huggingface.co/datasets/PatronusAI/financebench) (N=150 queries, 3 repeated runs):

| Metric | Baseline (no AVI) | AVI |
|---|---|---|
| LLM-judge compliance rate | 63.7% | **83.2%** (↑+19.5 pp, p=0.002) |
| Vector filter Precision / Recall / F1 | — | **1.000 / 1.000 / 1.000** |
| Time-to-Compliance (new rule) | ~hours (fine-tuning) | **< 5 seconds** (re-indexing) |

Cross-domain validation on 201 Russian-language provocative queries: Recall=0.985, LLM compliance among triggered queries=0.977.

---

## How It Works

```
User Query
    │
    ▼
┌─────────────────────────────┐
│  Input Filter               │  Vector search over policy rules
│  (content_filter.py)        │  → block / sanitize / pass
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  RAG System                 │  Retrieve relevant context
│  (rag_system.py)            │  + cross-encoder reranking
└──────────────┬──────────────┘
               │
               ▼
         [ Your LLM ]
               │
               ▼
┌─────────────────────────────┐
│  Output Guard               │  Stream-level output filtering
│  (streaming_guard.py)       │
└──────────────┬──────────────┘
               │
               ▼
         Response
```

Policies are plain CSV rows (`data/raw/filter_rules.csv`). Adding a rule takes seconds and is immediately effective — no deployment, no retraining.

---

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/ADanMan/AVI.git
cd AVI
cp .env.example .env
# Set MAIN_LLM_API_KEY and MAIN_LLM_MODEL in .env
docker compose up --build
```

Services after startup:

| Service | URL |
|---|---|
| API + Swagger | http://localhost:8000/docs |
| Gradio Chat UI | http://localhost:7860 |
| Grafana dashboards | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Jaeger traces | http://localhost:16686 |
| MLflow | http://localhost:5000 |

### Local (CPU, ~5 min)

```bash
git clone https://github.com/ADanMan/AVI.git
cd AVI
python -m venv venv && source venv/bin/activate
make install-cpu          # CPU-only ML deps, ~200 MB
cp .env.example .env      # set MAIN_LLM_API_KEY
make init-project         # create dirs, generate admin key
make run-api              # http://localhost:8000/docs
```

Minimum `.env` configuration:

```bash
MAIN_LLM_API_KEY=sk-or-v1-...       # required
MAIN_LLM_MODEL=openai/gpt-4o-mini   # or any OpenAI-compatible model
```

---

## Reproducing Paper Results

The `research_toolkit/` directory contains everything needed to reproduce the FinanceBench experiment from the paper.

```bash
cd research_toolkit

# 1. Download FinanceBench from HuggingFace
python scripts/01_download_financebench.py

# 2. Build experiment dataset (generate policy contexts via LLM)
python scripts/02_transform_dataset.py

# 3. Run experiment: baseline vs AVI (N=150, 3 runs)
python scripts/03_run_experiment.py

# 4. Generate figures and tables
python scripts/04_generate_visualizations.py
```

Interactive versions of all steps are available as Jupyter notebooks in `research_toolkit/notebooks/`.

> The Russian-language provocative dataset (N=201) used for cross-domain validation is proprietary and not publicly available, as noted in the paper.

---

## Safety Modes

AVI supports four safety configurations:

| Mode | Description | Latency overhead |
|---|---|---|
| `disabled` | Vector filter only (fastest) | ~10–50 ms |
| `external` | Vector filter + external LLM sanitization | ~200–800 ms |
| `local` | Vector filter + local safety microservice | ~50–200 ms |
| `hybrid` | local + external fallback | ~50–800 ms |

Set via `SAFETY_MODE` in `.env`. All modes share the same vector-based input filter; the mode controls the LLM sanitization step for flagged queries.

Pluggable safety models are supported — see [`docs/SAFETY_PLUGINS.md`](docs/SAFETY_PLUGINS.md) and [`examples/safety_plugins/`](examples/safety_plugins/).

---

## Adding Compliance Rules

Rules are CSV rows indexed into the vector database. No code changes or restarts required.

```csv
id,text,category,risk_level,threshold
rule_0,"Do not provide specific investment advice or price predictions.",financial_compliance,5,0.42
rule_1,"Do not reveal internal API credentials or infrastructure details.",information_security,5,0.40
```

Index new rules:

```bash
make index-data
# or: python scripts/index_data.py
```

Time-to-Compliance: under 5 seconds for a typical ruleset.

---

## Production Checklist

Before deploying to production:

- [ ] Set `REQUIRE_API_KEY=true` and rotate the admin key
- [ ] Switch vector DB to Qdrant (`VECTOR_DB_PROVIDER=qdrant`)
- [ ] Enable Redis for distributed caching (`REDIS_URL=...`)
- [ ] Configure rate limits (`RATE_LIMIT_PER_MINUTE`)
- [ ] Set `SAFETY_MODE` appropriate for your compliance requirements
- [ ] Review [`docs/PRODUCTION_CHECKLIST.md`](docs/PRODUCTION_CHECKLIST.md)

---

## Documentation

| Document | Description |
|---|---|
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Step-by-step setup guide (Russian) |
| [docs/API.md](docs/API.md) | Full API reference |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture and design decisions |
| [docs/CONFIGURATION_MATRIX.md](docs/CONFIGURATION_MATRIX.md) | All configuration parameters and valid combinations |
| [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | Docker, Kubernetes, production deployment |
| [docs/SAFETY_PLUGINS.md](docs/SAFETY_PLUGINS.md) | Custom safety model integration |
| [BENCHMARK_GUIDE.md](BENCHMARK_GUIDE.md) | Running and interpreting benchmarks |
| [GPU_QUICKSTART.md](GPU_QUICKSTART.md) | GPU acceleration for embeddings and reranking |

---

## Citation

If you use AVI in your research, please cite:

```bibtex
@article{katalshov2026avi,
  title   = {Decoupling Intelligence from Governance: A Dynamic Bilateral
             Architecture for Real-Time Enterprise AI Compliance},
  author  = {Katalshov, Danila and Shvetsova, Olga and Lee, Sang-Kon and Koltun, Sviatlana},
  journal = {Electronics},
  volume  = {15},
  number  = {10},
  pages   = {2125},
  year    = {2026},
  doi     = {10.3390/electronics15102125},
  url     = {https://doi.org/10.3390/electronics15102125}
}
```

---

## License

MIT — see [LICENSE](LICENSE).
