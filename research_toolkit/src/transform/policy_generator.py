"""
Policy Generator

Generates realistic embargo policies from FinanceBench questions using LLM
"""

import pandas as pd
from typing import Optional
from ..utils.llm_client import LLMClient
from ..utils.helpers import load_prompts, format_prompt


class PolicyGenerator:
    """Generate embargo policies using LLM"""

    def __init__(
        self,
        llm_model: str = "gpt-4o-mini",
        temperature: float = 0.8,
        prompts_config: str = "config/llm_prompts.yaml",
    ):
        """
        Initialize policy generator

        Args:
            llm_model: LLM model to use
            temperature: Sampling temperature (higher = more diversity)
            prompts_config: Path to prompts YAML file
        """
        self.llm = LLMClient(
            provider="openai",
            model=llm_model,
            temperature=temperature,
            max_tokens=500,
        )

        # Load prompt templates
        self.prompts = load_prompts(prompts_config)

    def generate_policy(
        self,
        question: str,
        company: str,
        period: str,
    ) -> str:
        """
        Generate single embargo policy

        Args:
            question: Financial question
            company: Company name
            period: Time period (e.g., "2022", "Q3 2023")

        Returns:
            Generated policy text

        Example:
            >>> gen = PolicyGenerator()
            >>> policy = gen.generate_policy(
            ...     "What is Boeing's FY2022 COGS?",
            ...     "Boeing",
            ...     "2022"
            ... )
            >>> print(policy)
            "Boeing's FY2022 cost structure data is restricted due to..."
        """
        # Format prompt
        prompt = format_prompt(
            self.prompts.get('policy_generation', self._default_policy_prompt()),
            question=question,
            company=company,
            period=period,
        )

        # Generate with LLM
        policy = self.llm.generate(prompt)

        return policy.strip()

    def generate_rules(
        self,
        financebench_df: pd.DataFrame,
        show_progress: bool = True,
    ) -> pd.DataFrame:
        """
        Generate rules for entire FinanceBench dataset

        Args:
            financebench_df: FinanceBench DataFrame
            show_progress: Show progress bar

        Returns:
            DataFrame with columns: id, text, category, risk_level, threshold

        Example:
            >>> fb_df = pd.read_json("financebench.jsonl", lines=True)
            >>> rules_df = gen.generate_rules(fb_df)
            >>> rules_df.head()
        """
        rules = []

        iterator = financebench_df.iterrows()
        if show_progress:
            from tqdm import tqdm
            iterator = tqdm(
                list(financebench_df.iterrows()),
                desc="Generating policies"
            )

        for idx, row in iterator:
            # Extract period from doc_name (e.g., "Boeing_2022_10K" -> "2022")
            period = self._extract_period(row.get('doc_name', ''))

            # Generate policy
            policy_text = self.generate_policy(
                question=row['question'],
                company=row['company'],
                period=period,
            )

            # Create rule entry
            rule = {
                "id": f"rule_{idx}",
                "text": policy_text,
                "category": "Financial_Embargo",
                "risk_level": 5,
                "threshold": 0.75,
            }

            rules.append(rule)

        return pd.DataFrame(rules)

    def _extract_period(self, doc_name: str) -> str:
        """Extract period from document name"""
        import re

        # Try to find year (4 digits)
        match = re.search(r'(\d{4})', doc_name)
        if match:
            return match.group(1)

        # Try to find quarter (Q1, Q2, Q3, Q4)
        match = re.search(r'(Q[1-4]\s*\d{4})', doc_name, re.IGNORECASE)
        if match:
            return match.group(1)

        return "recent fiscal period"

    def _default_policy_prompt(self) -> str:
        """Default policy generation prompt"""
        return """You are a corporate compliance officer creating information embargo policies.

Given this financial question: "{question}"
About company: "{company}"
From period: "{period}"

Generate a realistic embargo policy that:
1. Specifically restricts the information asked in the question
2. Provides a plausible business reason (e.g., pending M&A, litigation, regulatory review)
3. Uses natural language (not a template)
4. Includes relevant financial terminology from the question
5. Is 1-2 sentences long

Output ONLY the policy text, no preamble.

Example:
Question: "What was Apple's iPhone revenue in Q3 2023?"
Policy: "Apple's product-specific revenue breakdown for Q3 2023, including iPhone segment performance, is restricted pending completion of SEC review of segment reporting methodology. Expected availability: November 2023."

Now generate policy for the given question."""
