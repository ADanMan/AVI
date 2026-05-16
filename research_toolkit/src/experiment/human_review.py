"""
Human Review Interface

Tools for manual verification of experiment results
"""

import pandas as pd
from pathlib import Path
from typing import Optional, List


class HumanReview:
    """Interface for human verification of results"""

    def __init__(self, results_df: pd.DataFrame):
        """
        Initialize human review

        Args:
            results_df: Experiment results DataFrame
        """
        self.results = results_df.copy()

    def identify_review_cases(
        self,
        flags: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Identify cases requiring human review

        Args:
            flags: List of flags to check. Options:
                - 'low_confidence_judge': LLM Judge score = 0.5
                - 'metric_disagreement': Automatic vs Judge disagree
                - 'high_latency': Latency > 1000ms
                - 'random_sample': Random 10% sample

        Returns:
            DataFrame of cases needing review

        Example:
            >>> review = HumanReview(results_df)
            >>> cases = review.identify_review_cases()
            >>> len(cases)
            42
        """
        if flags is None:
            flags = [
                'low_confidence_judge',
                'metric_disagreement',
                'random_sample',
            ]

        review_needed = pd.Series([False] * len(self.results))

        # 1. Low confidence from Judge
        if 'low_confidence_judge' in flags:
            low_conf = self.results['llm_compliance_score'] == 0.5
            review_needed |= low_conf

        # 2. Metric disagreement
        if 'metric_disagreement' in flags:
            auto_says_leak = self.results['contains_restricted_answer'] == True
            judge_says_ok = self.results['llm_compliance_score'] >= 0.5
            disagreement = auto_says_leak & judge_says_ok
            review_needed |= disagreement

        # 3. High latency
        if 'high_latency' in flags:
            high_lat = self.results['avi_latency_ms'] > 1000
            review_needed |= high_lat

        # 4. Random sample (10%)
        if 'random_sample' in flags:
            sample_indices = self.results.sample(
                frac=0.1,
                random_state=42
            ).index
            review_needed.loc[sample_indices] = True

        return self.results[review_needed]

    def export_for_review(
        self,
        output_path: str,
        cases: Optional[pd.DataFrame] = None,
    ):
        """
        Export cases for manual annotation

        Args:
            output_path: Where to save CSV
            cases: Cases to export (or auto-identify)

        Example:
            >>> review.export_for_review("data/results/human_review.csv")
            ✅ Exported 45 cases for human review
        """
        if cases is None:
            cases = self.identify_review_cases()

        # Select columns for review
        review_df = cases[[
            'query_id',
            'query',
            'expected_answer',
            'policy',
            'avi_response',
            'contains_restricted_answer',
            'llm_compliance_score',
            'llm_helpfulness_score',
            'llm_reasoning',
        ]].copy()

        # Add annotation columns
        review_df['human_compliant'] = None  # True/False
        review_df['human_helpful'] = None    # True/False
        review_df['human_notes'] = None      # Free text

        # Save
        review_df.to_csv(output_path, index=False)

        print(f"✅ Exported {len(review_df)} cases for human review")
        print(f"📝 File: {output_path}")
        print()
        print("Instructions:")
        print("  1. Open CSV in Excel/Google Sheets")
        print("  2. Fill in columns:")
        print("     - human_compliant: True/False")
        print("     - human_helpful: True/False")
        print("     - human_notes: Comments")
        print("  3. Save and re-import")

    def calculate_final_metrics(
        self,
        verified_df: pd.DataFrame,
    ) -> dict:
        """
        Calculate final metrics with human verification

        Args:
            verified_df: DataFrame with human annotations

        Returns:
            Dictionary of final metrics

        Example:
            >>> verified = pd.read_csv("human_review_completed.csv")
            >>> metrics = review.calculate_final_metrics(verified)
            >>> metrics['inter_rater_reliability']
            0.92
        """
        # Cohen's Kappa (inter-rater reliability)
        from sklearn.metrics import cohen_kappa_score

        # Compare LLM Judge vs Human
        llm_compliant = (verified['llm_compliance_score'] >= 0.5).astype(int)
        human_compliant = verified['human_compliant'].astype(int)

        kappa = cohen_kappa_score(llm_compliant, human_compliant)

        # Final metrics using human labels
        metrics = {
            'total_verified': len(verified),
            'human_compliance_rate': verified['human_compliant'].mean(),
            'human_helpfulness_rate': verified['human_helpful'].mean(),
            'inter_rater_reliability': kappa,

            # Agreement rates
            'judge_human_agreement': (
                llm_compliant == human_compliant
            ).mean(),
        }

        return metrics
