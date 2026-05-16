# Operations Runbook: Environment Validation & Benchmarks

This runbook captures the steps operators follow when preparing a deployment or
running the final benchmark suite. It complements the secret-management guide in
`docs/operations.md` and focuses on runtime configuration, health checks, and
post-run analysis.

## 1. Configure Runtime Environment Variables

Export the core settings before starting the API (via `systemd`, container
variables, or an `.env` file mounted into the service). The following exports
cover the LLM endpoints, moderation guardrails, and vector store connectivity:

```bash
export APP_ENV=production
export MAIN_LLM_API_KEY="sk-..."              # Required for external LLM calls
export MAIN_LLM_MODEL="gpt-4o-mini"          # Matches config/benchmark_config.json
export MAIN_LLM_API_BASE="https://openrouter.ai/api/v1"

export SAFETY_MODE="llm"                      # disabled | llm | local | remote | external | hybrid
export SAFETY_LLM_API_KEY="safety-..."
export SAFETY_LLM_MODEL="gpt-4o-mini-guard"
export SAFETY_LLM_API_BASE="https://safety.vendor/api"

# Vector store provider (Chroma local path or Qdrant endpoint)
export VECTOR_DB_PROVIDER="qdrant"            # chroma | qdrant
export VECTOR_DB_PATH="/var/avi/indexes/chroma"   # used when provider=chroma
export QDRANT_HOST="qdrant.svc.cluster.local"
export QDRANT_PORT=6333
export QDRANT_API_KEY="qdrant-..."           # omit when running unauthenticated

# Optional observability for benchmark runs
export BENCHMARK_TRACKER="mlflow"            # "mlflow" or "wandb" to enable trackers
export MLFLOW_TRACKING_URI="http://mlflow:5000"
export WANDB_PROJECT="avi-benchmarks"
export WANDB_ENTITY="avi"
```

Additional environment variables (cache, Vault, tracing) are described in
`config/.env.example`; reuse them as needed for your deployment.

## 2. Verify Service Health

Run the API and execute the following checks from an operator workstation or the
deployment host.

### 2.1 Health Summary (`/health`)

```bash
curl -fsS "${AVI_API_BASE:-http://localhost:8000}/health" | jq
```

A healthy system returns `status: "healthy"` with component flags for
`external_llm`, `safety_llm`, and `vector_db`. Any `degraded` response warrants
investigation before continuing.

### 2.2 External LLM Connectivity (`/llm/external/status`)

```bash
curl -fsS "${AVI_API_BASE:-http://localhost:8000}/llm/external/status" | jq
```

Confirm the payload reports `status: "connected"` and the expected
`model` (matches `MAIN_LLM_MODEL`). If the endpoint returns `disconnected`,
re-check the API key and base URL environment variables.

### 2.3 System Statistics (`/stats`)

```bash
curl -fsS "${AVI_API_BASE:-http://localhost:8000}/stats" | jq
```

Validate that `vector_db.total_documents` and `vector_db.total_rules` contain
non-zero counts after indexing, and that cache metrics reflect recent activity.

### 2.4 Confirm Vector Store Connectivity

1. **Indexing sanity check** – run `python -m avi.cli index-data` (or trigger the
   `/reindex` endpoint) and ensure the command finishes without errors.
2. **Provider-specific probe**
   - *Chroma*: verify the directory in `VECTOR_DB_PATH` contains the updated
     collection files and that the service user has read/write permissions.
   - *Qdrant*: confirm TCP reachability (`nc -z $QDRANT_HOST $QDRANT_PORT`) and
     optional authentication by sending a simple `/collections` request with the
     configured API key.
3. Re-run `/stats` to ensure the document and rule counts increment after
   indexing completes.

## 3. Benchmark Execution & Reporting

Use the CLI to launch automated evaluations once the environment passes the
health checks.

### 3.1 Selective Benchmark Runs

Filter by model and/or dataset with repeatable options:

```bash
python -m avi.cli run-benchmarks --model gpt-4o-mini --benchmark toxicity.csv
python -m avi.cli run-benchmarks --model claude-3-haiku --model llama-3-70b
```

Model identifiers must match `config/benchmark_config.json`, and benchmark names
map to the CSV filenames in `data/benchmarks/`.

### 3.2 Full Benchmark Sweep

```bash
python -m avi.cli run-benchmarks
```

The command iterates over every configured model/benchmark combination and
stores raw results plus metrics CSVs under `artifacts/results/`.

### 3.3 Post-processing Report

Generate the consolidated analysis after any run (selective or full):

```bash
python scripts/generate_benchmark_report.py
```

The script aggregates outputs from `artifacts/results/` and emits a Markdown
summary ready for distribution to stakeholders.

---

Following this checklist ensures the deployment is correctly configured, core
services remain reachable, and benchmarking artifacts are reproducible across
operators.
