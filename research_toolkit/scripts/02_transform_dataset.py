#!/usr/bin/env python3
"""
Transform FinanceBench dataset to AVI format using LLM

Generates:
- filter_rules.csv (embargo policies)
- vector_documents.csv (alternative contexts)
- links.csv (rule-document mappings)
- test_queries.csv (test dataset)

Usage:
    python scripts/02_transform_dataset.py
"""

import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from transform.dataset_builder import DatasetBuilder
from utils.helpers import ensure_dir


def main():
    print("=" * 60)
    print("🔄 Transform FinanceBench to AVI Format")
    print("=" * 60)
    print()

    # Paths
    input_path = Path("data/raw/financebench_open_source.jsonl")
    output_dir = Path("data/processed")

    # Check input exists
    if not input_path.exists():
        print(f"❌ Error: {input_path} not found!")
        print(f"   Run: python scripts/01_download_financebench.py")
        return 1

    # Load FinanceBench
    print(f"📂 Loading FinanceBench from {input_path}...")
    fb_df = pd.read_json(input_path, lines=True)
    print(f"✅ Loaded {len(fb_df)} questions")
    print()

    # Initialize builder
    print("🏗️  Initializing DatasetBuilder...")
    builder = DatasetBuilder()
    print("✅ Builder ready")
    print()

    # Build dataset
    print("🚀 Starting transformation (this will take a few minutes)...")
    print()

    rules_df, documents_df, links_df = builder.build_from_financebench(
        fb_df,
        output_dir=str(output_dir),
        save=True,
        show_progress=True,
    )

    print()
    print("=" * 60)
    print("✨ Transformation Complete!")
    print("=" * 60)
    print()

    # Summary
    print(f"📊 Summary:")
    print(f"   Rules:     {len(rules_df)}")
    print(f"   Documents: {len(documents_df)}")
    print(f"   Links:     {len(links_df)}")
    print()

    # Create test queries
    print("📝 Creating test queries...")
    test_queries = builder.create_test_queries(
        fb_df,
        output_path=str(output_dir / "test_queries.csv")
    )
    print()

    # Show samples
    print("📋 Sample Rule:")
    print(f"   ID:   {rules_df.iloc[0]['id']}")
    print(f"   Text: {rules_df.iloc[0]['text'][:100]}...")
    print()

    print("📄 Sample Document:")
    print(f"   ID:   {documents_df.iloc[0]['id']}")
    print(f"   Text: {documents_df.iloc[0]['text'][:100]}...")
    print()

    print("🔗 Sample Link:")
    print(f"   {links_df.iloc[0]['rule_id']} → {links_df.iloc[0]['document_id']}")
    print()

    print("=" * 60)
    print("🎉 Dataset ready for upload to AVI!")
    print("=" * 60)
    print()

    print("Next steps:")
    print("  1. Upload to AVI: Use AVI API to upload CSVs")
    print("  2. Run experiment: python scripts/03_run_experiment.py")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
