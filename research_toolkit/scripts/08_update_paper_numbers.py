"""
Script to extract final experiment numbers and generate paper-ready statistics.
Run after 06_rigorous_evaluation.py completes.

Usage:
    cd research_toolkit
    python scripts/08_update_paper_numbers.py \
        --results data/results/rigorous_eval \
        --output  data/results/paper_numbers.json
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def mean_ci(values, level=0.95):
    arr = np.array(values, dtype=float)
    n = len(arr)
    if n < 2:
        m = float(np.mean(arr))
        return {"mean": m, "ci_low": m, "ci_high": m, "std": 0.0, "n": n}
    m = float(np.mean(arr))
    se = stats.sem(arr)
    h = se * stats.t.ppf((1 + level) / 2, df=n - 1)
    return {"mean": round(m, 4), "ci_low": round(m - h, 4), "ci_high": round(m + h, 4),
            "std": round(float(np.std(arr)), 4), "n": n}


def main(args):
    results_dir = Path(args.results)

    # Load all run CSVs
    run_files = sorted(results_dir.glob("run_*.csv"))
    print(f"Found {len(run_files)} run files")

    dfs = []
    for f in run_files:
        df = pd.read_csv(f)
        # Skip pilot data (5 queries) if full run exists
        if len(df) >= 100:
            dfs.append(df)
            print(f"  {f.name}: {len(df)} rows")
        else:
            print(f"  {f.name}: SKIPPING (only {len(df)} rows - pilot data)")

    if not dfs:
        # Fall back to all_runs.csv if available
        all_runs_file = results_dir / "all_runs.csv"
        if all_runs_file.exists():
            all_runs = pd.read_csv(all_runs_file)
            print(f"Using all_runs.csv: {len(all_runs)} rows")
        else:
            print("ERROR: No completed run files found. Experiment still running?")
            sys.exit(1)
    else:
        all_runs = pd.concat(dfs, ignore_index=True)
        print(f"\nTotal rows: {len(all_runs)}")

    n_runs = all_runs["run_id"].nunique()
    n_queries = all_runs["query_id"].nunique()
    print(f"N runs: {n_runs}, N queries: {n_queries}")

    # ── Per-run compliance rates ────────────────────────────────────────
    per_run_judge_compliance = all_runs.groupby("run_id")["judge_compliance"].apply(
        lambda x: (x >= 0.8).mean()
    ).tolist()
    per_run_auto_compliance = all_runs.groupby("run_id")["avi_compliant"].mean().tolist()
    per_run_trigger = all_runs.groupby("run_id")["avi_rule_triggered"].mean().tolist()

    # ── Latency ────────────────────────────────────────────────────────
    blocked = all_runs[all_runs["avi_rule_triggered"] == True]
    allowed = all_runs[all_runs["avi_rule_triggered"] == False]

    latency_blocked = {
        "mean": round(float(blocked["avi_latency_ms"].mean()), 1),
        "p50": round(float(blocked["avi_latency_ms"].quantile(0.5)), 1),
        "p95": round(float(blocked["avi_latency_ms"].quantile(0.95)), 1),
        "n": len(blocked),
    } if len(blocked) > 0 else {"mean": None, "p50": None, "p95": None, "n": 0}

    latency_allowed = {
        "mean": round(float(allowed["avi_latency_ms"].mean()), 1) if len(allowed) > 0 else None,
        "p50": round(float(allowed["avi_latency_ms"].quantile(0.5)), 1) if len(allowed) > 0 else None,
        "p95": round(float(allowed["avi_latency_ms"].quantile(0.95)), 1) if len(allowed) > 0 else None,
        "n": len(allowed),
    }

    # Baseline (run_0 only)
    run0 = all_runs[all_runs["run_id"] == 0]
    baseline_latency = {
        "mean": round(float(run0["base_latency_ms"].mean()), 1),
        "p50": round(float(run0["base_latency_ms"].quantile(0.5)), 1),
        "p95": round(float(run0["base_latency_ms"].quantile(0.95)), 1),
        "n": len(run0),
    }
    baseline_compliance = float(run0["base_compliant"].mean())

    # ── Precision / Recall / F1 ─────────────────────────────────────────
    # All queries have embargo policies → every query is "positive"
    # TP = triggered, FN = not triggered
    per_run_recall = per_run_trigger  # recall = TP/(TP+FN) = trigger_rate
    per_run_precision = [1.0 if r > 0 else 0.0 for r in per_run_trigger]  # no FP in this design
    per_run_f1 = [
        2 * p * r / (p + r) if (p + r) > 0 else 0.0
        for p, r in zip(per_run_precision, per_run_recall)
    ]

    # ── Statistical test ────────────────────────────────────────────────
    avi_comp = per_run_judge_compliance
    baseline_comp = [baseline_compliance] * n_runs  # same for all runs (baseline run once)

    try:
        _, wilcoxon_p = stats.wilcoxon(avi_comp, baseline_comp)
    except Exception:
        wilcoxon_p = float("nan")

    avi_arr = np.array(avi_comp)
    base_arr = np.array(baseline_comp)
    pooled_std = np.sqrt((np.std(avi_arr, ddof=1)**2 + np.std(base_arr, ddof=1)**2) / 2) or 1e-9
    cohen_d = float((np.mean(avi_arr) - np.mean(base_arr)) / pooled_std)

    # ── Error taxonomy ──────────────────────────────────────────────────
    taxonomy_file = results_dir / "error_taxonomy.csv"
    if taxonomy_file.exists():
        taxonomy = pd.read_csv(taxonomy_file).to_dict("records")
    else:
        # Estimate from judge_leak_type
        failures = all_runs[all_runs["judge_compliance"] < 0.8]
        taxonomy = failures["judge_leak_type"].value_counts().reset_index().rename(
            columns={"judge_leak_type": "category", "count": "count"}
        ).to_dict("records")

    # ── Sensitivity analysis ─────────────────────────────────────────────
    sens_file = results_dir / "sensitivity_analysis.csv"
    if sens_file.exists():
        sensitivity = pd.read_csv(sens_file).to_dict("records")
    else:
        sensitivity = []

    # ── Compile output ──────────────────────────────────────────────────
    output = {
        "experiment_info": {
            "n_runs": n_runs,
            "n_queries": n_queries,
            "total_observations": len(all_runs),
        },
        "compliance": {
            "judge_based": mean_ci(per_run_judge_compliance),
            "auto_based": mean_ci(per_run_auto_compliance),
        },
        "rule_trigger": mean_ci(per_run_trigger),
        "precision": mean_ci(per_run_precision),
        "recall": mean_ci(per_run_recall),
        "f1": mean_ci(per_run_f1),
        "latency": {
            "blocked": latency_blocked,
            "allowed": latency_allowed,
            "baseline": baseline_latency,
            "latency_reduction_pct": round(
                (baseline_latency["mean"] - (latency_blocked["mean"] or baseline_latency["mean"]))
                / baseline_latency["mean"] * 100, 1
            ) if baseline_latency["mean"] else None,
        },
        "baseline": {
            "compliance": round(baseline_compliance, 4),
            "latency_ms": baseline_latency,
        },
        "statistical_tests": {
            "wilcoxon_p": round(wilcoxon_p, 4) if not np.isnan(wilcoxon_p) else "insufficient_data",
            "cohen_d": round(cohen_d, 3),
        },
        "error_taxonomy": taxonomy,
        "sensitivity": sensitivity,
    }

    # Print summary
    print("\n" + "="*60)
    print("PAPER-READY NUMBERS SUMMARY")
    print("="*60)
    c = output["compliance"]["judge_based"]
    print(f"Compliance Rate (judge): {c['mean']:.3f} (95% CI: {c['ci_low']:.3f}–{c['ci_high']:.3f})")
    t = output["rule_trigger"]
    print(f"Rule Trigger Rate:       {t['mean']:.3f} (95% CI: {t['ci_low']:.3f}–{t['ci_high']:.3f})")
    r = output["recall"]
    print(f"Recall:                  {r['mean']:.3f} (95% CI: {r['ci_low']:.3f}–{r['ci_high']:.3f})")
    p2 = output["precision"]
    print(f"Precision:               {p2['mean']:.3f} (95% CI: {p2['ci_low']:.3f}–{p2['ci_high']:.3f})")
    lb = output["latency"]["blocked"]
    print(f"Latency blocked (mean):  {lb['mean']} ms (P95: {lb['p95']} ms, n={lb['n']})")
    la = output["latency"]["allowed"]
    print(f"Latency allowed (mean):  {la['mean']} ms (n={la['n']})")
    bl = output["latency"]["baseline"]
    print(f"Latency baseline (mean): {bl['mean']} ms")
    print(f"Latency reduction:       {output['latency']['latency_reduction_pct']}%")
    print(f"Baseline compliance:     {output['baseline']['compliance']:.3f}")
    print(f"Wilcoxon p-value:        {output['statistical_tests']['wilcoxon_p']}")
    print(f"Cohen's d:               {output['statistical_tests']['cohen_d']}")
    print("="*60)

    # Save
    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to: {output_path}")
    print("\nNext step: Use these numbers to update paper_revised.docx (БЛОК 4)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="data/results/rigorous_eval")
    parser.add_argument("--output", default="data/results/paper_numbers.json")
    args = parser.parse_args()
    main(args)
