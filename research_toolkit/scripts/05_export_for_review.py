#!/usr/bin/env python3
"""
Export cases for human verification

Identifies edge cases and exports for manual review

Usage:
    python scripts/05_export_for_review.py [results_csv_path]
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from experiment.human_review import HumanReview


def main():
    print("=" * 60)
    print("📋 Export for Human Verification")
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
        output_path = latest_exp / "human_review.csv"
    else:
        results_path = Path(sys.argv[1])
        output_path = results_path.parent / "human_review.csv"

    if not results_path.exists():
        print(f"❌ Error: {results_path} not found!")
        return 1

    print(f"📂 Loading results from {results_path}...")
    results_df = pd.read_csv(results_path)
    print(f"✅ Loaded {len(results_df)} results")
    print()

    # Initialize human review
    review = HumanReview(results_df)

    # Identify cases
    print("🔍 Identifying cases for review...")
    cases = review.identify_review_cases(
        flags=[
            'low_confidence_judge',
            'metric_disagreement',
            'random_sample',
        ]
    )
    print(f"✅ Identified {len(cases)} cases ({len(cases)/len(results_df):.1%} of total)")
    print()

    # Breakdown
    print("📊 Breakdown:")

    low_conf = (results_df['llm_compliance_score'] == 0.5).sum()
    print(f"   Low confidence: {low_conf}")

    auto_leak = results_df['contains_restricted_answer'] == True
    judge_ok = results_df['llm_compliance_score'] >= 0.5
    disagreement = (auto_leak & judge_ok).sum()
    print(f"   Disagreement: {disagreement}")

    random_sample = int(len(results_df) * 0.1)
    print(f"   Random sample: {random_sample}")
    print()

    # Export
    print(f"💾 Exporting to {output_path}...")
    review.export_for_review(str(output_path), cases=cases)

    print()
    print("=" * 60)
    print("✨ Export complete!")
    print("=" * 60)
    print()

    print("📝 Next steps:")
    print("  1. Open the CSV in Excel or Google Sheets")
    print("  2. Fill in these columns:")
    print("     - human_compliant: True/False")
    print("     - human_helpful: True/False")
    print("     - human_notes: Your comments")
    print("  3. Save the file")
    print("  4. Calculate inter-rater reliability:")
    print(f"     >>> verified = pd.read_csv('{output_path}')")
    print("     >>> review.calculate_final_metrics(verified)")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
