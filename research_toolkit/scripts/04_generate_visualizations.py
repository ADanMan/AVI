#!/usr/bin/env python3
"""
Generate all visualizations for paper

Creates figures and tables from experiment results

Usage:
    python scripts/04_generate_visualizations.py [results_csv_path]
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from visualization.results_visualizer import ResultsVisualizer
from visualization.paper_tables import PaperTables


def main():
    print("=" * 60)
    print("🎨 Generate Visualizations for Paper")
    print("=" * 60)
    print()

    # Find latest results
    results_dir = Path("data/results")

    if len(sys.argv) > 1:
        results_path = Path(sys.argv[1])
    else:
        # Find latest experiment
        experiment_dirs = sorted(results_dir.glob("experiment_*"))
        if not experiment_dirs:
            print(f"❌ Error: No experiment results found in {results_dir}")
            print(f"   Run: python scripts/03_run_experiment.py")
            return 1

        latest_exp = experiment_dirs[-1]
        results_path = latest_exp / "raw_results.csv"

    if not results_path.exists():
        print(f"❌ Error: {results_path} not found!")
        return 1

    print(f"📂 Loading results from {results_path}...")
    results_df = pd.read_csv(results_path)
    print(f"✅ Loaded {len(results_df)} results")
    print()

    # Generate figures
    print("🎨 Generating figures...")
    print()

    viz = ResultsVisualizer(results_df, dpi=300)
    viz.generate_all_figures(output_dir="paper/figures")

    print()

    # Generate tables
    print("📊 Generating tables...")
    print()

    tables = PaperTables(results_df)
    tables.generate_all_tables(output_dir="paper/tables")

    print()
    print("=" * 60)
    print("✨ All visualizations generated!")
    print("=" * 60)
    print()

    print("📁 Outputs:")
    print("   Figures: paper/figures/")
    print("   Tables:  paper/tables/")
    print()

    print("Next steps:")
    print("  1. Review figures in paper/figures/")
    print("  2. Review tables in paper/tables/")
    print("  3. Include in LaTeX manuscript")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
