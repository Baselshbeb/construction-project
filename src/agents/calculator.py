"""
Quantity Calculator Agent - computes construction-relevant quantities.

Coach Simple explains:
    "The parser told us each wall is 10m long and 3m high. But a builder
    needs to know: How much AREA to plaster? How much VOLUME of concrete?
    How much PERIMETER for skirting? This agent does all that math."

Pipeline position: THIRD agent (after Parser + Classifier)
Input: ProjectState with parsed_elements (classified)
Output: ProjectState with calculated_quantities filled in
"""

from __future__ import annotations

from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.project import ProcessingStatus


class CalculatorAgent(BaseAgent):
    """Computes construction quantities from parsed element data."""

    def __init__(self):
        super().__init__(
            name="calculator",
            description="Calculates areas, volumes, counts, and derived quantities",
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Calculate quantities for all parsed elements."""
        self.log("Starting quantity calculation...")
        state["status"] = ProcessingStatus.CALCULATING
        state["current_step"] = "Calculating quantities"

        elements = state.get("parsed_elements", [])
        if not elements:
            self.log_warning("No elements to calculate!")
            return state

        calculated = []
        for element in elements:
            quantities = self._calculate_for_element(element)
            calculated.append({
                "element_id": element["ifc_id"],
                "element_type": element["ifc_type"],
                "element_name": element.get("name"),
                "storey": element.get("storey"),
                "category": element.get("category"),
                "quantities": quantities,
            })

        state["calculated_quantities"] = calculated

        # Summary
        total_items = sum(len(c["quantities"]) for c in calculated)
        self.log(f"Calculated {total_items} quantities for {len(calculated)} elements")
        state["processing_log"].append(
            f"Calculator: computed {total_items} quantities for {len(calculated)} elements"
        )
        return state

    def _calculate_for_element(self, element: dict[str, Any]) -> list[dict[str, Any]]:
        """Calculate all relevant quantities for a single element."""
        ifc_type = element.get("ifc_type", "")
        qto = element.get("quantities", {})
        props = element.get("properties", {})

        if ifc_type in ("IfcWall", "IfcWallStandardCase"):
            return self._calc_wall(element, qto, props)
        elif ifc_type == "IfcSlab":
            return self._calc_slab(element, qto, props)
        elif ifc_type == "IfcColumn":
            return self._calc_column(element, qto, props)
        elif ifc_type == "IfcBeam":
            return self._calc_beam(element, qto, props)
        elif ifc_type == "IfcDoor":
            return self._calc_door(element, qto, props)
        elif ifc_type == "IfcWindow":
            return self._calc_window(element, qto, props)
        elif ifc_type in ("IfcStair", "IfcStairFlight"):
            return self._calc_stair(element, qto, props)
        elif ifc_type == "IfcRoof":
            return self._calc_roof(element, qto, props)
        elif ifc_type in ("IfcFooting", "IfcPile"):
            return self._calc_foundation(element, qto, props)
        else:
            return self._calc_generic(element, qto, props)

    # ------------------------------------------------------------------
    # Element-specific calculators
    # ------------------------------------------------------------------

    def _calc_wall(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate wall quantities.

        Coach Simple: "A wall needs: area for plaster/paint, volume for
        concrete, and we subtract doors/windows (net area)."
        """
        quantities = []
        length = qto.get("Length", 0)
        height = qto.get("Height", 0)
        width = qto.get("Width", 0)
        is_external = elem.get("is_external", False)

        # Gross wall area (one side)
        gross_area = qto.get("GrossArea", 0) or qto.get("GrossSideArea", 0)
        if not gross_area and length and height:
            gross_area = length * height

        # Net area (minus openings)
        net_area = qto.get("NetArea", 0) or qto.get("NetSideArea", 0)
        if not net_area:
            net_area = gross_area * 0.85  # assume 15% openings

        # Volume
        gross_volume = qto.get("GrossVolume", 0)
        if not gross_volume and gross_area and width:
            gross_volume = gross_area * width

        net_volume = qto.get("NetVolume", 0)
        if not net_volume:
            net_volume = gross_volume * 0.85

        quantities.append({
            "description": "Gross wall area (one side)",
            "quantity": round(gross_area, 2),
            "unit": "m2",
        })
        quantities.append({
            "description": "Net wall area (minus openings, one side)",
            "quantity": round(net_area, 2),
            "unit": "m2",
        })
        quantities.append({
            "description": "Wall volume",
            "quantity": round(net_volume, 2),
            "unit": "m3",
        })

        # Both sides for internal walls (plaster on both sides)
        if not is_external:
            quantities.append({
                "description": "Net wall area (both sides, for plaster/paint)",
                "quantity": round(net_area * 2, 2),
                "unit": "m2",
            })
        else:
            # External: internal side + external side
            quantities.append({
                "description": "Internal face area (for plaster/paint)",
                "quantity": round(net_area, 2),
                "unit": "m2",
            })
            quantities.append({
                "description": "External face area (for ext. plaster/paint)",
                "quantity": round(net_area, 2),
                "unit": "m2",
            })

        # Perimeter for skirting
        if length:
            quantities.append({
                "description": "Wall length (for skirting/coving)",
                "quantity": round(length, 2),
                "unit": "m",
            })

        return quantities

    def _calc_slab(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate slab quantities.

        Coach Simple: "A floor slab needs: area for tiling/screeding,
        volume for concrete, perimeter for edge details."
        """
        quantities = []
        length = qto.get("Length", 0)
        width_val = qto.get("Width", 0)
        depth = qto.get("Depth", 0)

        area = qto.get("Area", 0) or qto.get("NetArea", 0)
        if not area and length and width_val:
            area = length * width_val

        volume = qto.get("GrossVolume", 0) or qto.get("NetVolume", 0)
        if not volume and area and depth:
            volume = area * depth

        perimeter = qto.get("Perimeter", 0)
        if not perimeter and length and width_val:
            perimeter = 2 * (length + width_val)

        quantities.append({
            "description": "Slab area (top face)",
            "quantity": round(area, 2),
            "unit": "m2",
        })
        quantities.append({
            "description": "Slab area (bottom face / soffit)",
            "quantity": round(area, 2),
            "unit": "m2",
        })
        quantities.append({
            "description": "Slab volume",
            "quantity": round(volume, 2),
            "unit": "m3",
        })
        quantities.append({
            "description": "Slab perimeter",
            "quantity": round(perimeter, 2),
            "unit": "m",
        })

        # Formwork area = bottom face + edge
        edge_area = perimeter * depth if perimeter and depth else 0
        quantities.append({
            "description": "Formwork area (soffit + edges)",
            "quantity": round(area + edge_area, 2),
            "unit": "m2",
        })

        return quantities

    def _calc_column(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate column quantities."""
        quantities = []
        height = qto.get("Length", 0)  # Column "length" is its height
        cross_section = qto.get("CrossSectionArea", 0)
        volume = qto.get("GrossVolume", 0) or qto.get("NetVolume", 0)
        outer_surface = qto.get("OuterSurfaceArea", 0)

        if not volume and cross_section and height:
            volume = cross_section * height

        quantities.append({
            "description": "Column volume",
            "quantity": round(volume, 3),
            "unit": "m3",
        })

        if outer_surface:
            quantities.append({
                "description": "Column surface area (for formwork/plaster)",
                "quantity": round(outer_surface, 2),
                "unit": "m2",
            })
        elif cross_section and height:
            # Approximate: assume square cross-section
            import math
            side = math.sqrt(cross_section)
            surface = 4 * side * height
            quantities.append({
                "description": "Column surface area (estimated)",
                "quantity": round(surface, 2),
                "unit": "m2",
            })

        quantities.append({
            "description": "Column count",
            "quantity": 1,
            "unit": "nr",
        })

        return quantities

    def _calc_beam(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate beam quantities."""
        quantities = []
        length = qto.get("Length", 0)
        volume = qto.get("GrossVolume", 0) or qto.get("NetVolume", 0)
        outer_surface = qto.get("OuterSurfaceArea", 0)
        cross_section = qto.get("CrossSectionArea", 0)

        if not volume and cross_section and length:
            volume = cross_section * length

        quantities.append({
            "description": "Beam volume",
            "quantity": round(volume, 3),
            "unit": "m3",
        })
        quantities.append({
            "description": "Beam length",
            "quantity": round(length, 2),
            "unit": "m",
        })

        if outer_surface:
            quantities.append({
                "description": "Beam surface area (for formwork)",
                "quantity": round(outer_surface, 2),
                "unit": "m2",
            })

        return quantities

    def _calc_door(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate door quantities."""
        quantities = []
        width = qto.get("Width", 0)
        height = qto.get("Height", 0)
        area = qto.get("Area", 0)
        if not area and width and height:
            area = width * height

        quantities.append({
            "description": "Door count",
            "quantity": 1,
            "unit": "nr",
        })
        quantities.append({
            "description": "Door opening area (for wall deduction)",
            "quantity": round(area, 2),
            "unit": "m2",
        })
        quantities.append({
            "description": "Door frame perimeter",
            "quantity": round(2 * height + width, 2) if height and width else 0,
            "unit": "m",
        })

        return quantities

    def _calc_window(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate window quantities."""
        quantities = []
        width = qto.get("Width", 0)
        height = qto.get("Height", 0)
        area = qto.get("Area", 0)
        if not area and width and height:
            area = width * height

        quantities.append({
            "description": "Window count",
            "quantity": 1,
            "unit": "nr",
        })
        quantities.append({
            "description": "Window opening area (for wall deduction)",
            "quantity": round(area, 2),
            "unit": "m2",
        })
        quantities.append({
            "description": "Window sill length",
            "quantity": round(width, 2) if width else 0,
            "unit": "m",
        })

        return quantities

    def _calc_stair(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate stair quantities."""
        quantities = []
        volume = qto.get("GrossVolume", 0) or qto.get("NetVolume", 0)
        area = qto.get("GrossArea", 0) or qto.get("NetArea", 0)

        if volume:
            quantities.append({
                "description": "Stair volume",
                "quantity": round(volume, 3),
                "unit": "m3",
            })
        if area:
            quantities.append({
                "description": "Stair area",
                "quantity": round(area, 2),
                "unit": "m2",
            })
        quantities.append({
            "description": "Stair count",
            "quantity": 1,
            "unit": "nr",
        })

        return quantities

    def _calc_roof(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate roof quantities."""
        return self._calc_slab(elem, qto, props)

    def _calc_foundation(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate foundation element quantities."""
        quantities = []
        volume = qto.get("GrossVolume", 0) or qto.get("NetVolume", 0)
        area = qto.get("GrossArea", 0) or qto.get("NetArea", 0)

        if volume:
            quantities.append({
                "description": "Foundation volume",
                "quantity": round(volume, 3),
                "unit": "m3",
            })
        if area:
            quantities.append({
                "description": "Foundation area",
                "quantity": round(area, 2),
                "unit": "m2",
            })

        return quantities

    def _calc_generic(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Fallback calculator for unrecognized element types."""
        quantities = []
        for key, value in qto.items():
            if isinstance(value, (int, float)) and value > 0:
                unit = "m2" if "area" in key.lower() else (
                    "m3" if "volume" in key.lower() else (
                        "m" if "length" in key.lower() or "perimeter" in key.lower() else "nr"
                    )
                )
                quantities.append({
                    "description": key,
                    "quantity": round(float(value), 3),
                    "unit": unit,
                })
        return quantities
