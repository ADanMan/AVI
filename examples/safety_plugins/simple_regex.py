"""
Simple regex-based safety plugin for AVI.

This is a basic example showing how to implement a custom safety check
using regular expressions. Useful for learning or as a starting point.

Usage:
    from src.services.safety_plugin import SafetyPluginLoader

    plugin = SafetyPluginLoader.load_plugin(
        "examples.safety_plugins.simple_regex.SimpleRegexPlugin",
        config={
            "patterns": {
                "profanity": [r"\bbad\w*\b", r"\bdamn\w*\b"],
                "violence": [r"\bkill\w*\b", r"\bharm\w*\b"]
            },
            "case_sensitive": False
        }
    )
"""

from __future__ import annotations

import re

from src.services.safety_plugin import SafetyModelPlugin, SafetyResult


class SimpleRegexPlugin(SafetyModelPlugin):
    """
    Simple safety plugin using regex patterns.

    This is a basic example for educational purposes. For production use,
    consider more sophisticated models like Llama Guard or OpenAI Moderation.
    """

    DEFAULT_PATTERNS = {
        "profanity": [
            r"\bbadword\w*\b",
            r"\boffensive\w*\b",
        ],
        "violence": [
            r"\bharm\w*\b",
            r"\battack\w*\b",
        ],
        "hate": [
            r"\bhate\w*\b",
        ],
    }

    def __init__(
        self,
        patterns: dict[str, list[str]] | None = None,
        case_sensitive: bool = False,
        threshold: int = 1,
    ):
        """
        Initialize regex safety plugin.

        Args:
            patterns: Dict mapping category names to regex patterns
            case_sensitive: Whether pattern matching is case-sensitive
            threshold: Minimum number of matches to flag as unsafe
        """
        self.patterns = patterns or self.DEFAULT_PATTERNS
        self.case_sensitive = case_sensitive
        self.threshold = threshold

        # Compile patterns
        flags = 0 if case_sensitive else re.IGNORECASE
        self.compiled_patterns: dict[str, list[re.Pattern]] = {}

        for category, pattern_list in self.patterns.items():
            self.compiled_patterns[category] = [re.compile(p, flags) for p in pattern_list]

    async def check_safety(self, text: str, context: str | None = None) -> SafetyResult:
        """Check text safety using regex patterns."""
        # Check all patterns
        matches: dict[str, int] = {}
        total_matches = 0

        for category, patterns in self.compiled_patterns.items():
            category_matches = 0
            for pattern in patterns:
                category_matches += len(pattern.findall(text))

            if category_matches > 0:
                matches[category] = category_matches
                total_matches += category_matches

        # Determine if safe
        is_safe = total_matches < self.threshold
        flagged_categories = list(matches.keys())

        # Build explanation
        if flagged_categories:
            details = ", ".join([f"{cat} ({count} matches)" for cat, count in matches.items()])
            explanation = f"Flagged categories: {details}"
        else:
            explanation = "No unsafe patterns detected"

        # Calculate confidence (simple heuristic)
        if is_safe:
            confidence = 0.9  # High confidence when safe
        else:
            # Lower confidence with more matches
            confidence = min(0.9, 0.5 + (total_matches * 0.1))

        return SafetyResult(
            is_safe=is_safe,
            confidence=confidence,
            categories=flagged_categories,
            explanation=explanation,
            sanitized_text=None,
            metadata={"match_details": matches, "total_matches": total_matches},
        )

    async def check_health(self) -> bool:
        """Health check (regex always available)."""
        return True

    @property
    def model_name(self) -> str:
        """Return model identifier."""
        return "simple-regex-v1"
