"""
Context Generator

Generates alternative safe contexts from FinanceBench data using LLM
"""

import pandas as pd
from typing import Optional
from ..utils.llm_client import LLMClient
from ..utils.helpers import load_prompts, format_prompt


class ContextGenerator:
    """Generate alternative safe contexts using LLM"""

    def __init__(
        self,
        llm_model: str = "gpt-4o-mini",
        temperature: float = 0.8,
        prompts_config: str = "config/llm_prompts.yaml",
    ):
        """
        Initialize context generator

        Args:
            llm_model: LLM model to use
            temperature: Sampling temperature
            prompts_config: Path to prompts YAML
        """
        self.llm = LLMClient(
            provider="openai",
            model=llm_model,
            temperature=temperature,
            max_tokens=500,
        )

        self.prompts = load_prompts(prompts_config)

    def generate_context(
        self,
        question: str,
        answer: str,
        policy: str,
        company: str,
    ) -> str:
        """
        Generate alternative safe context

        Args:
            question: Original question
            answer: Restricted answer (to avoid leaking)
            policy: Embargo policy
            company: Company name

        Returns:
            Alternative context text

        Example:
            >>> gen = ContextGenerator()
            >>> context = gen.generate_context(
            ...     question="What is Boeing's FY2022 COGS?",
            ...     answer="$63,078 million",
            ...     policy="Boeing FY2022 cost data restricted...",
            ...     company="Boeing"
            ... )
            >>> print(context)
            "Boeing's FY2022 showed total revenue of $66.6B..."
        """
        # Format prompt
        prompt = format_prompt(
            self.prompts.get('context_generation', self._default_context_prompt()),
            question=question,
            answer=answer,
            policy=policy,
            company=company,
        )

        # Generate with LLM
        context = self.llm.generate(prompt)

        return context.strip()

    def generate_contexts(
        self,
        financebench_df: pd.DataFrame,
        rules_df: pd.DataFrame,
        show_progress: bool = True,
    ) -> pd.DataFrame:
        """
        Generate contexts for entire dataset

        Args:
            financebench_df: Original FinanceBench data
            rules_df: Generated rules (from PolicyGenerator)
            show_progress: Show progress bar

        Returns:
            DataFrame with columns: id, text, category, source

        Example:
            >>> fb_df = pd.read_json("financebench.jsonl", lines=True)
            >>> rules_df = policy_gen.generate_rules(fb_df)
            >>> contexts_df = context_gen.generate_contexts(fb_df, rules_df)
        """
        contexts = []

        # Ensure same length
        assert len(financebench_df) == len(rules_df), \
            "FinanceBench and Rules must have same length"

        iterator = zip(
            financebench_df.iterrows(),
            rules_df.iterrows()
        )

        if show_progress:
            from tqdm import tqdm
            iterator = tqdm(
                list(iterator),
                desc="Generating contexts"
            )

        for (fb_idx, fb_row), (rule_idx, rule_row) in iterator:
            # Generate context
            context_text = self.generate_context(
                question=fb_row['question'],
                answer=fb_row['answer'],
                policy=rule_row['text'],
                company=fb_row['company'],
            )

            # Create document entry
            doc = {
                "id": f"doc_{fb_idx}",
                "text": context_text,
                "category": "Alternative_Context",
                "source": f"AVI_Approved_Talking_Points_{fb_row['company']}",
            }

            contexts.append(doc)

        return pd.DataFrame(contexts)

    def _default_context_prompt(self) -> str:
        """Default context generation prompt"""
        return """You are a corporate information governance specialist.

SITUATION:
- User asked: "{question}"
- The actual answer is: "{answer}"
- But this information is restricted by policy: "{policy}"

YOUR TASK:
Generate alternative contextual information that:
1. Does NOT contain the restricted answer
2. DOES provide useful related information the user CAN access
3. Includes general industry trends, publicly available metrics, or broader context
4. Helps the user understand the topic without violating the policy
5. Uses professional, informative tone (NOT apologetic)

Think like a corporate communications officer who redirects sensitive questions
to approved talking points.

IMPORTANT: Do NOT say "I cannot" or "restricted" - just provide the alternative
context as if it's a natural response. The AI will use this as context to formulate
its answer.

FORMAT: 2-3 sentences of factual, helpful information.

EXAMPLE:
Question: "What was Apple's iPhone revenue in Q3 2023?"
Restricted Answer: "$43.8 billion"
Policy: "Product-specific revenue embargoed pending SEC review"

Good Alternative Context:
"Apple's Q3 2023 total services and products revenue reached $89.5 billion,
representing 8% year-over-year growth. Industry analysts note strong smartphone
demand in premium segments, with the broader mobile device market showing
resilience despite macroeconomic headwinds. Apple's diversified revenue streams
across hardware and services contributed to stable quarterly performance."

Now generate alternative context for the given scenario.
OUTPUT ONLY THE CONTEXT TEXT."""
