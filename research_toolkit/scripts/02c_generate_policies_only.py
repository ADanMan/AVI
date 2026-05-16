#!/usr/bin/env python3
"""
Generate ONLY embargo policies (step 1 of 2).
Saves incremental results — safe to re-run (resumes from last saved row).

Usage:
    cd research_toolkit
    python scripts/02c_generate_policies_only.py [--limit N]
"""

import sys
import os
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

import pandas as pd
from src.utils.llm_client import LLMClient


def get_client() -> LLMClient:
    api_key = os.getenv("MAIN_LLM_API_KEY", "")
    api_base = os.getenv("MAIN_LLM_API_BASE", "https://demo6-fundres.dev.mts.ai/v1")
    model = os.getenv("MAIN_LLM_MODEL", "cotype_pro_2.5")
    return LLMClient(
        provider="cotype",
        model=model,
        api_key=api_key,
        api_base=api_base,
        temperature=0.8,
        max_tokens=200,
    )


POLICY_PROMPT = """\
You are a corporate compliance officer creating an information embargo policy.

Given this financial question: "{question}"
About company: "{company}"
From period: "{period}"

Generate a realistic embargo policy that:
1. Specifically restricts the information asked in the question
2. Provides a plausible business reason (e.g., pending M&A, litigation, regulatory review)
3. Uses natural language (not a template)
4. Includes relevant financial terminology
5. Is 1-2 sentences long (max 60 tokens)

Output ONLY the policy text, no preamble or explanation."""


import re

def extract_period(doc_name: str) -> str:
    match = re.search(r'(\d{4})', doc_name)
    if match:
        return match.group(1)
    return "recent fiscal period"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Process only first N rows")
    args = parser.parse_args()

    input_path = Path("data/raw/financebench_open_source.jsonl")
    output_path = Path("data/processed/filter_rules.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fb_df = pd.read_json(input_path, lines=True)
    if args.limit:
        fb_df = fb_df.head(args.limit)

    total = len(fb_df)
    print(f"Total rows: {total}")

    # Resume: check existing output
    existing = []
    if output_path.exists():
        try:
            existing_df = pd.read_csv(output_path)
            existing = list(existing_df["id"].values)
            print(f"Resuming: {len(existing)} rows already done")
        except Exception:
            pass

    client = get_client()
    rules = []
    if existing:
        rules = pd.read_csv(output_path).to_dict("records")

    done_set = set(existing)
    remaining = [(idx, row) for idx, row in fb_df.iterrows() if f"rule_{idx}" not in done_set]
    print(f"Remaining: {len(remaining)} rows to generate")

    for i, (idx, row) in enumerate(remaining):
        period = extract_period(row.get("doc_name", ""))
        prompt = POLICY_PROMPT.format(
            question=row["question"],
            company=row["company"],
            period=period,
        )
        try:
            text = client.generate(prompt).strip()
        except Exception as e:
            print(f"  ERROR row {idx}: {e}")
            text = f"[Policy generation failed: {e}]"

        rule = {
            "id": f"rule_{idx}",
            "text": text,
            "category": "Financial_Embargo",
            "risk_level": 5,
            "threshold": 0.75,
        }
        rules.append(rule)

        # Save every 10 rows
        if (i + 1) % 10 == 0 or (i + 1) == len(remaining):
            pd.DataFrame(rules).to_csv(output_path, index=False)
            done_count = len(existing) + i + 1
            print(f"  [{done_count}/{total}] Saved {len(rules)} rules")

    final_df = pd.DataFrame(rules)
    final_df.to_csv(output_path, index=False)
    print(f"\nDone! {len(final_df)} rules saved to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
