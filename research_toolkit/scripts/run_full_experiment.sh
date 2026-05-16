#!/usr/bin/env bash
# =============================================================================
# AVI Full Experiment Runner
# =============================================================================
# Usage:
#   export OPENROUTER_API_KEY=sk-or-v1-xxx    (or OPENAI_API_KEY)
#   export AVI_API_KEY=avi_kzAw...             (from .env)
#   bash scripts/run_full_experiment.sh
#
# Requires AVI server running at $AVI_URL (default: http://localhost:8765)
# =============================================================================

set -euo pipefail

AVI_URL="${AVI_URL:-http://localhost:8765}"
AVI_KEY="${AVI_API_KEY:-avi_kzAw3BOEWzjI_Q7xpX3F-iOMlXYMx8RYEjGHrJmx4nQ}"
OR_KEY="${OPENROUTER_API_KEY:-${OPENAI_API_KEY:-}}"

echo "============================================================"
echo "  AVI Research Experiment Pipeline"
echo "============================================================"
echo "  AVI URL:      $AVI_URL"
echo "  AVI Key:      ${AVI_KEY:0:10}..."
echo "  LLM API Key:  ${OR_KEY:0:15}..."
echo ""

if [ -z "$OR_KEY" ]; then
  echo "ERROR: Set OPENROUTER_API_KEY or OPENAI_API_KEY"
  exit 1
fi

# Check AVI server
echo "[1/5] Checking AVI server..."
if ! curl -sf --max-time 10 "$AVI_URL/api/v1/health" > /dev/null 2>&1; then
  echo "  WARNING: AVI server not responding at $AVI_URL"
  echo "  Start it with: REQUIRE_API_KEY=false uvicorn main:app --port 8765"
fi
echo "  OK"

# Step 2: Transform dataset
echo "[2/5] Transforming FinanceBench dataset..."
OPENROUTER_API_KEY="$OR_KEY" \
OPENAI_API_KEY="$OR_KEY" \
PYTHONPATH=src \
python3 scripts/02_transform_dataset.py

echo ""
echo "[3/5] Indexing rules into AVI..."
OPENROUTER_API_KEY="$OR_KEY" \
OPENAI_API_KEY="$OR_KEY" \
PYTHONPATH=src \
python3 scripts/index_rules.py \
  --avi-url "$AVI_URL" \
  --avi-key "$AVI_KEY" \
  --rules data/processed/filter_rules.csv \
  --docs data/processed/vector_documents.csv \
  --links data/processed/links.csv || echo "  WARNING: index_rules.py not found, skipping"

echo ""
echo "[4/5] Running rigorous evaluation (N=5 seeds)..."
OPENROUTER_API_KEY="$OR_KEY" \
python3 scripts/06_rigorous_evaluation.py \
  --avi-url "$AVI_URL" \
  --avi-key "$AVI_KEY" \
  --openrouter-key "$OR_KEY" \
  --queries data/processed/test_queries.csv \
  --rules data/processed/filter_rules.csv \
  --output data/results/rigorous_eval \
  --n-seeds 5

echo ""
echo "[5/5] Generating paper figures and tables..."
python3 scripts/07_generate_paper_figures.py \
  --results data/results/rigorous_eval \
  --output data/results/paper_assets

echo ""
echo "============================================================"
echo "  DONE! Results in data/results/paper_assets/"
echo "============================================================"
