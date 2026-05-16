#!/usr/bin/env python3
"""
Index generated rules and documents into AVI via its REST API.

Usage:
    python scripts/index_rules.py \
        --avi-url http://localhost:8765 \
        --avi-key <KEY> \
        --rules data/processed/filter_rules.csv \
        --docs data/processed/vector_documents.csv \
        --links data/processed/links.csv
"""

import argparse
import sys
import time
from pathlib import Path

import httpx
import pandas as pd


def upload_csv(
    client: httpx.Client,
    endpoint: str,
    csv_path: Path,
    text_columns: str,
    metadata_columns: str,
    label: str,
) -> None:
    print(f"  Uploading {label} ({csv_path.name})...")
    with open(csv_path, "rb") as fh:
        resp = client.post(
            endpoint,
            data={
                "text_columns": text_columns,
                "metadata_columns": metadata_columns,
                "batch_size": "200",
            },
            files={"file": (csv_path.name, fh, "text/csv")},
            timeout=120,
        )
    if resp.status_code not in (200, 201, 202):
        print(f"  ERROR {resp.status_code}: {resp.text[:500]}")
        sys.exit(1)
    data = resp.json()
    print(f"  OK — {data.get('processed_documents', '?')} items indexed")


def apply_links(
    client: httpx.Client,
    base_url: str,
    links_df: pd.DataFrame,
) -> None:
    print(f"  Applying {len(links_df)} rule→document links...")
    ok = 0
    for _, row in links_df.iterrows():
        resp = client.post(
            f"{base_url}/api/v1/rules/{row['rule_id']}/documents",
            json={"document_ids": [row["document_id"]], "is_approved": True},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            ok += 1
        else:
            pass  # tolerate individual failures
    print(f"  OK — {ok}/{len(links_df)} links created")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--avi-url", default="http://localhost:8765")
    parser.add_argument("--avi-key", default="")
    parser.add_argument("--rules", default="data/processed/filter_rules.csv")
    parser.add_argument("--docs", default="data/processed/vector_documents.csv")
    parser.add_argument("--links", default="data/processed/links.csv")
    args = parser.parse_args()

    headers = {}
    if args.avi_key:
        headers["X-API-Key"] = args.avi_key

    base = args.avi_url.rstrip("/")

    with httpx.Client(base_url=base, headers=headers) as client:
        # 1. Upload documents
        docs_path = Path(args.docs)
        if docs_path.exists():
            upload_csv(
                client,
                f"{base}/api/v1/upload/documents",
                docs_path,
                text_columns="text",
                metadata_columns="category,source",
                label="knowledge documents",
            )
        else:
            print(f"  SKIP documents — {docs_path} not found")

        # 2. Upload rules
        rules_path = Path(args.rules)
        if rules_path.exists():
            upload_csv(
                client,
                f"{base}/api/v1/upload/rules",
                rules_path,
                text_columns="text",
                metadata_columns="category,risk_level,threshold",
                label="filter rules",
            )
        else:
            print(f"  ERROR — {rules_path} not found")
            sys.exit(1)

        # 3. Apply links
        links_path = Path(args.links)
        if links_path.exists():
            links_df = pd.read_csv(links_path)
            apply_links(client, base, links_df)
        else:
            print(f"  SKIP links — {links_path} not found")

    print("\nIndexing complete.")


if __name__ == "__main__":
    main()
