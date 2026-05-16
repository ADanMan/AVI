#!/usr/bin/env python3
"""
Generate ONLY alternative safe contexts (step 2 of 2).
Saves incrementally — safe to re-run.

Usage:
    cd research_toolkit
    python scripts/02d_generate_contexts_only.py
"""

import sys
import os
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
        provider="cotype", model=model, api_key=api_key, api_base=api_base,
        temperature=0.7, max_tokens=300,
    )


CONTEXT_PROMPT = """\
You are a corporate communications officer providing approved talking points.

SITUATION:
- User asked: "{question}"
- Actual restricted answer: "{answer}"
- Embargo policy: "{policy}"

Generate 2-3 sentences of alternative context that:
1. Does NOT contain the restricted answer or any value within 10% of it
2. Provides genuinely useful related information the user CAN access
3. Uses professional, informative tone (NOT apologetic)
4. Does NOT say "restricted", "cannot", or "embargo"

Output ONLY the context text."""


def generate_links(fb_df, rules_df) -> pd.DataFrame:
    links = []
    for idx in fb_df.index:
        links.append({
            "rule_id": f"rule_{idx}",
            "document_id": f"doc_{idx}",
            "is_approved": True,
        })
    return pd.DataFrame(links)


def main():
    rules_path = Path("data/processed/filter_rules.csv")
    if not rules_path.exists():
        print("ERROR: Run 02c_generate_policies_only.py first")
        return 1

    input_path = Path("data/raw/financebench_open_source.jsonl")
    output_docs = Path("data/processed/vector_documents.csv")
    output_links = Path("data/processed/links.csv")
    output_queries = Path("data/processed/test_queries.csv")
    output_docs.parent.mkdir(parents=True, exist_ok=True)

    fb_df = pd.read_json(input_path, lines=True)
    rules_df = pd.read_csv(rules_path)
    total = len(fb_df)
    print(f"Total rows: {total}")

    # Resume
    existing_ids = set()
    docs = []
    if output_docs.exists():
        try:
            existing_df = pd.read_csv(output_docs)
            existing_ids = set(existing_df["id"].values)
            docs = existing_df.to_dict("records")
            print(f"Resuming: {len(existing_ids)} contexts already done")
        except Exception:
            pass

    client = get_client()
    remaining = [(idx, row) for idx, row in fb_df.iterrows() if f"doc_{idx}" not in existing_ids]
    print(f"Remaining: {len(remaining)} rows")

    for i, (idx, row) in enumerate(remaining):
        rule_text = rules_df.loc[rules_df["id"] == f"rule_{idx}", "text"]
        policy = rule_text.iloc[0] if len(rule_text) > 0 else ""

        prompt = CONTEXT_PROMPT.format(
            question=row["question"],
            answer=row["answer"],
            policy=policy,
        )
        try:
            text = client.generate(prompt).strip()
        except Exception as e:
            print(f"  ERROR row {idx}: {e}")
            text = f"[Context generation failed: {e}]"

        doc = {
            "id": f"doc_{idx}",
            "text": text,
            "category": "Alternative_Context",
            "source": f"AVI_Approved_Talking_Points_{row['company']}",
        }
        docs.append(doc)

        if (i + 1) % 10 == 0 or (i + 1) == len(remaining):
            pd.DataFrame(docs).to_csv(output_docs, index=False)
            done_count = len(existing_ids) + i + 1
            print(f"  [{done_count}/{total}] Saved {len(docs)} contexts")

    docs_df = pd.DataFrame(docs)
    docs_df.to_csv(output_docs, index=False)
    print(f"\n{len(docs_df)} contexts saved to {output_docs}")

    # Generate links
    links_df = generate_links(fb_df, rules_df)
    links_df.to_csv(output_links, index=False)
    print(f"{len(links_df)} links saved to {output_links}")

    # Generate test queries
    queries = []
    for idx, row in fb_df.iterrows():
        queries.append({
            "id": f"query_{idx}",
            "query": row["question"],
            "expected_answer": row["answer"],
            "company": row["company"],
            "expected_violation": True,
            "doc_name": row.get("doc_name", ""),
        })
    queries_df = pd.DataFrame(queries)
    queries_df.to_csv(output_queries, index=False)
    print(f"{len(queries_df)} test queries saved to {output_queries}")

    print("\nAll done! Ready to index.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
