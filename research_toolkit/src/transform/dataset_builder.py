"""
Dataset Builder

Builds complete AVI dataset (rules, documents, links) from FinanceBench
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Tuple
from .policy_generator import PolicyGenerator
from .context_generator import ContextGenerator
from ..utils.helpers import ensure_dir


class DatasetBuilder:
    """Build complete AVI dataset from FinanceBench"""

    def __init__(
        self,
        policy_generator: Optional[PolicyGenerator] = None,
        context_generator: Optional[ContextGenerator] = None,
    ):
        """
        Initialize dataset builder

        Args:
            policy_generator: PolicyGenerator instance (or create default)
            context_generator: ContextGenerator instance (or create default)
        """
        self.policy_gen = policy_generator or PolicyGenerator()
        self.context_gen = context_generator or ContextGenerator()

    def build_from_financebench(
        self,
        financebench_df: pd.DataFrame,
        output_dir: str = "data/processed",
        save: bool = True,
        show_progress: bool = True,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Build complete dataset from FinanceBench

        Args:
            financebench_df: FinanceBench DataFrame
            output_dir: Directory to save CSV files
            save: Whether to save to disk
            show_progress: Show progress bars

        Returns:
            Tuple of (rules_df, documents_df, links_df)

        Example:
            >>> fb_df = pd.read_json("data/raw/financebench.jsonl", lines=True)
            >>> builder = DatasetBuilder()
            >>> rules, docs, links = builder.build_from_financebench(fb_df)
            ✅ Generated 150 rules
            ✅ Generated 150 documents
            ✅ Created 150 links
            💾 Saved to data/processed/
        """
        print(f"🔧 Building AVI dataset from {len(financebench_df)} questions...")

        # 1. Generate rules (policies)
        print("📝 Generating embargo policies...")
        rules_df = self.policy_gen.generate_rules(
            financebench_df,
            show_progress=show_progress
        )
        print(f"✅ Generated {len(rules_df)} rules")

        # 2. Generate documents (alternative contexts)
        print("📄 Generating alternative contexts...")
        documents_df = self.context_gen.generate_contexts(
            financebench_df,
            rules_df,
            show_progress=show_progress
        )
        print(f"✅ Generated {len(documents_df)} documents")

        # 3. Create links (rule → document mappings)
        print("🔗 Creating links...")
        links_df = self.create_links(rules_df, documents_df)
        print(f"✅ Created {len(links_df)} links")

        # 4. Save if requested
        if save:
            self.save_dataset(rules_df, documents_df, links_df, output_dir)
            print(f"💾 Saved to {output_dir}/")

        return rules_df, documents_df, links_df

    def create_links(
        self,
        rules_df: pd.DataFrame,
        documents_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Create links between rules and documents

        Args:
            rules_df: Rules DataFrame
            documents_df: Documents DataFrame

        Returns:
            Links DataFrame with columns: rule_id, document_id, is_approved

        Example:
            >>> links_df = builder.create_links(rules_df, documents_df)
            >>> links_df.head()
               rule_id document_id  is_approved
            0   rule_0      doc_0         True
            1   rule_1      doc_1         True
        """
        links = []

        # Simple 1:1 mapping (rule_i → doc_i)
        for idx in range(len(rules_df)):
            link = {
                "rule_id": f"rule_{idx}",
                "document_id": f"doc_{idx}",
                "is_approved": True,
            }
            links.append(link)

        return pd.DataFrame(links)

    def save_dataset(
        self,
        rules_df: pd.DataFrame,
        documents_df: pd.DataFrame,
        links_df: pd.DataFrame,
        output_dir: str = "data/processed",
    ):
        """Save dataset to CSV files"""
        output_path = ensure_dir(output_dir)

        # Save CSVs
        rules_df.to_csv(output_path / "filter_rules.csv", index=False)
        documents_df.to_csv(output_path / "vector_documents.csv", index=False)
        links_df.to_csv(output_path / "links.csv", index=False)

    def create_test_queries(
        self,
        financebench_df: pd.DataFrame,
        output_path: str = "data/processed/test_queries.csv",
    ) -> pd.DataFrame:
        """
        Create test queries CSV from FinanceBench

        Args:
            financebench_df: FinanceBench DataFrame
            output_path: Where to save test queries

        Returns:
            Test queries DataFrame

        Example:
            >>> test_queries = builder.create_test_queries(fb_df)
            >>> test_queries.columns
            ['id', 'query', 'expected_answer', 'company', 'expected_violation']
        """
        test_queries = []

        for idx, row in financebench_df.iterrows():
            query = {
                "id": f"query_{idx}",
                "query": row['question'],
                "expected_answer": row['answer'],
                "company": row['company'],
                "expected_violation": True,  # All should be blocked
                "doc_name": row.get('doc_name', ''),
            }
            test_queries.append(query)

        test_df = pd.DataFrame(test_queries)

        # Save
        test_df.to_csv(output_path, index=False)
        print(f"💾 Saved {len(test_df)} test queries to {output_path}")

        return test_df
