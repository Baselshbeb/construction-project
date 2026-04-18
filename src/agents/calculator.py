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

# Quantity key aliases: different IFC exporters use different names for the same
# quantity.  The calculator tries aliases in order and returns the first non-zero
# value found.  This fixes cross-exporter compatibility issues (Revit vs ArchiCAD
# vs generic).
QTY_ALIASES: dict[str, list[str]] = {
    "Length": ["Length", "NominalLength"],
    "Height": ["Height", "NominalHeight", "OverallHeight"],
    "Width": ["Width", "NominalWidth", "Thickness", "OverallWidth"],
    "Depth": ["Depth", "NominalDepth", "SlabDepth", "Thickness"],
    "GrossArea": [
        "GrossArea", "GrossSideArea", "GrossWallArea", "GrossFloorArea",
        "GrossFootprintArea", "Area",
    ],
    "NetArea": [
        "NetArea", "NetSideArea", "NetWallArea", "NetFloorArea",
        "NetFootprintArea",
    ],
    "GrossVolume": ["GrossVolume", "Volume"],
    "NetVolume": ["NetVolume"],
    "Perimeter": ["Perimeter", "GrossPerimeter"],
    "CrossSectionArea": ["CrossSectionArea", "GrossCrossSectionArea"],
    "OuterSurfaceArea": ["OuterSurfaceArea", "GrossOuterSurfaceArea", "GrossSurfaceArea"],
}

# Threshold below which a quantity value is likely in millimetres (anything
# above ~10 for a "Width" / "Depth" field is suspicious for metres).
_MM_THRESHOLD = 10.0


def _resolve_qty(qto: dict[str, float], key: str) -> float:
    """Look up a quantity using alias chain; return first non-zero hit."""
    aliases = QTY_ALIASES.get(key, [key])
    for alias in aliases:
        val = qto.get(alias, 0)
        if val:
            return float(val)
    return 0.0


def _normalize_unit(value: float, key: str) -> float:
    """Detect likely-millimetre values and convert to metres.

    Heuristic: for dimensional quantities (Width, Height, Depth, Length),
    a raw value > _MM_THRESHOLD is almost certainly in mm when the expected
    SI unit is metres (walls are rarely >10 m thick, or >10 m deep).
    """
    if key in ("Width", "Depth", "Thickness") and value > _MM_THRESHOLD:
        return value / 1000.0
    return value


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

        # Build a lookup of door/window opening areas per storey so we can
        # deduct actual openings from walls instead of guessing 15%.
        opening_area_by_storey: dict[str, float] = {}
        opening_count_by_storey: dict[str, int] = {}
        wall_gross_area_by_storey: dict[str, float] = {}

        # First pass: collect opening areas from doors & windows
        for elem in elements:
            ifc_type = elem.get("ifc_type", "")
            storey = elem.get("storey") or "_unknown"
            if ifc_type in ("IfcDoor", "IfcWindow"):
                qto = elem.get("quantities", {})
                w = _normalize_unit(_resolve_qty(qto, "Width"), "Width")
                h = _normalize_unit(_resolve_qty(qto, "Height"), "Height")
                area = qto.get("Area", 0) or (w * h)
                opening_area_by_storey[storey] = (
                    opening_area_by_storey.get(storey, 0) + area
                )
                opening_count_by_storey[storey] = (
                    opening_count_by_storey.get(storey, 0) + 1
                )

        # Second pass: collect gross wall areas per storey
        for elem in elements:
            ifc_type = elem.get("ifc_type", "")
            storey = elem.get("storey") or "_unknown"
            if ifc_type in ("IfcWall", "IfcWallStandardCase"):
                qto = elem.get("quantities", {})
                length = _resolve_qty(qto, "Length")
                height = _normalize_unit(_resolve_qty(qto, "Height"), "Height")
                gross_area = _resolve_qty(qto, "GrossArea")
                if not gross_area and length and height:
                    gross_area = length * height
                wall_gross_area_by_storey[storey] = (
                    wall_gross_area_by_storey.get(storey, 0) + gross_area
                )

        # Compute opening ratio per storey (for wall net-area deduction)
        self._opening_ratio_by_storey: dict[str, float] = {}
        for storey in wall_gross_area_by_storey:
            wall_area = wall_gross_area_by_storey[storey]
            opening_area = opening_area_by_storey.get(storey, 0)
            if wall_area > 0 and opening_area > 0:
                ratio = min(opening_area / wall_area, 0.80)  # cap at 80%
                if ratio > 0.75:
                    self.log_warning(
                        f"  Storey '{storey}': high opening ratio {ratio:.0%} — "
                        f"verify facade design is correct"
                    )
                self._opening_ratio_by_storey[storey] = ratio
                self.log(
                    f"  Storey '{storey}': opening ratio = {ratio:.1%} "
                    f"({opening_area:.1f} m2 openings / {wall_area:.1f} m2 walls)"
                )

        plog = state.get("_project_logger")

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
            if plog:
                ifc_type = element.get("ifc_type", "")
                extra: dict[str, Any] = {}
                if ifc_type in ("IfcWall", "IfcWallStandardCase"):
                    storey = element.get("storey") or "_unknown"
                    per_wall_openings = element.get("openings", [])
                    if per_wall_openings:
                        extra["opening_method"] = "per_wall"
                    elif self._opening_ratio_by_storey.get(storey, 0) > 0:
                        extra["opening_method"] = "storey_avg"
                    else:
                        extra["opening_method"] = "qto"
                plog.log_element("Calculation", element["ifc_id"], ifc_type,
                                 f"Computed {len(quantities)} quantities", **extra)

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
        elif ifc_type in ("IfcRamp", "IfcRampFlight"):
            return self._calc_ramp(element, qto, props)
        elif ifc_type == "IfcCovering":
            return self._calc_covering(element, qto, props)
        elif ifc_type == "IfcCurtainWall":
            return self._calc_curtain_wall(element, qto, props)
        elif ifc_type == "IfcRailing":
            return self._calc_railing(element, qto, props)
        elif ifc_type == "IfcMember":
            return self._calc_member(element, qto, props)
        elif ifc_type == "IfcPlate":
            return self._calc_plate(element, qto, props)
        else:
            return self._calc_generic(element, qto, props)

    # ------------------------------------------------------------------
    # Element-specific calculators
    # ------------------------------------------------------------------

    def _calc_wall(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate wall quantities.

        Uses actual door/window opening ratios per storey instead of a
        hardcoded 15% deduction.
        """
        quantities = []
        length = _resolve_qty(qto, "Length")
        height = _normalize_unit(_resolve_qty(qto, "Height"), "Height")
        width = _normalize_unit(_resolve_qty(qto, "Width"), "Width")
        is_external = elem.get("is_external", False)
        storey = elem.get("storey") or "_unknown"

        # Gross wall area (one side)
        gross_area = _resolve_qty(qto, "GrossArea")
        if not gross_area and length and height:
            gross_area = length * height

        # Net area — priority order:
        # 1. IFC NetArea from Qto (most reliable)
        # 2. Per-wall opening deduction via IfcRelVoidsElement (exact)
        # 3. Storey-level average opening ratio (approximate fallback)
        net_area = _resolve_qty(qto, "NetArea")
        opening_method = "qto"
        if not net_area and gross_area:
            per_wall_openings = elem.get("openings", [])
            if per_wall_openings:
                # Use exact per-wall opening area from IFC relationships
                total_opening_area = sum(o.get("area", 0) for o in per_wall_openings)
                net_area = max(gross_area - total_opening_area, 0)
                opening_method = "per_wall"
            else:
                # Fall back to storey-level average
                opening_ratio = self._opening_ratio_by_storey.get(storey, 0.10)
                net_area = gross_area * (1.0 - opening_ratio)
                opening_method = "storey_avg"

        # Volume
        gross_volume = _resolve_qty(qto, "GrossVolume")
        if not gross_volume and gross_area and width:
            gross_volume = gross_area * width

        net_volume = _resolve_qty(qto, "NetVolume")
        if not net_volume and gross_volume and gross_area:
            # Apply same opening ratio to volume
            net_volume = gross_volume * (net_area / gross_area) if gross_area > 0 else gross_volume

        # Full precision — rounding deferred to export
        quantities.append({
            "description": "Gross wall area (one side)",
            "quantity": gross_area,
            "unit": "m2",
        })
        quantities.append({
            "description": "Net wall area (minus openings, one side)",
            "quantity": net_area,
            "unit": "m2",
        })
        quantities.append({
            "description": "Wall volume",
            "quantity": net_volume,
            "unit": "m3",
        })

        # Both sides for internal walls (plaster on both sides)
        if not is_external:
            quantities.append({
                "description": "Net wall area (both sides, for plaster/paint)",
                "quantity": net_area * 2,
                "unit": "m2",
            })
        else:
            quantities.append({
                "description": "Internal face area (for plaster/paint)",
                "quantity": net_area,
                "unit": "m2",
            })
            quantities.append({
                "description": "External face area (for ext. plaster/paint)",
                "quantity": net_area,
                "unit": "m2",
            })

        if length:
            quantities.append({
                "description": "Wall length (for skirting/coving)",
                "quantity": length,
                "unit": "m",
            })

        return quantities

    def _calc_slab(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate slab quantities."""
        quantities = []
        length = _resolve_qty(qto, "Length")
        width_val = _normalize_unit(_resolve_qty(qto, "Width"), "Width")
        depth = _normalize_unit(_resolve_qty(qto, "Depth"), "Depth")

        area = _resolve_qty(qto, "GrossArea") or _resolve_qty(qto, "NetArea")
        if not area and length and width_val:
            area = length * width_val

        volume = _resolve_qty(qto, "GrossVolume") or _resolve_qty(qto, "NetVolume")
        if not volume and area and depth:
            volume = area * depth

        perimeter = _resolve_qty(qto, "Perimeter")
        if not perimeter and length and width_val:
            perimeter = 2 * (length + width_val)

        quantities.append({"description": "Slab area (top face)", "quantity": area, "unit": "m2"})
        quantities.append({"description": "Slab area (bottom face / soffit)", "quantity": area, "unit": "m2"})
        quantities.append({"description": "Slab volume", "quantity": volume, "unit": "m3"})
        quantities.append({"description": "Slab perimeter", "quantity": perimeter, "unit": "m"})

        edge_area = perimeter * depth if perimeter and depth else 0
        quantities.append({"description": "Formwork area (soffit + edges)", "quantity": area + edge_area, "unit": "m2"})

        return quantities

    def _calc_column(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate column quantities."""
        import math
        quantities = []
        # Columns: "Length" in IFC is height; also try "Height" alias
        height = _resolve_qty(qto, "Height") or _resolve_qty(qto, "Length")
        cross_section = _resolve_qty(qto, "CrossSectionArea")
        volume = _resolve_qty(qto, "GrossVolume") or _resolve_qty(qto, "NetVolume")
        outer_surface = _resolve_qty(qto, "OuterSurfaceArea")

        if not volume and cross_section and height:
            volume = cross_section * height

        quantities.append({"description": "Column volume", "quantity": volume, "unit": "m3"})

        if outer_surface:
            quantities.append({"description": "Column surface area (for formwork/plaster)", "quantity": outer_surface, "unit": "m2"})
        elif cross_section and height:
            # Estimate surface: use perimeter * height.
            # Perimeter for a circle = pi*d, for a square = 4*side.
            # Use circumscribed circle as upper bound: pi * sqrt(4A/pi) = 2*sqrt(pi*A)
            perimeter_est = 2 * math.sqrt(math.pi * cross_section)
            surface = perimeter_est * height
            quantities.append({"description": "Column surface area (estimated)", "quantity": surface, "unit": "m2"})

        quantities.append({"description": "Column count", "quantity": 1, "unit": "nr"})
        return quantities

    def _calc_beam(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate beam quantities."""
        quantities = []
        length = _resolve_qty(qto, "Length")
        volume = _resolve_qty(qto, "GrossVolume") or _resolve_qty(qto, "NetVolume")
        outer_surface = _resolve_qty(qto, "OuterSurfaceArea")
        cross_section = _resolve_qty(qto, "CrossSectionArea")

        if not volume and cross_section and length:
            volume = cross_section * length

        quantities.append({"description": "Beam volume", "quantity": volume, "unit": "m3"})
        quantities.append({"description": "Beam length", "quantity": length, "unit": "m"})

        if outer_surface:
            quantities.append({"description": "Beam surface area (for formwork)", "quantity": outer_surface, "unit": "m2"})

        return quantities

    def _calc_door(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate door quantities."""
        quantities = []
        width = _normalize_unit(_resolve_qty(qto, "Width"), "Width")
        height = _normalize_unit(_resolve_qty(qto, "Height"), "Height")
        area = qto.get("Area", 0)
        if not area and width and height:
            area = width * height

        quantities.append({"description": "Door count", "quantity": 1, "unit": "nr"})
        quantities.append({"description": "Door opening area (for wall deduction)", "quantity": area, "unit": "m2"})
        quantities.append({
            "description": "Door frame perimeter",
            "quantity": 2 * (height + width) if height and width else 0,
            "unit": "m",
        })
        return quantities

    def _calc_window(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate window quantities."""
        quantities = []
        width = _normalize_unit(_resolve_qty(qto, "Width"), "Width")
        height = _normalize_unit(_resolve_qty(qto, "Height"), "Height")
        area = qto.get("Area", 0)
        if not area and width and height:
            area = width * height

        quantities.append({"description": "Window count", "quantity": 1, "unit": "nr"})
        quantities.append({"description": "Window opening area (for wall deduction)", "quantity": area, "unit": "m2"})
        quantities.append({"description": "Window sill length", "quantity": width, "unit": "m"})
        return quantities

    def _calc_stair(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate stair quantities."""
        quantities = []
        volume = _resolve_qty(qto, "GrossVolume") or _resolve_qty(qto, "NetVolume")
        area = _resolve_qty(qto, "GrossArea") or _resolve_qty(qto, "NetArea")

        if volume:
            quantities.append({"description": "Stair volume", "quantity": volume, "unit": "m3"})
        if area:
            quantities.append({"description": "Stair area", "quantity": area, "unit": "m2"})
        quantities.append({"description": "Stair count", "quantity": 1, "unit": "nr"})
        return quantities

    def _calc_roof(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate roof quantities with slope compensation."""
        import math
        quantities = []

        # Base slab-like quantities
        length = _resolve_qty(qto, "Length")
        width_val = _normalize_unit(_resolve_qty(qto, "Width"), "Width")
        depth = _normalize_unit(_resolve_qty(qto, "Depth"), "Depth")

        footprint_area = _resolve_qty(qto, "GrossArea") or _resolve_qty(qto, "NetArea")
        if not footprint_area and length and width_val:
            footprint_area = length * width_val

        volume = _resolve_qty(qto, "GrossVolume") or _resolve_qty(qto, "NetVolume")
        if not volume and footprint_area and depth:
            volume = footprint_area * depth

        # Detect slope — check property or estimate from bounding box height
        slope_angle = props.get("PitchAngle", 0) or props.get("Slope", 0)
        if not slope_angle:
            # Estimate from bounding box if available
            bbox_height = qto.get("Height", 0) or _resolve_qty(qto, "Height")
            if bbox_height and footprint_area and bbox_height > 0.5:
                # Rough: if roof has significant height, estimate slope
                est_span = math.sqrt(footprint_area) if footprint_area else 0
                if est_span > 0:
                    slope_angle = math.degrees(math.atan(bbox_height / (est_span / 2)))

        # Sloped surface area = footprint / cos(angle)
        slope_factor = 1.0
        if slope_angle and slope_angle > 5:
            slope_factor = 1.0 / math.cos(math.radians(min(slope_angle, 60)))

        sloped_area = footprint_area * slope_factor

        quantities.append({"description": "Roof footprint area", "quantity": footprint_area, "unit": "m2"})
        quantities.append({"description": "Roof sloped surface area", "quantity": sloped_area, "unit": "m2"})
        if volume:
            quantities.append({"description": "Roof volume", "quantity": volume, "unit": "m3"})

        perimeter = _resolve_qty(qto, "Perimeter")
        if not perimeter and length and width_val:
            perimeter = 2 * (length + width_val)
        if perimeter:
            quantities.append({"description": "Roof perimeter (eave length)", "quantity": perimeter, "unit": "m"})

        return quantities

    def _calc_ramp(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate ramp quantities."""
        quantities = []
        volume = _resolve_qty(qto, "GrossVolume") or _resolve_qty(qto, "NetVolume")
        area = _resolve_qty(qto, "GrossArea") or _resolve_qty(qto, "NetArea")
        length = _resolve_qty(qto, "Length")

        if volume:
            quantities.append({"description": "Ramp volume", "quantity": volume, "unit": "m3"})
        if area:
            quantities.append({"description": "Ramp area", "quantity": area, "unit": "m2"})
        if length:
            quantities.append({"description": "Ramp length", "quantity": length, "unit": "m"})
        quantities.append({"description": "Ramp count", "quantity": 1, "unit": "nr"})
        return quantities

    def _calc_covering(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate covering quantities (floors, ceilings, cladding)."""
        quantities = []
        area = _resolve_qty(qto, "GrossArea") or _resolve_qty(qto, "NetArea")
        if not area:
            length = _resolve_qty(qto, "Length")
            width = _normalize_unit(_resolve_qty(qto, "Width"), "Width")
            if length and width:
                area = length * width

        if area:
            quantities.append({"description": "Covering area", "quantity": area, "unit": "m2"})

        perimeter = _resolve_qty(qto, "Perimeter")
        if perimeter:
            quantities.append({"description": "Covering perimeter", "quantity": perimeter, "unit": "m"})

        quantities.append({"description": "Covering count", "quantity": 1, "unit": "nr"})
        return quantities

    def _calc_curtain_wall(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate curtain wall quantities."""
        quantities = []
        area = _resolve_qty(qto, "GrossArea") or _resolve_qty(qto, "NetArea")
        length = _resolve_qty(qto, "Length")
        height = _normalize_unit(_resolve_qty(qto, "Height"), "Height")

        if not area and length and height:
            area = length * height

        if area:
            quantities.append({"description": "Curtain wall area", "quantity": area, "unit": "m2"})
        if length:
            quantities.append({"description": "Curtain wall length", "quantity": length, "unit": "m"})
        quantities.append({"description": "Curtain wall count", "quantity": 1, "unit": "nr"})
        return quantities

    def _calc_railing(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate railing quantities."""
        quantities = []
        length = _resolve_qty(qto, "Length")

        if length:
            quantities.append({"description": "Railing length", "quantity": length, "unit": "m"})
        quantities.append({"description": "Railing count", "quantity": 1, "unit": "nr"})
        return quantities

    def _calc_member(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate structural member quantities (steel members, bracing, etc.)."""
        quantities = []
        length = _resolve_qty(qto, "Length")
        volume = _resolve_qty(qto, "GrossVolume") or _resolve_qty(qto, "NetVolume")
        cross_section = _resolve_qty(qto, "CrossSectionArea")

        if not volume and cross_section and length:
            volume = cross_section * length

        if volume:
            quantities.append({"description": "Member volume", "quantity": volume, "unit": "m3"})
        if length:
            quantities.append({"description": "Member length", "quantity": length, "unit": "m"})

        outer_surface = _resolve_qty(qto, "OuterSurfaceArea")
        if outer_surface:
            quantities.append({"description": "Member surface area", "quantity": outer_surface, "unit": "m2"})

        quantities.append({"description": "Member count", "quantity": 1, "unit": "nr"})
        return quantities

    def _calc_plate(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate plate quantities (steel plates, panels)."""
        quantities = []
        area = _resolve_qty(qto, "GrossArea") or _resolve_qty(qto, "NetArea")
        volume = _resolve_qty(qto, "GrossVolume") or _resolve_qty(qto, "NetVolume")
        width = _normalize_unit(_resolve_qty(qto, "Width"), "Width")

        if area:
            quantities.append({"description": "Plate area", "quantity": area, "unit": "m2"})
        if volume:
            quantities.append({"description": "Plate volume", "quantity": volume, "unit": "m3"})
        elif area and width:
            volume = area * width
            quantities.append({"description": "Plate volume", "quantity": volume, "unit": "m3"})

        quantities.append({"description": "Plate count", "quantity": 1, "unit": "nr"})
        return quantities

    def _calc_foundation(
        self, elem: dict, qto: dict, props: dict
    ) -> list[dict[str, Any]]:
        """Calculate foundation element quantities."""
        quantities = []
        volume = _resolve_qty(qto, "GrossVolume") or _resolve_qty(qto, "NetVolume")
        area = _resolve_qty(qto, "GrossArea") or _resolve_qty(qto, "NetArea")

        if volume:
            quantities.append({"description": "Foundation volume", "quantity": volume, "unit": "m3"})
        if area:
            quantities.append({"description": "Foundation area", "quantity": area, "unit": "m2"})
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
                quantities.append({"description": key, "quantity": float(value), "unit": unit})
        return quantities
