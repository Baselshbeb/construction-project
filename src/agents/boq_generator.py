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
from src.models.project import ElementCategory, ProcessingStatus


# Section ordering and display names
SECTION_CONFIG = [
    (ElementCategory.SUBSTRUCTURE, "Substructure"),
    (ElementCategory.FRAME, "Structural Frame (Columns & Beams)"),
    (ElementCategory.EXTERNAL_WALLS, "External Walls"),
    (ElementCategory.INTERNAL_WALLS, "Internal Walls & Partitions"),
    (ElementCategory.UPPER_FLOORS, "Upper Floor Slabs"),
    (ElementCategory.ROOF, "Roof"),
    (ElementCategory.DOORS, "Doors"),
    (ElementCategory.WINDOWS, "Windows"),
    (ElementCategory.STAIRS, "Stairs & Ramps"),
    (ElementCategory.FINISHES, "Finishes"),
    (ElementCategory.MEP, "Mechanical, Electrical & Plumbing"),
    (ElementCategory.EXTERNAL_WORKS, "External Works"),
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
        for category_enum, title in SECTION_CONFIG:
            cat_key = category_enum.value
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
                    "quantity": mat["total_quantity"],
                    "rate": None,
                    "amount": None,
                    "category": cat_key,
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
                    "quantity": mat["total_quantity"],
                    "rate": None,
                    "amount": None,
                    "category": "other",
                })
            sections.append({
                "section_no": section_no,
                "title": "Other Items",
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

        boq_data = {
            "project_name": project_name,
            "building_name": building_name,
            "prepared_by": "Metraj AI System",
            "sections": sections,
            "total_line_items": sum(len(s["items"]) for s in sections),
            "total_sections": len(sections),
            "grand_total": None,
        }

        state["boq_data"] = boq_data

        self.log(
            f"BOQ generated: {boq_data['total_sections']} sections, "
            f"{boq_data['total_line_items']} line items"
        )
        state["processing_log"].append(
            f"BOQ Generator: {boq_data['total_sections']} sections, "
            f"{boq_data['total_line_items']} line items"
        )

        return state
