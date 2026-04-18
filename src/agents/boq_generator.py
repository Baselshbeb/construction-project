"""
BOQ Generator Agent - assembles the Bill of Quantities from material data.

Coach Simple explains:
    "We have the shopping list. Now we need to make it look professional -
    organized into sections with item numbers, descriptions, units,
    quantities, and totals. Like turning messy notes into a clean spreadsheet."

Pipeline position: FIFTH agent (after Material Mapper, before Validator)
Input: ProjectState with material_list and building_info
Output: ProjectState with boq_data filled in
"""

from __future__ import annotations

from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.confidence import ConfidenceScore
from src.models.project import ElementCategory, ProcessingStatus
from src.services.confidence_service import ConfidenceService
from src.translations.strings import get_boq_sections


# Section ordering (category enums in display order)
SECTION_ORDER = [
    ElementCategory.SUBSTRUCTURE,
    ElementCategory.FRAME,
    ElementCategory.EXTERNAL_WALLS,
    ElementCategory.INTERNAL_WALLS,
    ElementCategory.UPPER_FLOORS,
    ElementCategory.ROOF,
    ElementCategory.DOORS,
    ElementCategory.WINDOWS,
    ElementCategory.STAIRS,
    ElementCategory.FINISHES,
    ElementCategory.MEP,
    ElementCategory.EXTERNAL_WORKS,
]


class BOQGeneratorAgent(BaseAgent):
    """Assembles a structured Bill of Quantities from material data."""

    def __init__(self):
        super().__init__(
            name="boq_generator",
            description="Assembles structured BOQ from material list",
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Generate the BOQ data structure."""
        self.log("Generating Bill of Quantities...")
        state["status"] = ProcessingStatus.GENERATING_BOQ
        state["current_step"] = "Generating BOQ"

        language = state.get("language", "en")
        section_titles = get_boq_sections(language)

        materials = state.get("material_list", [])
        building_info = state.get("building_info", {})

        if not materials:
            self.log_warning("No materials to generate BOQ from!")
            return state

        # Group materials by category
        by_category: dict[str, list[dict]] = {}
        uncategorized: list[dict] = []
        for mat in materials:
            cat = mat.get("category")
            if cat:
                by_category.setdefault(cat, []).append(mat)
            else:
                uncategorized.append(mat)

        # Build BOQ sections
        sections = []
        section_no = 0
        for category_enum in SECTION_ORDER:
            cat_key = category_enum.value
            title = section_titles.get(cat_key, cat_key)
            cat_materials = by_category.get(cat_key, [])
            if not cat_materials:
                continue

            section_no += 1
            items = []
            for i, mat in enumerate(cat_materials, 1):
                items.append({
                    "item_no": f"{section_no}.{i:02d}",
                    "description": mat["description"],
                    "unit": mat["unit"],
                    "quantity": round(mat["total_quantity"], 3),
                    "base_quantity": round(mat.get("quantity", mat["total_quantity"]), 3),
                    "waste_factor": mat.get("waste_factor", 0),
                    "rate": None,
                    "amount": None,
                    "category": cat_key,
                    "source_elements": mat.get("source_elements", []),
                    "element_count": len(mat.get("source_elements", [])),
                })

            sections.append({
                "section_no": section_no,
                "title": title,
                "category": cat_key,
                "items": items,
                "subtotal": None,
            })

        # Handle uncategorized materials
        if uncategorized:
            section_no += 1
            items = []
            for i, mat in enumerate(uncategorized, 1):
                items.append({
                    "item_no": f"{section_no}.{i:02d}",
                    "description": mat["description"],
                    "unit": mat["unit"],
                    "quantity": round(mat["total_quantity"], 3),
                    "base_quantity": round(mat.get("quantity", mat["total_quantity"]), 3),
                    "waste_factor": mat.get("waste_factor", 0),
                    "rate": None,
                    "amount": None,
                    "category": "other",
                    "source_elements": mat.get("source_elements", []),
                    "element_count": len(mat.get("source_elements", [])),
                })
            sections.append({
                "section_no": section_no,
                "title": section_titles.get("other", "Other Items"),
                "category": "other",
                "items": items,
                "subtotal": None,
            })

        # Build report data
        project_name = "Untitled Project"
        building_name = None
        if isinstance(building_info, dict):
            project_name = building_info.get("project_name") or project_name
            building_name = building_info.get("building_name")

        # --- Confidence scoring ---
        confidence_svc = ConfidenceService()
        elements = state.get("parsed_elements", [])

        # Score each source element
        element_scores: dict[int, dict] = {}
        for elem in elements:
            calc_data = {}  # Calculator data not needed for element-level scoring
            elem_score = confidence_svc.score_element_quantities(elem, calc_data)
            element_scores[elem["ifc_id"]] = elem_score

        # Score each BOQ line item and collect scores for summary
        all_item_scores: list[ConfidenceScore] = []
        for section in sections:
            for item in section.get("items", []):
                item_confidence = confidence_svc.score_boq_item(item, element_scores)
                item["confidence"] = item_confidence.model_dump()
                all_item_scores.append(item_confidence)

        confidence_summary = confidence_svc.generate_summary(all_item_scores)
        self.log(
            f"Confidence: {confidence_summary['high_count']} HIGH, "
            f"{confidence_summary['medium_count']} MEDIUM, "
            f"{confidence_summary['low_count']} LOW "
            f"(overall: {confidence_summary['overall_score']:.0%})"
        )

        boq_data = {
            "project_name": project_name,
            "building_name": building_name,
            "prepared_by": "Metraj AI System",
            "sections": sections,
            "total_line_items": sum(len(s["items"]) for s in sections),
            "total_sections": len(sections),
            "grand_total": None,
            "confidence_summary": confidence_summary,
        }

        state["boq_data"] = boq_data

        self.log(
            f"BOQ generated: {boq_data['total_sections']} sections, "
            f"{boq_data['total_line_items']} line items"
        )
        state["processing_log"].append(
            f"BOQ Generator: {boq_data['total_sections']} sections, "
            f"{boq_data['total_line_items']} line items, "
            f"confidence: {confidence_summary['overall_level']}"
        )

        return state
