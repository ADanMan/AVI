"""
OpenAI Moderation API plugin for AVI.

This plugin integrates OpenAI's Moderation API for content safety checks.

Installation:
    pip install openai

Configuration:
    OPENAI_API_KEY=your-key-here

Usage:
    from src.services.safety_plugin import SafetyPluginLoader

    plugin = SafetyPluginLoader.load_plugin(
        "examples.safety_plugins.openai_moderation.OpenAIModerationPlugin",
        config={"api_key": "your-openai-key"}
    )
"""

from __future__ import annotations

from src.services.safety_plugin import SafetyModelPlugin, SafetyResult


class OpenAIModerationPlugin(SafetyModelPlugin):
    """
    Safety plugin using OpenAI's Moderation API.

    Categories detected:
    - hate
    - hate/threatening
    - harassment
    - harassment/threatening
    - self-harm
    - self-harm/intent
    - self-harm/instructions
    - sexual
    - sexual/minors
    - violence
    - violence/graphic
    """

    def __init__(self, api_key: str, threshold: float = 0.01):
        """
        Initialize OpenAI Moderation plugin.

        Args:
            api_key: OpenAI API key
            threshold: Threshold for flagging content (0.0-1.0)
        """
        self.api_key = api_key
        self.threshold = threshold

        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai package required. Install with: pip install openai")

        self.client = AsyncOpenAI(api_key=api_key)

    async def check_safety(self, text: str, context: str | None = None) -> SafetyResult:
        """Check text safety using OpenAI Moderation API."""
        try:
            response = await self.client.moderations.create(input=text)
            result = response.results[0]

            # Determine if content is safe
            is_safe = not result.flagged

            # Extract flagged categories
            categories = []
            max_score = 0.0

            for category, flagged in result.categories.model_dump().items():
                if flagged:
                    categories.append(category)
                    score = result.category_scores.model_dump()[category]
                    max_score = max(max_score, score)

            # Build explanation
            if categories:
                explanation = f"Content flagged for: {', '.join(categories)}"
            else:
                explanation = "Content passed all safety checks"

            return SafetyResult(
                is_safe=is_safe,
                confidence=max_score if not is_safe else (1.0 - max_score),
                categories=categories,
                explanation=explanation,
                sanitized_text=None,  # OpenAI API doesn't provide sanitization
            )

        except Exception as e:
            # Return error as unsafe with low confidence
            return SafetyResult(
                is_safe=False,
                confidence=0.5,
                categories=["error"],
                explanation=f"Safety check failed: {str(e)}",
                sanitized_text=None,
            )

    async def check_health(self) -> bool:
        """Health check for OpenAI API."""
        try:
            # Simple test with benign content
            await self.client.moderations.create(input="Hello")
            return True
        except Exception:
            return False

    @property
    def model_name(self) -> str:
        """Return model identifier."""
        return "openai-moderation-latest"
