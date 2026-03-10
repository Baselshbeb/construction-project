"""
Material Mapper Agent - maps building elements to construction materials using
Claude AI.

Coach Simple explains:
    "We know we have a concrete external wall with 30 m2 of area and 6 m3
    of volume. But WHAT materials do we need to BUILD it? We ask Claude -
    who knows construction engineering deeply - to figure out the shopping
    list: concrete, steel, formwork, plaster, paint... Claude handles ANY
    building type, not just the simple ones our rules cover."

Pipeline position: FOURTH agent (after Calculator)
Input: ProjectState with calculated_quantities
Output: ProjectState with material_list filled in
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.project import ProcessingStatus
from src.prompts.material_mapper_prompts import (
    build_mapper_message,
    get_mapper_system_prompt,
)
from src.services.llm_service import LLMService
from src.utils.logger import get_logger

logger = get_logger("material_mapper")

DATA_DIR = Path(__file__).parent.parent / "data"


def _load_json(filename: str) -> dict:
    path = DATA_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    logger.warning(f"Data file not found: {path}")
    return {}


class MaterialMapperAgent(BaseAgent):
    """Maps building elements to construction materials using AI."""

    def __init__(self, llm_service: LLMService | None = None):
        super().__init__(
            name="material_mapper",
            description="Maps element quantities to specific construction materials using AI",
        )
        self.llm = llm_service or LLMService()
        self.waste_factors = _load_json("waste_factors.json")
        self.element_rules = _load_json("element_rules.json")

        # Build the system prompt with reference data injected
        self.system_prompt = get_mapper_system_prompt(
            self.waste_factors, self.element_rules
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Map all elements to their required materials using AI."""
        self.log("Starting AI material mapping...")
        state["status"] = ProcessingStatus.MAPPING_MATERIALS
        state["current_step"] = "Mapping materials"

        elements = state.get("parsed_elements", [])
        calc_quantities = state.get("calculated_quantities", [])

        if not elements or not calc_quantities:
            self.log_warning("No elements or quantities to map!")
            return state

        # Build lookup: element_id -> calculated quantities
        qty_lookup: dict[int, list[dict]] = {}
        for cq in calc_quantities:
            qty_lookup[cq["element_id"]] = cq["quantities"]

        # Group elements by IFC type for batching
        batches = self._group_by_type(elements)

        all_materials: list[dict[str, Any]] = []
        total_batches = len(batches)

        for i, (type_name, batch_elements) in enumerate(batches.items()):
            self.log(f"  Mapping batch {i + 1}/{total_batches}: {type_name} ({len(batch_elements)} elements)")

            # Build enriched element data with quantities attached
            enriched = []
            for elem in batch_elements:
                enriched.append({
                    "element_id": elem["ifc_id"],
                    "ifc_type": elem["ifc_type"],
                    "name": elem.get("name"),
                    "is_external": elem.get("is_external"),
                    "category": elem.get("category"),
                    "ifc_materials": elem.get("materials", []),
                    "quantities": qty_lookup.get(elem["ifc_id"], []),
                })

            user_message = build_mapper_message(enriched)

            try:
                ai_result = await self.llm.ask_json(
                    system_prompt=self.system_prompt,
                    user_message=user_message,
                    temperature=0.0,
                    max_tokens=8192,
                )
            except Exception as e:
                self.log_error(f"AI mapping failed for {type_name}: {e}")
                state["warnings"].append(
                    f"AI material mapping failed for {type_name}: {e}"
                )
                continue

            # Process AI response
            for elem_result in ai_result.get("elements", []):
                materials = self._process_ai_materials(
                    elem_result, qty_lookup, elements
                )
                all_materials.extend(materials)

        # Aggregate same materials across all elements
        aggregated = self._aggregate_materials(all_materials)

        state["material_list"] = aggregated

        self.log(
            f"AI mapped {len(all_materials)} material items, "
            f"aggregated to {len(aggregated)} unique materials"
        )
        state["processing_log"].append(
            f"Material Mapper: AI mapped {len(elements)} elements "
            f"to {len(aggregated)} unique materials"
        )

        return state

    def _group_by_type(
        self, elements: list[dict[str, Any]]
    ) -> dict[str, list[dict]]:
        """Group elements by IFC type for batch API calls."""
        groups: dict[str, list[dict]] = defaultdict(list)
        for elem in elements:
            groups[elem.get("ifc_type", "Unknown")].append(elem)
        return dict(groups)

    def _process_ai_materials(
        self,
        elem_result: dict[str, Any],
        qty_lookup: dict[int, list[dict]],
        all_elements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert AI response for one element into material dicts."""
        elem_id = elem_result.get("element_id")
        if elem_id is None:
            return []

        # Find the element to get its category
        element = None
        for e in all_elements:
            if e["ifc_id"] == elem_id:
                element = e
                break
        if not element:
            return []

        # Build quantity lookup for this element
        quantities = qty_lookup.get(elem_id, [])
        qty_map: dict[str, float] = {}
        for q in quantities:
            qty_map[q["description"]] = q["quantity"]

        result = []
        for mat_rule in elem_result.get("materials", []):
            material = self._apply_material_rule(mat_rule, qty_map, element)
            if material:
                result.append(material)

        return result

    def _apply_material_rule(
        self,
        rule: dict,
        qty_lookup: dict[str, float],
        element: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Apply a single material rule from AI response to produce a material item."""
        name = rule.get("name", "Unknown material")
        unit = rule.get("unit", "nr")
        source_desc = rule.get("source", "")
        multiplier = rule.get("multiplier", 1.0)

        # Get the source quantity
        source_qty = qty_lookup.get(source_desc, 0)

        # Try partial matching if exact match fails
        if source_qty == 0 and source_desc:
            source_lower = source_desc.lower()
            for desc, val in qty_lookup.items():
                if source_lower in desc.lower() or desc.lower() in source_lower:
                    source_qty = val
                    break

        if source_qty == 0:
            return None

        # Calculate base quantity
        base_quantity = source_qty * multiplier

        # Get waste factor
        waste = 0.0
        if "waste_key" in rule:
            waste = self._get_waste_factor(rule["waste_key"])
        elif "waste" in rule:
            waste = self._get_waste_factor(rule["waste"])
        elif "waste_value" in rule:
            waste = rule["waste_value"]

        total_quantity = round(base_quantity * (1 + waste), 3)

        return {
            "description": name,
            "unit": unit,
            "quantity": round(base_quantity, 3),
            "waste_factor": waste,
            "total_quantity": total_quantity,
            "category": element.get("category"),
            "source_elements": [element["ifc_id"]],
            "notes": rule.get("note"),
        }

    def _get_waste_factor(self, waste_key: str) -> float:
        """Look up a waste factor from waste_factors.json data.

        waste_key format: "concrete.standard" -> waste_factors["concrete"]["standard"]
        """
        parts = waste_key.split(".")
        if len(parts) != 2:
            return 0.05  # default 5%

        category, level = parts
        cat_data = self.waste_factors.get(category, {})
        if isinstance(cat_data, dict):
            return cat_data.get(level, 0.05)
        return 0.05

    def _aggregate_materials(
        self, materials: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Combine same materials across all elements.

        E.g., if 8 walls each need 'Concrete C25/30', sum them into one entry.
        """
        aggregated: dict[str, dict[str, Any]] = {}

        for mat in materials:
            key = f"{mat['description']}|{mat['unit']}"
            if key not in aggregated:
                aggregated[key] = {
                    "description": mat["description"],
                    "unit": mat["unit"],
                    "quantity": 0,
                    "total_quantity": 0,
                    "waste_factor": mat["waste_factor"],
                    "category": mat["category"],
                    "source_elements": [],
                    "notes": mat.get("notes"),
                }
            aggregated[key]["quantity"] += mat["quantity"]
            aggregated[key]["total_quantity"] += mat["total_quantity"]
            aggregated[key]["source_elements"].extend(mat["source_elements"])

        # Round final values
        result = []
        for item in aggregated.values():
            item["quantity"] = round(item["quantity"], 2)
            item["total_quantity"] = round(item["total_quantity"], 2)
            # Deduplicate source elements
            item["source_elements"] = list(set(item["source_elements"]))
            result.append(item)

        # Sort by category then description
        result.sort(key=lambda x: (x.get("category") or "", x["description"]))
        return result
