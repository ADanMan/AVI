# Experiment Tracking for Benchmarks

This guide explains how to capture benchmark runs launched via
`python -m avi.cli run-benchmarks` in
MLflow or Weights & Biases (W&B). The script now logs the evaluated model,
parameter grid, guardrail filter modes, per-mode metrics (TP/FP/FN/TN, precision,
recall, F1, latency), and persists the generated CSV artifacts through the
selected tracking backend.

## Prerequisites

1. Install the dependencies from `requirements.main.txt` so that `mlflow` and
   `wandb` are available in your Python environment.
2. Ensure the benchmark configuration in `config/benchmark_config.json` points
   to the datasets and API endpoint you want to evaluate.

## Selecting a Tracking Backend

Set `BENCHMARK_TRACKER` to `mlflow` or `wandb` before running the benchmark
script. If the variable is not provided the run finishes locally without remote
logging.

```bash
export BENCHMARK_TRACKER=mlflow  # or: wandb
```

### MLflow

The repository ships with an MLflow service that is started automatically when
running `docker compose up`. The API container now exposes the relevant
configuration so that ad-hoc benchmark runs launched via Docker inherit the
tracking settings.

```bash
# Start the full stack (includes MLflow at http://localhost:5000)
docker compose up -d mlflow api

# Optional: override defaults
export MLFLOW_TRACKING_URI=http://localhost:5000
export MLFLOW_EXPERIMENT_NAME="AVI Benchmarks"
```

When `BENCHMARK_TRACKER=mlflow` the script

* logs the dataset name, model id, and LLM parameters as MLflow parameters;
* records unique input/output filter modes that appeared during the run;
* publishes confusion-matrix style metrics (`tp`, `fp`, `fn`, `tn`, precision,
  recall, F1, average latency) per stage/mode; and
* uploads the response CSV and aggregated metrics CSV as run artifacts.

You can explore the results in the MLflow UI at `http://localhost:5000`. Use the
experiment selector to switch between benchmark runs or compare models.

### Weights & Biases

To use W&B you must authenticate and supply the desired project metadata:

```bash
export BENCHMARK_TRACKER=wandb
export WANDB_API_KEY=<your-api-key>
export WANDB_PROJECT=avi-benchmarks   # optional override
export WANDB_ENTITY=<your-wandb-entity>  # optional team/org slug
```

The script initialises a fresh W&B run for every dataset/model/parameter
combination. Parameters and filter modes are saved in the run configuration,
metrics are reported via `wandb.log`, and both CSV artifacts are uploaded as
benchmark artifacts.

Open <https://wandb.ai/> after authenticating with your API key to inspect
history charts, compare runs, or download the stored files.

## Running the Benchmark

Execute the command once the backend is configured:

```bash
python -m avi.cli run-benchmarks
```

Progress is streamed to the terminal. Results are still written to the local
`artifacts/results` directory to keep the resume capability, but they are now
mirrored to the configured experiment tracker once each dataset/model/parameter
combination finishes. If the script detects that a combination is already fully
processed it will reuse the cached CSVs and only publish the aggregated metrics
and artifacts.

## Troubleshooting

* **Missing package warning** – If `BENCHMARK_TRACKER` is set but the
  corresponding library is not installed, the script logs a warning and continues
  without remote tracking.
* **Authentication issues** – Ensure your `WANDB_API_KEY` is exported before the
  script starts, or that the MLflow server is reachable at the configured
  `MLFLOW_TRACKING_URI`.
* **Artifact visibility** – Both backends receive two artifacts per run: the
  raw response CSV (`responses-<file-stem>`) and the aggregated metrics CSV
  (`metrics-<file-stem>`). Use these to download the results or share them with
  collaborators.
