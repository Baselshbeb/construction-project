"""
Confidence scoring models for BOQ line items.

Each BOQ item gets a confidence score (HIGH/MEDIUM/LOW) based on the
data sources used to compute it. This allows users to focus review
effort on uncertain items instead of checking everything.

Scoring is deterministic (not AI-based) — it reflects the quality of
the input data, not a subjective assessment.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    """Confidence levels for BOQ quantities."""

    HIGH = "high"       # 85%+ score: Qto data present, exact openings, IFC rebar
    MEDIUM = "medium"   # 65-84%: geometry fallback, storey-avg openings, ratio rebar
    LOW = "low"         # <65%: no quantities, AI-guessed materials, generic rules


class ConfidenceScore(BaseModel):
    """Confidence assessment for a single BOQ line item."""

    level: ConfidenceLevel = Field(description="HIGH, MEDIUM, or LOW")
    score: float = Field(ge=0.0, le=1.0, description="Numeric score 0.0 to 1.0")
    factors: list[str] = Field(
        default_factory=list,
        description="Human-readable reasons for the score",
    )
    review_needed: bool = Field(
        default=False,
        description="True if a human should verify this item",
    )

    model_config = {"frozen": False}
