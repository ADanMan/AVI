

# AVI — Interfaz de Validación de Acuerdos

[![DOI](https://img.shields.io/badge/DOI-10.3390%2Felectronics15102125-blue)](https://doi.org/10.3390/electronics15102125)
[![CI](https://github.com/ADanMan/AVI/actions/workflows/ci.yml/badge.svg)](https://github.com/ADanMan/AVI/actions/workflows/ci.yml)
[![Smoke Tests](https://github.com/ADanMan/AVI/actions/workflows/smoke-tests.yml/badge.svg)](https://github.com/ADanMan/AVI/actions/workflows/smoke-tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

Implementación oficial de la **Alineación Bilateral Dinámica (DBA)** del artículo:

> **Decoupling Intelligence from Governance: A Dynamic Bilateral Architecture for Real-Time Enterprise AI Compliance**  
> Danila Katalshov, Olga Shvetsova, Sang-Kon Lee, Sviatlana Koltun  
> *Electronics* 2026, 15(10), 2125 · [https://doi.org/10.3390/electronics15102125](https://doi.org/10.3390/electronics15102125)

AVI es un middleware de gobernanza modular que se sitúa entre su aplicación y cualquier LLM. Hace cumplir las políticas de cumplimiento tanto en la **entrada** (lo que envía el usuario) como en la **salida** (lo que devuelve el modelo) mediante recuperación semántica basada en vectores: no se requiere volver a entrenar el modelo.

---

## Resultados Clave

Validado contra [FinanceBench](https://huggingface.co/datasets/PatronusAI/financebench) (N=150 consultas, 3 ejecuciones repetidas):

| Métrica | Línea base (sin AVI) | AVI |
|---|---|---|
| Tasa de cumplimiento del evaluador LLM | 63.7% | **83.2%** (↑+19.5 pp, p=0.002) |
| Precisión / Recall / F1 del filtro vectorial | — | **1.000 / 1.000 / 1.000** |
| Tiempo hasta el cumplimiento (nueva regla) | ~horas (ajuste fino) | **< 5 segundos** (reindexación) |

Validación cruzada de dominios en 201 consultas provocativas en ruso: Recall=0.985, cumplimiento del LLM entre las consultas activadas=0.977.

---

## Cómo Funciona

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

Las políticas son filas CSV simples (`data/raw/filter_rules.csv`). Agregar una regla toma segundos y es efectiva inmediatamente: sin despliegue, sin volver a entrenar.

---

## Inicio Rápido

### Docker (recomendado)

```bash
git clone https://github.com/ADanMan/AVI.git
cd AVI
cp .env.example .env
# Set MAIN_LLM_API_KEY and MAIN_LLM_MODEL in .env
docker compose up --build
```

Servicios después del inicio:

| Servicio | URL |
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

Configuración mínima de `.env`:

```bash
MAIN_LLM_API_KEY=sk-or-v1-...       # required
MAIN_LLM_MODEL=openai/gpt-4o-mini   # or any OpenAI-compatible model
```

---

## Reproducción de los Resultados del Artículo

El directorio `research_toolkit/` contiene todo lo necesario para reproducir el experimento de FinanceBench del artículo.

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

Versiones interactivas de todos los pasos están disponibles como cuadernos de Jupyter en `research_toolkit/notebooks/`.

> El conjunto de datos provocativo en ruso (N=201) utilizado para la validación cruzada de dominios es propietario y no está disponible públicamente, como se indica en el artículo.

---

## Modos de Seguridad

AVI admite cuatro configuraciones de seguridad:

| Modo | Descripción | Sobrecarga de latencia |
|---|---|---|
| `disabled` | Solo filtro vectorial (el más rápido) | ~10–50 ms |
| `external` | Filtro vectorial + sanitización LLM externa | ~200–800 ms |
| `local` | Filtro vectorial + microservicio de seguridad local | ~50–200 ms |
| `hybrid` | local + respaldo externo | ~50–800 ms |

Se configura mediante `SAFETY_MODE` en `.env`. Todos los modos comparten el mismo filtro de entrada basado en vectores; el modo controla el paso de sanitización del LLM para las consultas marcadas.

Se admiten modelos de seguridad integrables — consulte [`docs/SAFETY_PLUGINS.md`](docs/SAFETY_PLUGINS.md) y [`examples/safety_plugins/`](examples/safety_plugins/).

---

## Adición de Reglas de Cumplimiento

Las reglas son filas CSV indexadas en la base de datos vectorial. No se requieren cambios de código ni reinicios.

```csv
id,text,category,risk_level,threshold
rule_0,"Do not provide specific investment advice or price predictions.",financial_compliance,5,0.42
rule_1,"Do not reveal internal API credentials or infrastructure details.",information_security,5,0.40
```

Indexar nuevas reglas:

```bash
make index-data
# or: python scripts/index_data.py
```

Tiempo hasta el cumplimiento: menos de 5 segundos para un conjunto de reglas típico.

---

## Lista de Verificación para Producción

Antes de desplegar en producción:

- [ ] Establecer `REQUIRE_API_KEY=true` y rotar la clave de administrador
- [ ] Cambiar la DB vectorial a Qdrant (`VECTOR_DB_PROVIDER=qdrant`)
- [ ] Habilitar Redis para almacenamiento en caché distribuido (`REDIS_URL=...`)
- [ ] Configurar límites de tasa (`RATE_LIMIT_PER_MINUTE`)
- [ ] Establecer `SAFETY_MODE` apropiado para sus requisitos de cumplimiento
- [ ] Revisar [`docs/PRODUCTION_CHECKLIST.md`](docs/PRODUCTION_CHECKLIST.md)

---

## Documentación

| Documento | Descripción |
|---|---|
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Guía de configuración paso a paso (ruso) |
| [docs/API.md](docs/API.md) | Referencia completa de la API |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arquitectura del sistema y decisiones de diseño |
| [docs/CONFIGURATION_MATRIX.md](docs/CONFIGURATION_MATRIX.md) | Todos los parámetros de configuración y combinaciones válidas |
| [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | Docker, Kubernetes, despliegue en producción |
| [docs/SAFETY_PLUGINS.md](docs/SAFETY_PLUGINS.md) | Integración de modelos de seguridad personalizados |
| [BENCHMARK_GUIDE.md](BENCHMARK_GUIDE.md) | Ejecución e interpretación de benchmarks |
| [GPU_QUICKSTART.md](GPU_QUICKSTART.md) | Aceleración por GPU para embeddings y reranking |

---

## Citación

Si utiliza AVI en su investigación, por favor cite:

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

## Licencia

MIT — consulte [LICENSE](LICENSE).
