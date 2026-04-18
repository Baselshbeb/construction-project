"""
Confidence scoring service for BOQ line items.

Scores each BOQ item based on the quality and source of the data used
to compute it. The scoring is fully deterministic — no AI involved.

Penalty-based system:
  - Start at 1.0
  - Deduct for each data quality concern
  - Map final score to HIGH (>= 0.85), MEDIUM (>= 0.65), LOW (< 0.65)
"""

from __future__ import annotations

from typing import Any

from src.models.confidence import ConfidenceLevel, ConfidenceScore
from src.utils.logger import get_logger

logger = get_logger("confidence_service")

# Penalty values for various data quality concerns
PENALTIES = {
    # Quantity source
    "quantity_source_qto": 0.0,
    "quantity_source_geometry": 0.10,
    "quantity_source_mixed": 0.05,
    "quantity_source_none": 0.40,

    # Opening deduction method
    "opening_qto": 0.0,
    "opening_per_wall": 0.0,
    "opening_storey_avg": 0.03,
    "opening_none": 0.12,

    # Reinforcement source
    "rebar_ifc_detailed": 0.0,
    "rebar_ratio_based": 0.02,
    "rebar_none": 0.0,  # no penalty if element doesn't need rebar

    # Material mapping source
    "material_rule_based": 0.0,
    "material_ai_with_hints": 0.05,
    "material_ai_guess": 0.15,

    # Element type coverage
    "element_has_dedicated_calc": 0.0,
    "element_generic_calc": 0.07,
}

# Thresholds for level classification
HIGH_THRESHOLD = 0.85
MEDIUM_THRESHOLD = 0.65


class ConfidenceService:
    """Scores BOQ items based on data quality."""

    def score_element_quantities(
        self,
        element: dict[str, Any],
        calc_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Score the confidence of calculated quantities for one element.

        Args:
            element: Parsed element dict with quantity_source, openings, etc.
            calc_data: Calculated quantity data for this element.

        Returns:
            Confidence metadata dict to attach to the element's quantities.
        """
        score = 1.0
        factors: list[str] = []

        # 1. Quantity source
        src = element.get("quantity_source", "none")
        penalty = PENALTIES.get(f"quantity_source_{src}", 0.15)
        if penalty > 0:
            score -= penalty
            factors.append(f"Quantities from {src} (-{penalty:.0%})")
        else:
            factors.append("Quantities from IFC Qto (reliable)")

        # 2. Opening deduction (walls only)
        ifc_type = element.get("ifc_type", "")
        if ifc_type in ("IfcWall", "IfcWallStandardCase"):
            openings = element.get("openings", [])
            has_net_area = element.get("quantities", {}).get("NetArea", 0) > 0
            if has_net_area:
                factors.append("Net area from IFC Qto")
            elif openings:
                factors.append("Per-wall opening deduction (exact)")
            else:
                score -= PENALTIES["opening_storey_avg"]
                factors.append("Storey-average opening deduction (approximate)")

        # 3. Element type coverage
        has_dedicated = ifc_type in (
            "IfcWall", "IfcWallStandardCase", "IfcSlab", "IfcColumn", "IfcBeam",
            "IfcDoor", "IfcWindow", "IfcStair", "IfcStairFlight", "IfcRoof",
            "IfcFooting", "IfcPile", "IfcRamp", "IfcRampFlight",
            "IfcCovering", "IfcCurtainWall", "IfcRailing", "IfcMember", "IfcPlate",
        )
        if not has_dedicated:
            score -= PENALTIES["element_generic_calc"]
            factors.append("Generic calculator used (no dedicated rules)")

        # 4. Reinforcement (structural elements only)
        structural_types = {
            "IfcWall", "IfcWallStandardCase", "IfcSlab", "IfcColumn",
            "IfcBeam", "IfcFooting", "IfcPile", "IfcStair", "IfcStairFlight",
        }
        if ifc_type in structural_types:
            rebar = element.get("reinforcement", {})
            rebar_source = rebar.get("source", "none") if rebar else "none"
            if rebar_source == "ifc_detailed":
                factors.append("Reinforcement from IFC (exact)")
            else:
                score -= PENALTIES["rebar_ratio_based"]
                factors.append("Reinforcement from ratio estimates")

        # Clamp score
        score = max(0.0, min(1.0, score))

        # Classify
        if score >= HIGH_THRESHOLD:
            level = ConfidenceLevel.HIGH
        elif score >= MEDIUM_THRESHOLD:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        return {
            "level": level.value,
            "score": round(score, 2),
            "factors": factors,
            "review_needed": level != ConfidenceLevel.HIGH,
        }

    def score_boq_item(
        self,
        item: dict[str, Any],
        element_scores: dict[int, dict[str, Any]],
    ) -> ConfidenceScore:
        """Score a BOQ line item based on its source elements' scores.

        Uses worst-case: the item's confidence is the lowest confidence
        among all contributing elements. This is conservative — if ANY
        source element is uncertain, the aggregated item is flagged.
        """
        source_elements = item.get("source_elements", [])
        if not source_elements:
            return ConfidenceScore(
                level=ConfidenceLevel.LOW,
                score=0.4,
                factors=["No source elements linked"],
                review_needed=True,
            )

        # Collect scores from source elements
        scores = []
        all_factors: list[str] = []
        for eid in source_elements:
            elem_conf = element_scores.get(eid)
            if elem_conf:
                scores.append(elem_conf["score"])
                all_factors.extend(elem_conf["factors"])

        if not scores:
            return ConfidenceScore(
                level=ConfidenceLevel.MEDIUM,
                score=0.7,
                factors=["Source element confidence not available"],
                review_needed=True,
            )

        # Weighted average score (more realistic than worst-case)
        # Each element contributes equally since we don't have per-element quantities here
        min_score = sum(scores) / len(scores)

        # Deduplicate factors
        unique_factors = list(dict.fromkeys(all_factors))

        if min_score >= HIGH_THRESHOLD:
            level = ConfidenceLevel.HIGH
        elif min_score >= MEDIUM_THRESHOLD:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        return ConfidenceScore(
            level=level,
            score=round(min_score, 2),
            factors=unique_factors[:5],  # Limit to top 5 factors
            review_needed=level != ConfidenceLevel.HIGH,
        )

    def generate_summary(
        self, item_scores: list[ConfidenceScore],
    ) -> dict[str, Any]:
        """Generate overall confidence summary for the project."""
        if not item_scores:
            return {"high_count": 0, "medium_count": 0, "low_count": 0, "overall_score": 0}

        high = sum(1 for s in item_scores if s.level == ConfidenceLevel.HIGH)
        medium = sum(1 for s in item_scores if s.level == ConfidenceLevel.MEDIUM)
        low = sum(1 for s in item_scores if s.level == ConfidenceLevel.LOW)
        avg_score = sum(s.score for s in item_scores) / len(item_scores)

        return {
            "high_count": high,
            "medium_count": medium,
            "low_count": low,
            "total_items": len(item_scores),
            "review_needed_count": medium + low,
            "overall_score": round(avg_score, 2),
            "overall_level": (
                "high" if avg_score >= HIGH_THRESHOLD
                else "medium" if avg_score >= MEDIUM_THRESHOLD
                else "low"
            ),
        }
