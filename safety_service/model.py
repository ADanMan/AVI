"""Simple heuristic model that simulates a Llama Guard/Qwen safety classifier."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SafetyJudgement:
    """Structured result returned by the safety model."""

    safe: bool
    score: float
    reasons: Sequence[str]
    sanitized_text: str


class LlamaGuardHeuristic:
    """A lightweight rule-based guardrail inspired by Llama Guard/Qwen safety policies."""

    DEFAULT_BLOCKLIST = ("hate", "violence", "attack", "bomb", "kill", "weapon", "drug", "terror")

    def __init__(self, blocklist: Iterable[str] | None = None):
        self.blocklist = tuple(
            sorted({term.strip().lower() for term in (blocklist or self.DEFAULT_BLOCKLIST)})
        )
        self.pattern = re.compile(
            r"|".join(re.escape(term) for term in self.blocklist), re.IGNORECASE
        )

    @classmethod
    def from_file(cls, path: str | None) -> LlamaGuardHeuristic:
        """Load blocklist terms from a file if provided."""

        if not path:
            return cls()
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Blocklist file '{path}' does not exist")
        content = file_path.read_text(encoding="utf-8")
        terms: list[str] = []
        for chunk in re.split(r"[\r\n,;]+", content):
            candidate = chunk.strip()
            if candidate:
                terms.append(candidate)
        return cls(terms or None)

    def evaluate(self, text: str) -> SafetyJudgement:
        """Return a simple safety evaluation for *text*."""

        if not text:
            return SafetyJudgement(True, 1.0, (), "")

        matches = [match.group(0).lower() for match in self.pattern.finditer(text)]
        safe = not matches
        reasons: list[str] = []
        score = 1.0 if safe else max(0.0, 1.0 - 0.1 * len(matches))
        sanitized = text
        if not safe:
            reasons.append(
                "Detected sensitive terms associated with violence/abuse: "
                + ", ".join(sorted(set(matches)))
            )
            sanitized = self.pattern.sub("[redacted]", text)
        return SafetyJudgement(
            safe=safe, score=score, reasons=tuple(reasons), sanitized_text=sanitized
        )


__all__ = ["LlamaGuardHeuristic", "SafetyJudgement"]
