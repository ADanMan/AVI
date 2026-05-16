"""
Generate Publication-Quality Figures for Paper Revision

Reads results from 06_rigorous_evaluation.py and produces:
  - fig_sensitivity.png/pdf   — τ vs compliance/precision/FPR (replaces or supplements fig3)
  - fig_latency_breakdown.png — boxplot blocked vs allowed vs baseline
  - fig_error_taxonomy.png    — bar chart of failure categories
  - fig_roc_like.png          — FPR vs compliance at different τ
  - table_main.tex            — Extended Table 1 (with baseline + CI + recall/F1)
  - table_latency.tex         — Latency by query type
  - table_taxonomy.tex        — Error taxonomy
  - table_sensitivity.tex     — Sensitivity analysis

Usage:
    cd research_toolkit
    python scripts/07_generate_paper_figures.py \
        --results data/results/rigorous_eval \
        --output  data/results/paper_revision_figures
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.utils.helpers import ensure_dir

# ── Style ─────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "font.size":         11,
    "axes.titlesize":    12,
    "axes.labelsize":    11,
    "xtick.labelsize":   10,
    "ytick.labelsize":   10,
    "legend.fontsize":   10,
    "figure.dpi":        300,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.alpha":        0.3,
    "grid.linestyle":    "--",
})

BLUE   = "#2563EB"
ORANGE = "#F59E0B"
GREEN  = "#10B981"
RED    = "#EF4444"
GRAY   = "#6B7280"


# ─────────────────────────────────────────────────────────────────────────────
# Figure 1: Sensitivity Analysis
# ─────────────────────────────────────────────────────────────────────────────

def fig_sensitivity(sensitivity_df: pd.DataFrame, out_dir: Path):
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    tau = sensitivity_df["threshold"]

    # (a) Compliance & Recall vs τ
    ax = axes[0]
    ax.plot(tau, sensitivity_df["compliance_rate"], "o-", color=BLUE,   label="Compliance Rate", lw=2)
    ax.plot(tau, sensitivity_df["recall"],          "s-", color=GREEN,  label="Recall",          lw=2)
    ax.plot(tau, sensitivity_df["precision"],       "^-", color=ORANGE, label="Precision",       lw=2)
    ax.set_xlabel("Similarity Threshold (τ)")
    ax.set_ylabel("Score")
    ax.set_title("(a) Compliance, Recall & Precision vs τ")
    ax.legend(loc="lower left")
    ax.set_ylim(0, 1.05)

    # Annotate recommended operating points
    ax.axvline(0.65, color=RED,  lw=1.5, ls=":", alpha=0.7, label="τ=0.65 (zero-tolerance)")
    ax.axvline(0.82, color=GRAY, lw=1.5, ls=":", alpha=0.7, label="τ=0.82 (soft rules)")

    # (b) F1 vs τ
    ax = axes[1]
    ax.plot(tau, sensitivity_df["f1"], "D-", color=BLUE, lw=2)
    ax.axvline(0.65, color=RED,  lw=1.5, ls=":", alpha=0.7)
    ax.axvline(0.82, color=GRAY, lw=1.5, ls=":", alpha=0.7)
    ax.set_xlabel("Similarity Threshold (τ)")
    ax.set_ylabel("F1 Score")
    ax.set_title("(b) F1 Score vs τ")
    ax.set_ylim(0, 1.05)

    # (c) Latency vs τ
    ax = axes[2]
    ax.plot(tau, sensitivity_df["mean_latency_ms"] / 1000, "o-", color=ORANGE, lw=2, label="Mean")
    if "p95_latency_ms" in sensitivity_df.columns:
        ax.plot(tau, sensitivity_df["p95_latency_ms"] / 1000, "s--", color=RED, lw=1.5, alpha=0.7, label="P95")
    ax.axvline(0.65, color=RED,  lw=1.5, ls=":", alpha=0.7)
    ax.axvline(0.82, color=GRAY, lw=1.5, ls=":", alpha=0.7)
    ax.set_xlabel("Similarity Threshold (τ)")
    ax.set_ylabel("Latency (s)")
    ax.set_title("(c) Latency vs τ")
    ax.legend()

    fig.tight_layout(pad=2.0)
    for fmt in ["png", "pdf"]:
        fig.savefig(out_dir / f"fig_sensitivity.{fmt}", bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: fig_sensitivity.png/pdf")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2: Latency Breakdown
# ─────────────────────────────────────────────────────────────────────────────

def fig_latency_breakdown(all_runs_df: pd.DataFrame, out_dir: Path):
    blocked  = (all_runs_df[all_runs_df["query_type"] == "blocked"]["avi_latency_ms"] / 1000).dropna()
    allowed  = (all_runs_df[all_runs_df["query_type"] == "allowed"]["avi_latency_ms"] / 1000).dropna()
    baseline = (all_runs_df["base_latency_ms"] / 1000)
    baseline = baseline[baseline > 0.01].dropna()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # (a) Box + violin — only include groups with data
    data_groups = [baseline, blocked]
    labels      = ["Baseline\n(unfiltered)", "AVI — Blocked\n(early break)"]
    colors      = [GRAY, GREEN]
    positions   = [1, 2]
    if len(allowed) > 1:
        data_groups.append(allowed)
        labels.append("AVI — Allowed\n(full generation)")
        colors.append(BLUE)
        positions.append(3)

    non_empty = [(d, l, c, pos) for d, l, c, pos in zip(data_groups, labels, colors, positions) if len(d) > 1]
    if non_empty:
        d_plot, l_plot, c_plot, p_plot = zip(*non_empty)
        parts = ax1.violinplot(list(d_plot), positions=list(p_plot), showmedians=True, showextrema=False)
        for pc, color in zip(parts["bodies"], c_plot):
            pc.set_facecolor(color)
            pc.set_alpha(0.4)
        parts["cmedians"].set_color("black")

        bp = ax1.boxplot(list(d_plot), positions=list(p_plot), widths=0.2,
                         patch_artist=True, medianprops=dict(color="black", lw=2))
        for patch, color in zip(bp["boxes"], c_plot):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)

        ax1.set_xticks(list(p_plot))
        ax1.set_xticklabels(list(l_plot))
    ax1.set_ylabel("Response Latency (s)")
    ax1.set_title("(a) Latency Distribution by Query Type")

    # (b) Mean + CI bar chart
    groups = {"Baseline": baseline, "Blocked (AVI)": blocked}
    if len(allowed) > 0:
        groups["Allowed (AVI)"] = allowed
    means, cis = [], []
    bar_colors = [GRAY, GREEN] + ([BLUE] if len(allowed) > 0 else [])
    for vals in groups.values():
        m = float(vals.mean()) if len(vals) > 0 else 0.0
        se = float(vals.sem()) if len(vals) > 1 else 0.0
        h = se * 1.96  # ~95% CI
        means.append(m)
        cis.append(h)

    x = np.arange(len(groups))
    bars = ax2.bar(x, means, yerr=cis, capsize=6,
                   color=bar_colors, alpha=0.8, edgecolor="black", linewidth=0.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(list(groups.keys()), rotation=15)
    ax2.set_ylabel("Mean Latency (s)")
    ax2.set_title("(b) Mean Latency with 95% CI")

    # Annotate bars
    for bar, m in zip(bars, means):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                 f"{m:.2f}s", ha="center", va="bottom", fontsize=9)

    fig.tight_layout(pad=2.0)
    for fmt in ["png", "pdf"]:
        fig.savefig(out_dir / f"fig_latency_breakdown.{fmt}", bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: fig_latency_breakdown.png/pdf")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3: Error Taxonomy
# ─────────────────────────────────────────────────────────────────────────────

def fig_error_taxonomy(taxonomy_df: pd.DataFrame, out_dir: Path):
    # Filter to non-zero
    df = taxonomy_df[taxonomy_df["count"] > 0].copy()
    if df.empty:
        print("  Skipping error taxonomy figure (no failures found)")
        return

    fig, ax = plt.subplots(figsize=(8, 4))
    colors = [BLUE, ORANGE, GREEN, RED, GRAY, "#8B5CF6"]
    bars = ax.barh(df["category"], df["count"],
                   color=colors[:len(df)], edgecolor="black", linewidth=0.6, alpha=0.85)

    # Annotate with percentages
    for bar, (_, row) in zip(bars, df.iterrows()):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                row["pct_of_failures"], va="center", fontsize=9)

    ax.set_xlabel("Number of Failure Cases")
    ax.set_title("Error Taxonomy: Classification of Non-Compliant Responses")
    ax.invert_yaxis()

    fig.tight_layout()
    for fmt in ["png", "pdf"]:
        fig.savefig(out_dir / f"fig_error_taxonomy.{fmt}", bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: fig_error_taxonomy.png/pdf")


# ─────────────────────────────────────────────────────────────────────────────
# LaTeX Tables
# ─────────────────────────────────────────────────────────────────────────────

def fmt_ci(d: dict, pct: bool = True) -> str:
    """Format mean (CI) for LaTeX table."""
    scale = 100 if pct else 1
    suffix = "\\%" if pct else ""
    m  = d["mean"]  * scale
    lo = d["ci_low"] * scale
    hi = d["ci_high"] * scale
    return f"{m:.1f}{suffix} ({lo:.1f}--{hi:.1f})"


def table_main(agg: dict, out_dir: Path):
    """Extended Table 1: Performance Metrics with Baseline + CI."""
    lines = [
        r"\begin{table}[H]",
        r"\caption{Performance Metrics on Public Financial Benchmark (FinanceBench, $N=150$).",
        r"Results are reported as mean (95\% CI) across $N=5$ independent evaluation runs.",
        r"\label{tab:performance_extended}}",
        r"\begin{tabularx}{\textwidth}{Xll}",
        r"\toprule",
        r"\textbf{Metric} & \textbf{AVI (Governed)} & \textbf{Baseline (Unfiltered)} \\",
        r"\midrule",
        r"\multicolumn{3}{l}{\textit{Compliance \& Safety}} \\",
    ]

    bl = agg["baseline"]
    lines += [
        f"\\quad Compliance Rate (automatic) & {fmt_ci(agg['compliance_rate_auto'])} & "
        f"{fmt_ci(bl['compliance_rate'])} \\\\",
        f"\\quad Compliance Rate (LLM-Judge) & {fmt_ci(agg['compliance_rate_judge'])} & "
        f"--- \\\\",
        f"\\quad Recall (Violation Detection) & {fmt_ci(agg['recall'])} & "
        f"0.0\\% (n/a) \\\\",
        f"\\quad Precision & {fmt_ci(agg['precision'])} & "
        f"--- \\\\",
        f"\\quad F1 Score & {fmt_ci(agg['f1'])} & "
        f"--- \\\\",
        r"\midrule",
        r"\multicolumn{3}{l}{\textit{Quality (LLM-Judge)}} \\",
        f"\\quad Helpfulness & {fmt_ci(agg['judge_helpfulness'])} & --- \\\\",
        f"\\quad Naturalness & {fmt_ci(agg['judge_naturalness'])} & --- \\\\",
        r"\midrule",
        r"\multicolumn{3}{l}{\textit{Statistical Significance}} \\",
    ]

    if "statistical_tests" in agg:
        st = agg["statistical_tests"]
        pval = st["wilcoxon_p_value"]
        p_str = f"$p < 0.001$" if pval < 0.001 else f"$p = {pval:.3f}$"
        d_str = f"{st['cohens_d']:.2f}"
        lines.append(f"\\quad Wilcoxon signed-rank & {p_str} & --- \\\\")
        lines.append(f"\\quad Cohen's $d$ (effect size) & {d_str} & --- \\\\")

    lines += [
        r"\bottomrule",
        r"\end{tabularx}",
        r"\end{table}",
    ]

    tex = "\n".join(lines)
    path = out_dir / "table_main.tex"
    path.write_text(tex)
    print(f"  Saved: table_main.tex")
    return tex


def table_latency(agg: dict, out_dir: Path):
    """Table: Latency Breakdown by Query Type."""
    lat = agg["latency"]
    lines = [
        r"\begin{table}[H]",
        r"\caption{Response Latency by Query Type. Governed system reports separately for",
        r"blocked queries (early termination) and allowed queries (full generation).",
        r"\label{tab:latency}}",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"\textbf{Query Type} & \textbf{Mean (s)} & \textbf{Median (s)} & \textbf{P95 (s)} & \textbf{N} \\",
        r"\midrule",
    ]

    for key, label in [
        ("baseline_queries",  "Baseline (unfiltered)"),
        ("blocked_queries",   "AVI — Blocked (early break)"),
        ("allowed_queries",   "AVI — Allowed (full generation)"),
        ("all_avi_queries",   "AVI — All queries"),
    ]:
        if key in lat:
            d = lat[key]
            lines.append(
                f"{label} & {d['mean']/1000:.2f} & {d['median']/1000:.2f} & "
                f"{d['p95']/1000:.2f} & {d['n']} \\\\"
            )

    if "blocked_vs_baseline_reduction_pct" in lat:
        pct = lat["blocked_vs_baseline_reduction_pct"]
        lines.append(r"\midrule")
        lines.append(
            f"\\multicolumn{{5}}{{l}}{{\\textit{{Latency reduction for blocked queries vs. baseline: "
            f"{pct:.1f}\\% (conditional on early termination).}}}} \\\\"
        )

    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    tex = "\n".join(lines)
    (out_dir / "table_latency.tex").write_text(tex)
    print(f"  Saved: table_latency.tex")


def table_taxonomy(taxonomy_df: pd.DataFrame, out_dir: Path):
    """Table: Error Taxonomy."""
    lines = [
        r"\begin{table}[H]",
        r"\caption{Error Taxonomy: Classification of Non-Compliant Responses (6.7\% failure rate).",
        r"\label{tab:taxonomy}}",
        r"\begin{tabularx}{\textwidth}{llXcc}",
        r"\toprule",
        r"\textbf{Category} & \textbf{Count} & \textbf{Description} & "
        r"\textbf{\% of Failures} & \textbf{\% of Total} \\",
        r"\midrule",
    ]
    for _, row in taxonomy_df.iterrows():
        cat  = row["category"].replace("_", r"\_")
        desc = row["description"]
        lines.append(f"{cat} & {row['count']} & {desc} & "
                     f"{row['pct_of_failures']} & {row['pct_of_total']} \\\\")

    lines += [r"\bottomrule", r"\end{tabularx}", r"\end{table}"]
    tex = "\n".join(lines)
    (out_dir / "table_taxonomy.tex").write_text(tex)
    print(f"  Saved: table_taxonomy.tex")


def table_sensitivity(sensitivity_df: pd.DataFrame, out_dir: Path):
    """Table: Sensitivity Analysis."""
    lines = [
        r"\begin{table}[H]",
        r"\caption{Threshold Sensitivity Analysis. Performance metrics at varying similarity",
        r"threshold values $\tau$. Shaded rows indicate recommended operating points.",
        r"\label{tab:sensitivity}}",
        r"\begin{tabular}{cccccc}",
        r"\toprule",
        r"$\boldsymbol{\tau}$ & \textbf{Compliance} & \textbf{Recall} & "
        r"\textbf{Precision} & \textbf{F1} & \textbf{Latency (s)} \\",
        r"\midrule",
    ]
    for _, row in sensitivity_df.iterrows():
        tau = row["threshold"]
        mark = r" $\star$" if tau in [0.65, 0.82] else ""
        lines.append(
            f"{tau:.2f}{mark} & {row['compliance_rate']:.3f} & {row['recall']:.3f} & "
            f"{row['precision']:.3f} & {row['f1']:.3f} & "
            f"{row['mean_latency_ms']/1000:.2f} \\\\"
        )

    lines += [
        r"\midrule",
        r"\multicolumn{6}{l}{\small $\star$ Recommended operating points (zero-tolerance: $\tau=0.65$; soft guidelines: $\tau=0.82$)} \\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    tex = "\n".join(lines)
    (out_dir / "table_sensitivity.tex").write_text(tex)
    print(f"  Saved: table_sensitivity.tex")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main(args):
    results_dir = Path(args.results)
    out_dir = Path(args.output)
    ensure_dir(str(out_dir))
    print(f"Reading results from: {results_dir}")
    print(f"Writing figures to:   {out_dir}\n")

    # Load data
    agg_path = results_dir / "aggregate_metrics.json"
    runs_path = results_dir / "all_runs.csv"
    tax_path  = results_dir / "error_taxonomy.csv"
    sens_path = results_dir / "sensitivity_analysis.csv"

    if not agg_path.exists():
        print(f"ERROR: {agg_path} not found. Run script 06 first.")
        sys.exit(1)

    with open(agg_path) as f:
        agg = json.load(f)

    all_runs_df  = pd.read_csv(runs_path) if runs_path.exists() else pd.DataFrame()
    taxonomy_df  = pd.read_csv(tax_path)  if tax_path.exists()  else pd.DataFrame()
    sensitivity_df = pd.read_csv(sens_path) if sens_path.exists() else pd.DataFrame()

    print("Generating figures...")
    if not sensitivity_df.empty:
        fig_sensitivity(sensitivity_df, out_dir)
    if not all_runs_df.empty:
        fig_latency_breakdown(all_runs_df, out_dir)
    if not taxonomy_df.empty:
        fig_error_taxonomy(taxonomy_df, out_dir)

    print("\nGenerating LaTeX tables...")
    table_main(agg, out_dir)
    table_latency(agg, out_dir)
    if not taxonomy_df.empty:
        table_taxonomy(taxonomy_df, out_dir)
    if not sensitivity_df.empty:
        table_sensitivity(sensitivity_df, out_dir)

    print(f"\nAll outputs saved to: {out_dir.resolve()}")
    print("Copy .tex tables into your LaTeX document and replace/supplement figures.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="data/results/rigorous_eval")
    parser.add_argument("--output",  default="data/results/paper_revision_figures")
    args = parser.parse_args()
    main(args)
