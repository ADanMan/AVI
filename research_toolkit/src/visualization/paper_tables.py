"""
Paper Tables Generator

Generates tables for paper
"""

import pandas as pd
from pathlib import Path


class PaperTables:
    """Generate publication-ready tables"""

    def __init__(self, results_df: pd.DataFrame):
        """
        Initialize table generator

        Args:
            results_df: Experiment results DataFrame
        """
        self.results = results_df

    def generate_performance_table(
        self,
        save_path: str = "paper/tables/table1_performance.csv",
    ) -> pd.DataFrame:
        """
        Generate overall performance table

        Returns:
            Performance metrics table

        Example:
            >>> tables = PaperTables(results_df)
            >>> perf = tables.generate_performance_table()
        """
        metrics = {
            'Metric': [
                'Compliance Rate',
                'Leak Rate',
                'Mean Helpfulness',
                'Mean Naturalness',
                'Mean Latency Overhead (ms)',
                'P95 Latency Overhead (ms)',
            ],
            'AVI': [
                f"{(self.results['llm_compliance_score'] >= 0.5).mean():.1%}",
                f"{self.results['contains_restricted_answer'].mean():.1%}",
                f"{self.results['llm_helpfulness_score'].mean():.2f}/1.0",
                f"{self.results['llm_naturalness_score'].mean():.2f}/1.0",
                f"{self.results['latency_overhead_ms'].mean():.1f}",
                f"{self.results['latency_overhead_ms'].quantile(0.95):.1f}",
            ],
        }

        table = pd.DataFrame(metrics)

        # Save
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(save_path, index=False)

        print(f"💾 Saved: {save_path}")
        print()
        print(table.to_string(index=False))

        return table

    def generate_qualitative_examples(
        self,
        n_examples: int = 3,
        save_path: str = "paper/tables/table2_examples.csv",
    ) -> pd.DataFrame:
        """
        Generate qualitative examples table

        Args:
            n_examples: Number of examples
            save_path: Where to save

        Returns:
            Examples table
        """
        # Select diverse examples
        # 1. High compliance + high helpfulness
        ideal = self.results[
            (self.results['llm_compliance_score'] == 1.0) &
            (self.results['llm_helpfulness_score'] >= 0.8)
        ].sample(min(1, len(self.results)))

        # 2. Compliant but low helpfulness
        safe_unhelpful = self.results[
            (self.results['llm_compliance_score'] == 1.0) &
            (self.results['llm_helpfulness_score'] <= 0.5)
        ].sample(min(1, len(self.results)))

        # 3. Leak detected
        leaked = self.results[
            self.results['contains_restricted_answer'] == True
        ].sample(min(1, len(self.results)))

        examples = pd.concat([ideal, safe_unhelpful, leaked])

        # Format for table
        table = examples[[
            'query',
            'expected_answer',
            'avi_response',
            'llm_compliance_score',
            'llm_helpfulness_score',
            'contains_restricted_answer',
        ]].copy()

        table = table.rename(columns={
            'query': 'Query',
            'expected_answer': 'Restricted Answer',
            'avi_response': 'AVI Response',
            'llm_compliance_score': 'Compliance',
            'llm_helpfulness_score': 'Helpfulness',
            'contains_restricted_answer': 'Leak Detected',
        })

        # Truncate long text
        for col in ['Query', 'Restricted Answer', 'AVI Response']:
            table[col] = table[col].str[:200] + '...'

        # Save
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(save_path, index=False)

        print(f"💾 Saved: {save_path}")

        return table

    def generate_latency_table(
        self,
        save_path: str = "paper/tables/table3_latency.csv",
    ) -> pd.DataFrame:
        """Generate latency percentiles table"""
        percentiles = [50, 75, 90, 95, 99]

        data = {
            'Percentile': [f"P{p}" for p in percentiles],
            'Baseline (ms)': [
                self.results['baseline_latency_ms'].quantile(p/100)
                for p in percentiles
            ],
            'AVI (ms)': [
                self.results['avi_latency_ms'].quantile(p/100)
                for p in percentiles
            ],
            'Overhead (ms)': [
                self.results['latency_overhead_ms'].quantile(p/100)
                for p in percentiles
            ],
        }

        table = pd.DataFrame(data)

        # Format
        for col in ['Baseline (ms)', 'AVI (ms)', 'Overhead (ms)']:
            table[col] = table[col].round(1)

        # Save
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(save_path, index=False)

        print(f"💾 Saved: {save_path}")
        print()
        print(table.to_string(index=False))

        return table

    def generate_all_tables(
        self,
        output_dir: str = "paper/tables",
    ):
        """Generate all tables"""
        print("📊 Generating all tables...")
        print()

        self.generate_performance_table(f"{output_dir}/table1_performance.csv")
        print()
        self.generate_qualitative_examples(f"{output_dir}/table2_examples.csv")
        print()
        self.generate_latency_table(f"{output_dir}/table3_latency.csv")

        print()
        print(f"✨ All tables saved to {output_dir}/")
