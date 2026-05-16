# Notebook & Benchmark Guide

This guide walks through preparing benchmark datasets, configuring shared settings, and executing the interactive notebooks.

## 1. Prepare datasets

1. Review `config/benchmark_config.json` to see the list of expected CSV files.
2. Download each dataset and copy it into `data/benchmarks/`.
3. Keep the filenames identical to the `file` field declared in the configuration (for example `toxigen.csv`).

> Tip: `python -m avi.cli setup-data` downloads several public datasets automatically. Place any proprietary benchmarks in the same folder.

## 2. Configure shared settings

The benchmarking command (`python -m avi.cli run-benchmarks`) and all notebook templates read values from `config/benchmark_config.json`.

- `paths.benchmarks` – location of the CSV files.
- `paths.results` – output folder for generated CSVs (`artifacts/results/` by default).
- `api.url` – URL for the AVI API endpoint used during evaluation.
- `models` – ordered list of LLM identifiers to benchmark.
- `parameters` – parameter grid expanded when running scripted benchmarks.
- `benchmarks` – metadata for each dataset (display name, text column, label hints, description).

Update these fields to match your environment before starting any experiments.

## 3. Launch the API and tooling

1. Install dependencies:
   ```bash
   pip install -r requirements.research.txt jupyter
   ```
2. Start the API locally:
   ```bash
   uvicorn main:app --reload
   ```
   Ensure the port matches the value configured in the JSON file.
3. (Optional) Start supporting services using `docker compose up` if you rely on the full stack.

## 4. Run notebooks

1. From the repository root launch Jupyter:
   ```bash
   jupyter lab
   ```
2. Open one of the templates inside `notebooks/` (for example `toxicity_detection_template.ipynb`).
3. Follow the cells sequentially:
   - Load configuration and inspect dataset metadata.
   - Preview the CSV with `pandas`.
   - Execute the asynchronous helper with `await run_experiment(...)` on a subset of rows.
   - Explore returned payloads and latency plots.
   - Save results to `artifacts/results/`.

## 5. Run scripted benchmarks

To process entire datasets without manual intervention use `python -m avi.cli run-benchmarks`:

```bash
python -m avi.cli run-benchmarks
```

The script reads the same configuration file and writes results and aggregated metrics into `artifacts/results/`.

## 6. Manage artifacts

- Intermediate notebook exports and benchmark outputs live in `artifacts/results/`.
- Add additional subdirectories under `artifacts/` (for charts, reports, etc.) as needed.
- Clean up outdated runs manually or archive them for reproducibility.

With the configuration-driven workflow both the notebooks and scripts stay aligned, reducing duplicate settings and making it straightforward to repeat experiments.
