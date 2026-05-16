#!/usr/bin/env python3
"""
Transform FinanceBench using MTS AI (cotype_pro_2.5) — drop-in for 02_transform_dataset.py.

Reads credentials from AVI .env file or environment variables:
  COTYPE_API_KEY    (or MAIN_LLM_API_KEY)
  COTYPE_API_BASE   (or MAIN_LLM_API_BASE)
  COTYPE_MODEL      (or MAIN_LLM_MODEL)

Usage:
    cd research_toolkit
    python scripts/02b_transform_with_mts.py
"""

import sys
import os
from pathlib import Path

# Add src and project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Load .env from AVI root
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)
    print(f"Loaded .env from {env_path}")

import pandas as pd
from src.utils.llm_client import LLMClient
from src.transform.policy_generator import PolicyGenerator
from src.transform.context_generator import ContextGenerator
from src.transform.dataset_builder import DatasetBuilder
from src.utils.helpers import ensure_dir


def make_cotype_client(temperature: float = 0.8, max_tokens: int = 500) -> LLMClient:
    """Create LLMClient configured for MTS AI / cotype."""
    api_key = (
        os.getenv("COTYPE_API_KEY")
        or os.getenv("MAIN_LLM_API_KEY", "")
    )
    api_base = (
        os.getenv("COTYPE_API_BASE")
        or os.getenv("MAIN_LLM_API_BASE", "https://demo6-fundres.dev.mts.ai/v1")
    )
    model = (
        os.getenv("COTYPE_MODEL")
        or os.getenv("MAIN_LLM_MODEL", "cotype_pro_2.5")
    )
    return LLMClient(
        provider="cotype",
        model=model,
        api_key=api_key,
        api_base=api_base,
        temperature=temperature,
        max_tokens=max_tokens,
    )


class CotypePolicyGenerator(PolicyGenerator):
    """PolicyGenerator backed by MTS AI."""

    def __init__(self, prompts_config: str = "config/llm_prompts.yaml"):
        # Bypass parent __init__ to inject our client
        self.llm = make_cotype_client(temperature=0.8, max_tokens=500)
        from src.utils.helpers import load_prompts
        self.prompts = load_prompts(prompts_config)


class CotypeContextGenerator(ContextGenerator):
    """ContextGenerator backed by MTS AI."""

    def __init__(self, prompts_config: str = "config/llm_prompts.yaml"):
        self.llm = make_cotype_client(temperature=0.8, max_tokens=500)
        from src.utils.helpers import load_prompts
        self.prompts = load_prompts(prompts_config)


def main() -> int:
    print("=" * 60)
    print("Transform FinanceBench → AVI Format (MTS AI / cotype)")
    print("=" * 60)

    input_path = Path("data/raw/financebench_open_source.jsonl")
    output_dir = Path("data/processed")

    if not input_path.exists():
        print(f"ERROR: {input_path} not found — run 01_download_financebench.py first")
        return 1

    print(f"Loading {input_path}...")
    fb_df = pd.read_json(input_path, lines=True)
    print(f"Loaded {len(fb_df)} questions")

    builder = DatasetBuilder(
        policy_generator=CotypePolicyGenerator(),
        context_generator=CotypeContextGenerator(),
    )

    rules_df, documents_df, links_df = builder.build_from_financebench(
        fb_df,
        output_dir=str(output_dir),
        save=True,
        show_progress=True,
    )

    print(f"\nGenerated: {len(rules_df)} rules, {len(documents_df)} docs, {len(links_df)} links")

    test_queries = builder.create_test_queries(
        fb_df,
        output_path=str(output_dir / "test_queries.csv"),
    )
    print(f"Created {len(test_queries)} test queries")

    print("\nSample rule:")
    print(f"  {rules_df.iloc[0]['text'][:120]}...")

    print("\nDataset ready — next: run index_rules.py then 06_rigorous_evaluation.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
