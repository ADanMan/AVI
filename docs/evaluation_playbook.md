# Evaluation Playbook

This playbook centralises the datasets, notebooks, scripts, metrics, and run configurations used to evaluate AVI's safety and retrieval capabilities. Use it as the single source of truth when preparing experiments or onboarding new benchmarks.

## Dataset ↔ Notebook/Script Map

| Scenario | Dataset File | Description | Primary Notebook | Automation Script |
| --- | --- | --- | --- | --- |
| Toxicity Detection | `toxigen.csv` | Classify adversarial prompts from the ToxiGen benchmark. | [`notebooks/toxicity_detection_template.ipynb`](../notebooks/toxicity_detection_template.ipynb) | [`python -m avi.cli run-benchmarks`](../scripts/benchmark_test.py) |
| Prompt Injection Detection | `prompt_injections.csv` | Detect malicious prompt-injection attempts and record guardrail responses. | [`notebooks/prompt_injection_template.ipynb`](../notebooks/prompt_injection_template.ipynb) | [`python -m avi.cli run-benchmarks`](../scripts/benchmark_test.py) |
| Jailbreak Defense | `advbench_jailbreak.csv` | Evaluate jailbreak attempts (e.g., AdvBench/Anthropic red teaming) and sanitisation quality. | [`notebooks/prompt_injection_template.ipynb`](../notebooks/prompt_injection_template.ipynb) | [`python -m avi.cli run-benchmarks`](../scripts/benchmark_test.py) |
| PII Masking | `pii_masking_200k.csv` | Verify that personally identifiable information is redacted or masked. | [`notebooks/pii_masking_template.ipynb`](../notebooks/pii_masking_template.ipynb) | [`python -m avi.cli run-benchmarks`](../scripts/benchmark_test.py) |
| Factual Consistency | `poly_fever.csv` | Check factual grounding against PolyFever knowledge base. | [`notebooks/factuality_template.ipynb`](../notebooks/factuality_template.ipynb) | [`python -m avi.cli run-benchmarks`](../scripts/benchmark_test.py) |
| Bias & Harm Analysis | `shades_nationality.csv` | Measure disparate treatment in SHADES nationality splits. | [`notebooks/bias_assessment_template.ipynb`](../notebooks/bias_assessment_template.ipynb) | [`python -m avi.cli run-benchmarks`](../scripts/benchmark_test.py) |

All benchmark metadata is centralised in [`config/benchmark_config.json`](../config/benchmark_config.json). The `python -m avi.cli setup-data` helper downloads the public datasets listed above and places them under `data/benchmarks/`.

## Scenario Metrics & Calculation Checklists

For every run, capture the metrics below. The "Checklist" column lists the calculations that must be validated before certifying the run.

| Scenario | Core Metrics | Checklist |
| --- | --- | --- |
| Toxicity Detection | TP, FP, FN, TN, Precision, Recall, F1, latency distribution, per-request cost | - [ ] Confusion matrix totals equal processed rows<br>- [ ] Average latency matches Prometheus histogram export<br>- [ ] Cost per request derived from `api_response_raw.billing` or `usage` payload |
| Prompt Injection Detection | TP, FP, FN, TN, Precision, Recall, F1, latency, sanitisation delta tokens | - [ ] Injection labels aligned with `label_hints`<br>- [ ] Review modified text for every TP sample<br>- [ ] Compute average sanitisation latency |
| Jailbreak Defense | TP/FP/FN/TN, Recall@k, nDCG@k, latency, cost | - [ ] Map jailbreak labels from `is_jailbreak`/`label` columns<br>- [ ] Compute retrieval metrics from `relevance_scores`/`rerank_scores`<br>- [ ] Confirm latency buckets recorded in tracker |
| PII Masking | TP/FP/FN/TN, Recall@k for PII spans, latency, cost | - [ ] Validate redaction quality by sampling FP/FN records<br>- [ ] Ensure Recall@k uses ground-truth mask annotations<br>- [ ] Capture average token cost |
| Factual Consistency | nDCG@k, Recall@k, hallucination rate (FN), latency, cost | - [ ] Map PolyFever labels to boolean supports<br>- [ ] Compute ranking metrics using retrieved context<br>- [ ] Record hallucination rate (false positives) |
| Bias & Harm Analysis | Grouped TP/FP/FN/TN, per-group Recall@k, disparate impact score, latency | - [ ] Compute per-group confusion matrix grouped by `target`<br>- [ ] Calculate disparate impact (minority recall / majority recall)<br>- [ ] Store summary in tracker tags |

Use the checklists as acceptance criteria before publishing reports. Any unchecked item requires remediation or annotation in the final summary.

## Where to Hook in Metrics

* Aggregated confusion-matrix and latency metrics are generated automatically by [`python -m avi.cli run-benchmarks`](../scripts/benchmark_test.py) and saved alongside raw results as `<dataset>_...csv` and `<dataset>_...metrics.csv`.
* Additional ranking metrics (nDCG, Recall@k) are derived from the `relevance_scores` or `rerank_scores` columns in the raw outputs. Ensure your datasets include the necessary annotations (e.g. `is_relevant`, `label`, `relevance`).
* Cost metrics are read from the `api_response_raw` column. The script expects `usage` or `billing` blocks compatible with OpenAI, Anthropic, or OpenRouter schemas.

## Automation Overview

1. Configure your preferred model pairings using the presets in [`config/run_presets/`](../config/run_presets/).
2. Launch batch evaluations via `python -m avi.cli run-benchmarks` (optionally setting `BENCHMARK_TRACKER`, `MLFLOW_TRACKING_URI`, or `WANDB_PROJECT`).
3. Generate Markdown or LaTeX reports from the tracker outputs with [`scripts/generate_benchmark_report.py`](../scripts/generate_benchmark_report.py).
4. Attach the report and completed checklist to the experiment ticket.

Maintaining this playbook keeps dataset ownership, metric expectations, and automation tooling aligned across teams.
