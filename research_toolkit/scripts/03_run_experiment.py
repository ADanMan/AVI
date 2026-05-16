#!/usr/bin/env python3
"""
Run complete experiment on AVI system

Runs baseline + AVI, collects metrics, evaluates with LLM Judge

Usage:
    python scripts/03_run_experiment.py
"""

import sys
import asyncio
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from experiment.runner import ExperimentRunner
from utils.helpers import ExperimentConfig


async def main():
    print("=" * 60)
    print("🚀 Run AVI Experiment")
    print("=" * 60)
    print()

    # Load config
    config = ExperimentConfig("config/experiment_config.yaml")

    # Load test queries
    test_queries_path = Path("data/processed/test_queries.csv")

    if not test_queries_path.exists():
        print(f"❌ Error: {test_queries_path} not found!")
        print(f"   Run: python scripts/02_transform_dataset.py")
        return 1

    print(f"📂 Loading test queries from {test_queries_path}...")
    test_queries = pd.read_csv(test_queries_path)
    print(f"✅ Loaded {len(test_queries)} test queries")
    print()

    # Initialize runner
    print("🏗️  Initializing ExperimentRunner...")
    runner = ExperimentRunner(
        avi_api_url=config.get('avi.api_url'),
        avi_api_key=config.get('avi.api_key', 'your-avi-key'),
        test_model=config.get('llm.test_model'),
        test_api_base=config.get('llm.test_api_base'),
        test_api_key=config.get('llm.test_api_key'),
    )
    print("✅ Runner ready")
    print()

    # Run experiment
    print("🎯 Starting experiment...")
    print("   This will take several minutes...")
    print()

    results_df = await runner.run_full_experiment(
        test_queries_df=test_queries,
        run_baseline=True,
        show_progress=True,
    )

    print()
    print("=" * 60)
    print("✨ Experiment Complete!")
    print("=" * 60)
    print()

    # Summary
    print(f"📊 Results Summary:")
    print(f"   Total queries: {len(results_df)}")
    print(f"   Compliance rate: {(results_df['llm_compliance_score'] >= 0.5).mean():.1%}")
    print(f"   Leak rate: {results_df['contains_restricted_answer'].mean():.1%}")
    print(f"   Mean helpfulness: {results_df['llm_helpfulness_score'].mean():.2f}/1.0")
    print(f"   Mean latency overhead: {results_df['latency_overhead_ms'].mean():.1f}ms")
    print()

    print("Next steps:")
    print("  1. Review results: Open data/results/experiment_*/raw_results.csv")
    print("  2. Generate visualizations: python scripts/04_generate_visualizations.py")
    print("  3. Human verification: python scripts/05_export_for_review.py")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
