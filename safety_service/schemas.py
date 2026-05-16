"""Pydantic models exposed by the safety microservice."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SafetyRequest(BaseModel):
    text: str = Field(..., description="Text to evaluate")
    context: str | None = Field(None, description="Optional conversational context")


class SafetyResponse(BaseModel):
    safe: bool = Field(..., description="Whether the input is considered safe")
    score: float = Field(..., description="Confidence score in range [0, 1]")
    reasons: list[str] = Field(default_factory=list, description="List of violation descriptions")
    sanitized_text: str = Field(..., description="Sanitized version of the text")
    model: str = Field(..., description="Model identifier")
    evaluated_at: datetime = Field(..., description="Timestamp of evaluation")


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Human readable health status")


__all__ = ["HealthResponse", "SafetyRequest", "SafetyResponse"]
