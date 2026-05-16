#!/usr/bin/env python3
"""
Download FinanceBench dataset from HuggingFace

Downloads the PatronusAI/financebench dataset and saves it to data/raw/

Usage:
    python scripts/01_download_financebench.py
"""

import sys
from pathlib import Path
import pandas as pd
from datasets import load_dataset

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main():
    print("=" * 60)
    print("📥 Download FinanceBench Dataset")
    print("=" * 60)
    print()

    # Setup paths
    output_dir = Path("data/raw")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "financebench_open_source.jsonl"

    # Download dataset
    print("📥 Downloading FinanceBench from HuggingFace...")
    print("   Dataset: PatronusAI/financebench")
    print()

    try:
        fb_dataset = load_dataset("PatronusAI/financebench")
    except Exception as e:
        print(f"❌ Error downloading dataset: {e}")
        print()
        print("Make sure you have internet connection and datasets library installed:")
        print("   pip install datasets")
        return 1

    # Convert to DataFrame
    fb_df = fb_dataset['train'].to_pandas()

    print(f"✅ Downloaded {len(fb_df)} questions")
    print(f"   Columns: {fb_df.columns.tolist()}")
    print()

    # Save to JSONL
    print(f"💾 Saving to {output_path}...")
    fb_df.to_json(output_path, orient='records', lines=True)

    print(f"✅ Saved successfully!")
    print()

    # Display summary
    print("=" * 60)
    print("📊 Dataset Summary")
    print("=" * 60)
    print()
    print(f"Total questions: {len(fb_df)}")
    print(f"Unique companies: {fb_df['company'].nunique()}")

    if 'question' in fb_df.columns:
        fb_df['question_length'] = fb_df['question'].str.len()
        print(f"Average question length: {fb_df['question_length'].mean():.0f} characters")

    print()
    print("=" * 60)
    print("✨ Download complete!")
    print("=" * 60)
    print()

    print("📝 Next step:")
    print("   python scripts/02_transform_dataset.py")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
