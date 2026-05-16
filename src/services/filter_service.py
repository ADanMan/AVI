"""
FilterService: service for working with filters and rules.
"""

from typing import Any

from src.core.content_filter import ContentFilterService, create_content_filter_service
from src.models.schemas import FilteredContent
from src.services.vector_db import VectorDBClient, VectorDBService


class FilterService:
    def __init__(
        self,
        vector_db: VectorDBClient | None = None,
        content_filter: ContentFilterService | None = None,
    ):
        self.vector_db = vector_db or VectorDBService()
        self.content_filter = content_filter or create_content_filter_service(
            vector_db=self.vector_db
        )

    async def filter_input(
        self,
        text: str,
        use_llm: bool = False,
        use_linked_docs: bool = True,
        context_docs=None,
        # New granular control parameters
        enable_vector_rules: bool = True,
        enable_prompt_modification: bool = True,
    ):
        """
        Filter input text using ContentFilterService with configurable components.

        Args:
            text: Input text to filter.
            use_llm: Whether to use LLM-based filtering (Safety LLM).
            use_linked_docs: Whether to use linked documents for filtering.
            context_docs: Optional context documents to include in modified text.
            enable_vector_rules: Enable vector-based rule matching. Default: True.
            enable_prompt_modification: Enable prompt modification when matches found. Default: True.

        Returns:
            FilterResult: Filtering result object.
        """
        return await self.content_filter.check_content(
            text,
            use_llm=use_llm,
            use_linked_docs=use_linked_docs,
            is_input=True,
            context=(
                "\n\n".join([doc.get("text", "") for doc in context_docs]) if context_docs else None
            ),
            enable_vector_rules=enable_vector_rules,
            enable_prompt_modification=enable_prompt_modification,
            enable_output_cleaning=False,  # N/A for input
        )

    async def filter_output(
        self,
        text: str,
        use_linked_docs: bool = True,
        context_docs=None,
        # New granular control parameters
        use_llm: bool = False,  # Now configurable for output!
        enable_vector_rules: bool = True,
        enable_output_cleaning: bool = True,
    ):
        """
        Filter output text using ContentFilterService with configurable components.

        Args:
            text: Output text to filter.
            use_linked_docs: Whether to use linked documents for filtering.
            context_docs: Optional context documents for filtering.
            use_llm: Whether to use LLM-based filtering for output (previously hardcoded to False). Default: False.
            enable_vector_rules: Enable vector-based rule matching. Default: True.
            enable_output_cleaning: Enable output content cleaning (system prompt removal). Default: True.

        Returns:
            FilterResult: Filtering result object.
        """
        return await self.content_filter.check_content(
            text,
            use_llm=use_llm,  # Now configurable!
            use_linked_docs=use_linked_docs,
            is_input=False,
            context=(
                "\n\n".join([doc.get("text", "") for doc in context_docs]) if context_docs else None
            ),
            enable_vector_rules=enable_vector_rules,
            enable_prompt_modification=False,  # N/A for output
            enable_output_cleaning=enable_output_cleaning,
        )

    async def validate_rule(self, rule: FilteredContent) -> dict[str, Any]:
        """
        Validate a filtering rule before adding/updating it.

        Performs comprehensive validation including:
        - Basic field validation (text, category, risk_level, threshold)
        - Duplicate detection (checks if rule with same text already exists)
        - Category validation (warns if category is non-standard)

        Args:
            rule: FilteredContent instance to validate.

        Returns:
            dict with validation result:
                {
                    "valid": bool,
                    "errors": list[str],
                    "warnings": list[str],
                    "duplicate_rule_id": str | None
                }

        Example:
            >>> rule = FilteredContent(
            ...     text="No violence",
            ...     category="violence",
            ...     risk_level=5,
            ...     threshold=0.8
            ... )
            >>> result = await filter_service.validate_rule(rule)
            >>> if not result["valid"]:
            ...     print(f"Errors: {result['errors']}")
        """
        from src.utils.logger import logger

        errors: list[str] = []
        warnings: list[str] = []
        duplicate_rule_id: str | None = None

        # Standard categories (can be extended based on your use case)
        standard_categories = {
            # Safety categories
            "violence",
            "hate",
            "toxicity",
            "harassment",
            "sexual",
            "self-harm",
            # Content categories
            "discrimination",
            "bias",
            "misinformation",
            "profanity",
            # Security categories
            "prompt_injection",
            "jailbreak",
            "pii",
            "data_leakage",
            # General
            "general",
            "other",
        }

        # 1. Basic field validation (Pydantic already validates most of this)
        # But we check explicitly for edge cases

        # Check text
        if not rule.text or not rule.text.strip():
            errors.append("Rule text cannot be empty")
        elif len(rule.text) < 5:
            warnings.append(
                "Rule text is very short (< 5 characters). Consider making it more descriptive."
            )
        elif len(rule.text) > 500:
            warnings.append(
                "Rule text is very long (> 500 characters). Consider splitting into multiple rules."
            )

        # Check category
        if not rule.category or not rule.category.strip():
            errors.append("Rule category cannot be empty")
        else:
            # Normalize category for comparison (lowercase, replace spaces with underscores)
            normalized_category = rule.category.lower().replace(" ", "_")
            if normalized_category not in standard_categories:
                warnings.append(
                    f"Category '{rule.category}' is not a standard category. "
                    f"Standard categories: {', '.join(sorted(standard_categories))}"
                )

        # Check risk_level
        if rule.risk_level < 1 or rule.risk_level > 5:
            errors.append(f"Risk level must be between 1 and 5, got {rule.risk_level}")

        # Check threshold
        if rule.threshold < 0.0 or rule.threshold > 1.0:
            errors.append(f"Threshold must be between 0.0 and 1.0, got {rule.threshold}")
        elif rule.threshold < 0.5:
            warnings.append(
                f"Threshold {rule.threshold} is very low. This may cause many false positives."
            )

        # 2. Check for duplicate rules (same text)
        try:
            existing_rules = await self.vector_db.get_all_rules()
            for existing_rule in existing_rules:
                existing_text = existing_rule.get("text", "").strip().lower()
                new_text = rule.text.strip().lower()

                if existing_text == new_text:
                    duplicate_rule_id = existing_rule.get("id")
                    errors.append(
                        f"Duplicate rule detected. A rule with this text already exists (ID: {duplicate_rule_id})"
                    )
                    break
                elif self._is_similar_text(existing_text, new_text):
                    warnings.append(
                        f"Similar rule may exist (ID: {existing_rule.get('id')}): '{existing_rule.get('text')}'"
                    )

        except Exception as e:
            logger.error(f"Error checking for duplicate rules: {e}")
            warnings.append(f"Could not check for duplicate rules: {e!s}")

        # Determine if valid
        is_valid = len(errors) == 0

        result = {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "duplicate_rule_id": duplicate_rule_id,
        }

        logger.info(
            f"Rule validation result: valid={is_valid}, "
            f"errors={len(errors)}, warnings={len(warnings)}, "
            f"category='{rule.category}', risk_level={rule.risk_level}"
        )

        return result

    def _is_similar_text(self, text1: str, text2: str, threshold: float = 0.8) -> bool:
        """
        Check if two text strings are similar using simple character overlap.

        Args:
            text1: First text string
            text2: Second text string
            threshold: Similarity threshold (0.0-1.0)

        Returns:
            True if texts are similar, False otherwise
        """
        # Simple similarity check based on word overlap
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return False

        intersection = words1 & words2
        union = words1 | words2

        similarity = len(intersection) / len(union) if union else 0.0
        return similarity >= threshold

    async def get_rules(self):
        """
        Get all filtering rules from the vector database.
        Returns:
            List of rules.
        """
        return await self.vector_db.get_all_rules()

    async def get_rule_by_id(self, rule_id: str):
        """
        Get a filtering rule by its ID from the vector database.
        Args:
            rule_id: Rule identifier.
        Returns:
            Rule object or None.
        """
        return await self.vector_db.get_rule(rule_id)

    async def get_rule_ids(self) -> list:
        """
        Get all rule IDs from the vector database.
        Returns:
            List of rule IDs (str).
        """
        rules = await self.get_rules()
        return [rule["id"] for rule in rules] if rules else []

    async def get_rules_dict(self) -> list:
        """
        Get all filtering rules as a list of dicts (for API or testing).
        Returns:
            List of rule dicts.
        """
        rules = await self.get_rules()
        return [dict(rule) for rule in rules] if rules else []

    async def get_rule_by_text(self, text: str) -> dict:
        """
        Get a filtering rule by its text content (for testing or API).
        Args:
            text: Rule text to search for.
        Returns:
            Rule dict or None.
        """
        rules = await self.get_rules()
        for rule in rules:
            if rule.get("text") == text:
                return dict(rule)
        return None
