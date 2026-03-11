"""
Prompt templates for the Validator Agent.

Coach Simple explains:
    "We tell Claude: 'You're a senior engineer reviewing a shopping list.
    Does this list make sense for a 2-story house? Did we forget anything?
    Are any quantities suspiciously high or low?' Claude catches things
    that simple math checks can't."
"""

from __future__ import annotations

import json
from typing import Any


VALIDATOR_SYSTEM_PROMPT = """\
You are a senior quantity surveyor reviewing a Bill of Quantities (BOQ) for a \
construction project. Perform an intelligent review and identify issues that \
simple arithmetic checks cannot catch.

Review these aspects:
1. COMPLETENESS: Are any material categories missing for this building type? \
   (e.g., a building with columns but no beams is suspicious, a ground slab \
   without waterproofing is a concern)
2. CONSISTENCY: Do material ratios make sense? \
   (e.g., plaster area should roughly match wall area, formwork should match \
   concrete contact surfaces)
3. REASONABLENESS: Are quantities reasonable for a building of this size? \
   (e.g., steel ratio 50-200 kg/m3 concrete, concrete 0.1-1.5 m3/m2 floor area)
4. CONSTRUCTION LOGIC: Does the material combination make construction sense? \
   (e.g., timber frame with concrete columns is contradictory)
5. MISSING ITEMS: Are typical items missing? \
   (e.g., no foundation for multi-storey, no insulation for external walls, \
   no waterproofing for basement, no handrails for stairs)

IMPORTANT CONTEXT:
- You are reviewing ONLY the materials derived from elements in the IFC model.
- If the IFC model does not include certain elements (stairs, MEP, foundations, \
  site works), that is NOT an error - it simply means those items were not \
  modeled. Flag them as "info" at most.
- Only flag issues with the materials that ARE present in the BOQ.

Severity levels:
- error: Contradictory or impossible data (e.g., negative quantity, steel but \
  no concrete, plaster area 10x wall area). Use VERY sparingly.
- warning: Unusual ratios or quantities that are worth double-checking \
  (e.g., steel ratio outside 50-200 kg/m3, missing insulation on external walls)
- info: Observations, missing scope items, or suggestions for improvement \
  (e.g., no MEP in model, no site works, no finishes)

Respond with a JSON object with this structure:
{{
  "overall_assessment": "REASONABLE" | "CONCERNS" | "SIGNIFICANT_ISSUES",
  "confidence": 0.0 to 1.0,
  "issues": [
    {{
      "severity": "error" | "warning" | "info",
      "category": "completeness" | "consistency" | "reasonableness" | "construction_logic" | "missing_items",
      "message": "Description of the issue",
      "suggestion": "What to do about it"
    }}
  ],
  "summary": "2-3 sentence overall assessment"
}}"""


def build_validator_message(
    elements: list[dict[str, Any]],
    materials: list[dict[str, Any]],
    building_info: dict[str, Any] | None,
    boq_data: dict[str, Any] | None,
    calc_quantities: list[dict[str, Any]] | None = None,
) -> str:
    """Build the user message for the validator prompt.

    Provides a summary view of the entire project rather than raw data,
    to keep token count manageable.
    """
    # Element type counts
    type_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for e in elements:
        t = e.get("ifc_type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
        c = e.get("category", "uncategorized")
        category_counts[c] = category_counts.get(c, 0) + 1

    # Material summary (compact)
    mat_summary = []
    for m in materials:
        mat_summary.append({
            "description": m["description"],
            "unit": m["unit"],
            "quantity": m.get("quantity", 0),
            "total_quantity": m.get("total_quantity", 0),
            "waste_factor": m.get("waste_factor", 0),
        })

    # Key ratios
    total_concrete = sum(
        m.get("total_quantity", 0)
        for m in materials
        if "concrete" in m["description"].lower() and m["unit"] == "m3"
    )
    total_steel = sum(
        m.get("total_quantity", 0)
        for m in materials
        if "reinforcement" in m["description"].lower() and m["unit"] == "kg"
    )
    total_floor_area = 0
    if calc_quantities:
        total_floor_area = sum(
            q["quantity"]
            for cq in calc_quantities
            for q in cq.get("quantities", [])
            if "slab area (top" in q.get("description", "").lower()
        )

    data: dict[str, Any] = {
        "building": {
            "name": building_info.get("building_name") or building_info.get("project_name", "Unknown") if building_info else "Unknown",
            "storeys": building_info.get("storeys", []) if building_info else [],
            "element_types": type_counts,
            "element_categories": category_counts,
            "total_elements": len(elements),
        },
        "materials": mat_summary,
        "key_ratios": {
            "total_concrete_m3": round(total_concrete, 2),
            "total_steel_kg": round(total_steel, 2),
            "total_floor_area_m2": round(total_floor_area, 2),
            "concrete_per_floor_area": round(total_concrete / total_floor_area, 2) if total_floor_area > 0 else None,
            "steel_per_concrete_kg_m3": round(total_steel / total_concrete, 1) if total_concrete > 0 else None,
        },
    }

    if boq_data:
        data["boq_summary"] = {
            "total_sections": boq_data.get("total_sections", 0),
            "total_line_items": boq_data.get("total_line_items", 0),
            "section_titles": [s["title"] for s in boq_data.get("sections", [])],
        }

    return json.dumps(data, indent=2)
