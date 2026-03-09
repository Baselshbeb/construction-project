"""
Element Classifier Agent - categorizes building elements into BOQ sections.

Coach Simple explains:
    "The parser gave us a pile of building pieces. Now we need to SORT them.
    Is this wall an external wall or an internal partition? Is this slab a
    ground floor, upper floor, or roof? This agent sorts every piece into
    the right category so the BOQ is organized properly."

This agent uses rule-based classification first (fast and reliable),
then falls back to AI for ambiguous elements.

Pipeline position: SECOND agent
Input: ProjectState with parsed_elements
Output: ProjectState with category set on each element + classified_elements dict
"""

from __future__ import annotations

from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.project import ElementCategory, ProcessingStatus


# ------------------------------------------------------------------
# Classification rules
# ------------------------------------------------------------------
# Coach Simple: "These rules are like a sorting hat. If it's an IfcDoor,
# it goes in the 'doors' pile. Simple!"

# Direct type-to-category mapping for unambiguous types
DIRECT_TYPE_MAP: dict[str, ElementCategory] = {
    "IfcDoor": ElementCategory.DOORS,
    "IfcWindow": ElementCategory.WINDOWS,
    "IfcStair": ElementCategory.STAIRS,
    "IfcStairFlight": ElementCategory.STAIRS,
    "IfcRamp": ElementCategory.STAIRS,
    "IfcRampFlight": ElementCategory.STAIRS,
    "IfcRoof": ElementCategory.ROOF,
    "IfcCovering": ElementCategory.FINISHES,
    "IfcRailing": ElementCategory.STAIRS,
    "IfcCurtainWall": ElementCategory.EXTERNAL_WALLS,
    "IfcFooting": ElementCategory.SUBSTRUCTURE,
    "IfcPile": ElementCategory.SUBSTRUCTURE,
}


def _classify_wall(element: dict[str, Any]) -> ElementCategory:
    """Classify a wall as external or internal."""
    # Check IsExternal property
    is_external = element.get("is_external")
    if is_external is True:
        return ElementCategory.EXTERNAL_WALLS
    if is_external is False:
        return ElementCategory.INTERNAL_WALLS

    # Check property sets
    props = element.get("properties", {})
    if props.get("IsExternal") is True:
        return ElementCategory.EXTERNAL_WALLS
    if props.get("IsExternal") is False:
        return ElementCategory.INTERNAL_WALLS

    # Heuristic: check name for clues
    name = (element.get("name") or "").lower()
    if any(kw in name for kw in ["external", "exterior", "outer", "facade"]):
        return ElementCategory.EXTERNAL_WALLS
    if any(kw in name for kw in ["internal", "interior", "inner", "partition"]):
        return ElementCategory.INTERNAL_WALLS

    # Heuristic: thicker walls are more likely external
    quantities = element.get("quantities", {})
    width = quantities.get("Width", 0)
    if width >= 0.15:  # 150mm or thicker -> likely external
        return ElementCategory.EXTERNAL_WALLS

    # Default to external (safer - won't miss materials)
    return ElementCategory.EXTERNAL_WALLS


def _classify_slab(element: dict[str, Any]) -> ElementCategory:
    """Classify a slab as ground floor, upper floor, or roof."""
    name = (element.get("name") or "").lower()
    storey = (element.get("storey") or "").lower()

    # Check name for clues
    if any(kw in name for kw in ["roof", "terrace", "top"]):
        return ElementCategory.ROOF
    if any(kw in name for kw in ["ground", "foundation", "base", "raft"]):
        return ElementCategory.SUBSTRUCTURE

    # Check storey
    if any(kw in storey for kw in ["ground", "basement", "sub"]):
        # Ground floor slab could be substructure
        # But if it's named just "Ground Floor Slab", it's an upper floor
        if any(kw in name for kw in ["foundation", "raft", "base"]):
            return ElementCategory.SUBSTRUCTURE

    return ElementCategory.UPPER_FLOORS


def _classify_column(element: dict[str, Any]) -> ElementCategory:
    """Classify a column - almost always frame."""
    storey = (element.get("storey") or "").lower()
    if any(kw in storey for kw in ["basement", "sub"]):
        return ElementCategory.SUBSTRUCTURE
    return ElementCategory.FRAME


def _classify_beam(element: dict[str, Any]) -> ElementCategory:
    """Classify a beam - almost always frame."""
    return ElementCategory.FRAME


class ClassifierAgent(BaseAgent):
    """Classifies building elements into BOQ categories."""

    def __init__(self):
        super().__init__(
            name="classifier",
            description="Categorizes building elements into BOQ sections",
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Classify all parsed elements into categories.

        Steps:
        1. Read parsed_elements from state
        2. Apply classification rules to each element
        3. Update each element's category
        4. Build classified_elements index (category -> element IDs)
        """
        self.log("Starting element classification...")
        state["status"] = ProcessingStatus.CLASSIFYING
        state["current_step"] = "Classifying elements"

        elements = state.get("parsed_elements", [])
        if not elements:
            self.log_warning("No elements to classify!")
            return state

        classified: dict[str, list[int]] = {}
        unclassified = []

        for element in elements:
            category = self._classify_element(element)

            if category:
                element["category"] = category.value
                cat_key = category.value
                if cat_key not in classified:
                    classified[cat_key] = []
                classified[cat_key].append(element["ifc_id"])
            else:
                unclassified.append(element)
                self.log_warning(
                    f"Could not classify: {element.get('ifc_type')} "
                    f"'{element.get('name')}'"
                )

        state["classified_elements"] = classified

        # Log summary
        self.log(f"Classified {len(elements) - len(unclassified)}/{len(elements)} elements:")
        for category, ids in sorted(classified.items()):
            self.log(f"  {category}: {len(ids)} elements")
        if unclassified:
            self.log_warning(f"  unclassified: {len(unclassified)} elements")

        state["processing_log"].append(
            f"Classifier: categorized {len(elements) - len(unclassified)} elements "
            f"into {len(classified)} categories"
        )

        return state

    def _classify_element(self, element: dict[str, Any]) -> ElementCategory | None:
        """Classify a single element using rules."""
        ifc_type = element.get("ifc_type", "")

        # Direct mapping for simple types
        if ifc_type in DIRECT_TYPE_MAP:
            return DIRECT_TYPE_MAP[ifc_type]

        # Type-specific classification logic
        if ifc_type in ("IfcWall", "IfcWallStandardCase"):
            return _classify_wall(element)

        if ifc_type == "IfcSlab":
            return _classify_slab(element)

        if ifc_type == "IfcColumn":
            return _classify_column(element)

        if ifc_type in ("IfcBeam",):
            return _classify_beam(element)

        # IfcBuildingElementProxy - catch-all for unrecognized elements
        if ifc_type == "IfcBuildingElementProxy":
            self.log_warning(
                f"IfcBuildingElementProxy '{element.get('name')}' "
                f"needs manual classification"
            )
            return None

        # Unknown type
        self.log_warning(f"Unknown IFC type: {ifc_type}")
        return None
