"""
Material Mapper Agent - maps building elements to specific construction materials.

Coach Simple explains:
    "We know we have a concrete external wall with 30 m2 of area and 6 m3
    of volume. But WHAT materials do we need to BUILD it? This agent figures
    that out: 6.3 m3 concrete, 504 kg steel, 63 m2 formwork, 30 m2 plaster,
    30 m2 paint... It's the brain that turns measurements into a shopping list."

This agent uses RULE-BASED mapping from element_rules.json for standard cases.
For complex/ambiguous elements, it can fall back to AI (Claude API).

Pipeline position: FOURTH agent (after Calculator)
Input: ProjectState with calculated_quantities
Output: ProjectState with material_list filled in
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.project import ProcessingStatus
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
    """Maps building elements to construction materials using rules + AI."""

    def __init__(self):
        super().__init__(
            name="material_mapper",
            description="Maps element quantities to specific construction materials",
        )
        self.waste_factors = _load_json("waste_factors.json")
        self.element_rules = _load_json("element_rules.json")

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Map all elements to their required materials."""
        self.log("Starting material mapping...")
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

        # Map each element to materials
        all_materials: list[dict[str, Any]] = []

        for element in elements:
            elem_id = element["ifc_id"]
            elem_quantities = qty_lookup.get(elem_id, [])

            materials = self._map_element(element, elem_quantities)
            all_materials.extend(materials)

        # Aggregate: combine same materials across all elements
        aggregated = self._aggregate_materials(all_materials)

        state["material_list"] = aggregated

        self.log(f"Mapped {len(all_materials)} material items, aggregated to {len(aggregated)} unique materials")
        state["processing_log"].append(
            f"Material Mapper: mapped {len(elements)} elements to {len(aggregated)} unique materials"
        )

        return state

    def _map_element(
        self, element: dict[str, Any], quantities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Map a single element to its required materials using rules."""
        ifc_type = element.get("ifc_type", "")
        is_external = element.get("is_external", False)
        materials_from_ifc = element.get("materials", [])

        # Get rules for this element type
        type_rules = self.element_rules.get(ifc_type, {})
        if not type_rules:
            # No rules for this type - skip
            return []

        # Find the best matching rule variant
        rule_variant = self._find_matching_rule(
            type_rules, is_external, materials_from_ifc
        )
        if not rule_variant:
            return []

        # Build quantity lookup: description -> value
        qty_lookup: dict[str, float] = {}
        for q in quantities:
            qty_lookup[q["description"]] = q["quantity"]

        # Apply each material rule
        result = []
        for mat_rule in rule_variant.get("materials", []):
            material = self._apply_material_rule(
                mat_rule, qty_lookup, element
            )
            if material:
                result.append(material)

        return result

    def _find_matching_rule(
        self,
        type_rules: dict,
        is_external: bool | None,
        materials_from_ifc: list[str],
    ) -> dict | None:
        """Find the best matching rule variant for an element."""
        # Remove the description key if present
        variants = {k: v for k, v in type_rules.items() if k != "_description"}

        if not variants:
            return None

        # If there's only one variant (like "standard"), use it
        if len(variants) == 1:
            return next(iter(variants.values()))

        # Try to match conditions
        materials_lower = " ".join(materials_from_ifc).lower()

        for variant_name, variant in variants.items():
            condition = variant.get("condition", {})

            # Check is_external condition
            if "is_external" in condition:
                if condition["is_external"] != is_external:
                    continue

            # Check material_contains condition
            if "material_contains" in condition:
                if condition["material_contains"].lower() not in materials_lower:
                    continue

            return variant

        # No condition matched - return first variant as fallback
        return next(iter(variants.values()))

    def _apply_material_rule(
        self,
        rule: dict,
        qty_lookup: dict[str, float],
        element: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Apply a single material rule to produce a material item."""
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
        if "waste" in rule:
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
        """Look up a waste factor from the waste_factors.json data.

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
