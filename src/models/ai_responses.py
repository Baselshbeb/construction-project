"""
Pydantic models for validating AI (Claude) responses.

Each agent that calls the LLM expects a specific JSON structure back.
These models enforce that structure so malformed AI responses are caught
early instead of silently corrupting downstream data.

Usage:
    from src.models.ai_responses import ClassifierResponse
    validated = ClassifierResponse.model_validate(raw_dict)
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Classifier Agent response
# ---------------------------------------------------------------------------

class ClassifierResponse(BaseModel):
    """Validated classifier output: mapping of element ID -> category.

    The raw AI response is a flat dict like {"123": "external_walls", ...}.
    We wrap it so we can validate every key/value pair.
    """

    classifications: dict[str, str]

    @field_validator("classifications")
    @classmethod
    def validate_categories(cls, v: dict[str, str]) -> dict[str, str]:
        from src.models.project import ElementCategory
        valid = {cat.value for cat in ElementCategory}
        cleaned: dict[str, str] = {}
        for elem_id, category in v.items():
            if category in valid:
                cleaned[str(elem_id)] = category
            # silently skip invalid categories — caller will track them as unclassified
        return cleaned

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> ClassifierResponse:
        """Build from the raw AI dict (flat elem_id->category mapping)."""
        # The AI returns a flat dict, not wrapped in "classifications"
        return cls(classifications={str(k): v for k, v in raw.items()})


# ---------------------------------------------------------------------------
# Material Mapper Agent response
# ---------------------------------------------------------------------------

class MaterialRule(BaseModel):
    """A single material rule returned by the AI for one element."""

    name: str = Field(description="Material name, e.g. 'Concrete C25/30'")
    unit: str = Field(description="Unit: m2, m3, m, kg, nr, set, litre")
    source: str = Field(default="", description="Source quantity description to look up")
    multiplier: float = Field(default=1.0, description="Factor to apply to source quantity")
    waste_key: Optional[str] = Field(default=None, description="Waste factor lookup key")
    waste: Optional[str] = Field(default=None, description="Alternative waste key field")
    waste_value: Optional[float] = Field(default=None, description="Direct waste factor decimal")
    note: Optional[str] = Field(default=None, description="Brief explanation")

    @field_validator("multiplier", mode="before")
    @classmethod
    def coerce_multiplier(cls, v: Any) -> float:
        """Handle AI returning multiplier as string like '5x' or '80'."""
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            cleaned = v.strip().lower().rstrip("x")
            try:
                return float(cleaned)
            except ValueError:
                return 1.0
        return 1.0


class ElementMaterialResult(BaseModel):
    """AI response for one element's materials."""

    element_id: int | str = Field(description="The IFC element ID")
    materials: list[MaterialRule] = Field(default_factory=list)

    @field_validator("element_id", mode="before")
    @classmethod
    def coerce_element_id(cls, v: Any) -> int:
        """Normalize element_id to int."""
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return -1
        return -1


class MapperResponse(BaseModel):
    """Validated material mapper output."""

    elements: list[ElementMaterialResult] = Field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> MapperResponse:
        """Build from the raw AI dict."""
        if "elements" in raw and isinstance(raw["elements"], list):
            return cls.model_validate(raw)
        # If AI returned something else, wrap empty
        return cls(elements=[])


# ---------------------------------------------------------------------------
# Validator Agent response
# ---------------------------------------------------------------------------

class ValidationIssue(BaseModel):
    """A single issue found by the AI validator."""

    severity: str = Field(description="error, warning, or info")
    category: str = Field(default="general")
    message: str = Field(default="")
    suggestion: Optional[str] = None

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        allowed = {"error", "warning", "info"}
        v_lower = v.lower().strip()
        return v_lower if v_lower in allowed else "info"


class ValidatorResponse(BaseModel):
    """Validated AI validator output."""

    overall_assessment: str = Field(default="REASONABLE")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    issues: list[ValidationIssue] = Field(default_factory=list)
    summary: Optional[str] = None

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: Any) -> float:
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (TypeError, ValueError):
            return 0.5

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> ValidatorResponse:
        """Build from the raw AI dict, tolerating missing fields."""
        return cls.model_validate(raw)
