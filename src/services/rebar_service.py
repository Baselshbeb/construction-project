"""
Rebar Service - extracts reinforcement data from IFC files.

Searches for IfcReinforcingBar and IfcReinforcingBarSet entities,
links them to their host building elements, and computes steel
weights based on bar diameter, length, and count.

When the IFC model contains no reinforcement data (which is common
for architectural models), the service returns an empty dict gracefully.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import ifcopenshell
import ifcopenshell.util.element

from src.utils.logger import get_logger

logger = get_logger("rebar_service")

# Steel density in kg/m3
STEEL_DENSITY_KG_M3 = 7850.0


class RebarService:
    """Extracts reinforcement bar data from an IFC model.

    Usage:
        service = RebarService(ifc_model)
        rebar_data = service.extract_rebar_data()
        # rebar_data is {element_id: {"total_weight_kg": ..., ...}}
    """

    def __init__(self, model: ifcopenshell.file) -> None:
        """Initialise with an already-opened IfcOpenShell model.

        Args:
            model: An ifcopenshell.file instance (from ifcopenshell.open()).
        """
        self.model = model

    def extract_rebar_data(self) -> dict[int, dict[str, Any]]:
        """Extract reinforcement data grouped by host element ID.

        Returns:
            A dict keyed by host element IFC id, each value containing:
                - total_weight_kg (float): total rebar weight in kg
                - bar_count (int): number of bars
                - grade (str): steel grade if found, else "unknown"
                - source (str): always "ifc_detailed"

            Returns an empty dict if no reinforcement entities exist.
        """
        rebars = self._collect_rebars()
        if not rebars:
            logger.info("No IfcReinforcingBar/IfcReinforcingBarSet entities found in model")
            return {}

        logger.info(f"Found {len(rebars)} reinforcement entities")

        # Accumulator: host_element_id -> {weight, count, grade}
        grouped: dict[int, dict[str, Any]] = {}

        for rebar in rebars:
            try:
                host_id = self._find_host_element_id(rebar)
                if host_id is None:
                    logger.debug(
                        f"Rebar #{rebar.id()} has no identifiable host element, skipping"
                    )
                    continue

                diameter_m = self._get_diameter(rebar)
                length_m = self._get_bar_length(rebar)
                count = self._get_bar_count(rebar)
                grade = self._get_grade(rebar)

                if diameter_m <= 0 or length_m <= 0:
                    logger.debug(
                        f"Rebar #{rebar.id()} has zero diameter or length, skipping"
                    )
                    continue

                weight_kg = self._compute_weight(diameter_m, length_m, count)

                if host_id not in grouped:
                    grouped[host_id] = {
                        "total_weight_kg": 0.0,
                        "bar_count": 0,
                        "grade": grade,
                        "source": "ifc_detailed",
                    }

                grouped[host_id]["total_weight_kg"] += weight_kg
                grouped[host_id]["bar_count"] += count
                # Keep the most specific grade we find
                if grade != "unknown":
                    grouped[host_id]["grade"] = grade

            except Exception as e:
                logger.warning(f"Failed to process rebar #{rebar.id()}: {e}")

        logger.info(
            f"Extracted rebar data for {len(grouped)} host elements, "
            f"total weight: {sum(d['total_weight_kg'] for d in grouped.values()):.1f} kg"
        )
        return grouped

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_rebars(self) -> list:
        """Collect all IfcReinforcingBar and IfcReinforcingBarSet entities."""
        rebars: list = []
        for ifc_type in ("IfcReinforcingBar", "IfcReinforcingBarSet"):
            try:
                rebars.extend(self.model.by_type(ifc_type))
            except RuntimeError:
                # Type not present in this schema version
                pass
        return rebars

    def _find_host_element_id(self, rebar) -> Optional[int]:
        """Find the host building element for a rebar entity.

        Searches through three possible IFC relationship types:
        1. IfcRelAggregates (rebar aggregated into a host element)
        2. IfcRelContainedInSpatialStructure (rebar in same spatial container)
        3. IfcRelAssignsToProduct (rebar assigned to a product)

        Args:
            rebar: An IfcReinforcingBar or IfcReinforcingBarSet entity.

        Returns:
            The IFC id of the host element, or None if not found.
        """
        # 1. IfcRelAggregates: rebar is a part decomposed from a host
        if hasattr(rebar, "Decomposes") and rebar.Decomposes:
            for rel in rebar.Decomposes:
                if rel.is_a("IfcRelAggregates"):
                    host = rel.RelatingObject
                    if host and hasattr(host, "id"):
                        return host.id()

        # 2. IfcRelContainedInSpatialStructure: not a direct host link,
        #    but we can try IfcRelAssignsToProduct first
        if hasattr(rebar, "HasAssignments") and rebar.HasAssignments:
            for rel in rebar.HasAssignments:
                if rel.is_a("IfcRelAssignsToProduct"):
                    product = rel.RelatingProduct
                    if product and hasattr(product, "id"):
                        return product.id()

        # 3. Walk up via nesting (IfcRelNests)
        if hasattr(rebar, "Nests") and rebar.Nests:
            for rel in rebar.Nests:
                host = rel.RelatingObject
                if host and hasattr(host, "id"):
                    return host.id()

        return None

    def _get_diameter(self, rebar) -> float:
        """Extract nominal diameter in metres from a rebar entity."""
        if hasattr(rebar, "NominalDiameter") and rebar.NominalDiameter:
            return float(rebar.NominalDiameter)
        # Fallback: check property sets
        psets = ifcopenshell.util.element.get_psets(rebar, psets_only=True)
        for pset_values in psets.values():
            for key, val in pset_values.items():
                if "diameter" in key.lower() and isinstance(val, (int, float)):
                    return float(val)
        return 0.0

    def _get_bar_length(self, rebar) -> float:
        """Extract bar length in metres from a rebar entity."""
        if hasattr(rebar, "BarLength") and rebar.BarLength:
            return float(rebar.BarLength)
        # Fallback: check quantity sets
        qtos = ifcopenshell.util.element.get_psets(rebar, qtos_only=True)
        for qto_values in qtos.values():
            for key, val in qto_values.items():
                if "length" in key.lower() and isinstance(val, (int, float)):
                    return float(val)
        return 0.0

    def _get_bar_count(self, rebar) -> int:
        """Extract bar count (defaults to 1 if not specified)."""
        # IfcReinforcingBarSet may have a Quantity attribute
        if hasattr(rebar, "Quantity") and rebar.Quantity:
            return int(rebar.Quantity)
        # Check BarCount in some IFC variants
        if hasattr(rebar, "BarCount") and rebar.BarCount:
            return int(rebar.BarCount)
        # Fallback: check quantity sets
        qtos = ifcopenshell.util.element.get_psets(rebar, qtos_only=True)
        for qto_values in qtos.values():
            for key, val in qto_values.items():
                if "count" in key.lower() and isinstance(val, (int, float)):
                    return int(val)
        return 1

    def _get_grade(self, rebar) -> str:
        """Extract steel grade from rebar properties or material."""
        # Check SteelGrade attribute
        if hasattr(rebar, "SteelGrade") and rebar.SteelGrade:
            return str(rebar.SteelGrade)
        # Check property sets for grade info
        psets = ifcopenshell.util.element.get_psets(rebar, psets_only=True)
        for pset_values in psets.values():
            for key, val in pset_values.items():
                if "grade" in key.lower() and val:
                    return str(val)
        # Check material name
        material = ifcopenshell.util.element.get_material(rebar)
        if material and hasattr(material, "Name") and material.Name:
            return str(material.Name)
        return "unknown"

    @staticmethod
    def _compute_weight(diameter_m: float, length_m: float, count: int) -> float:
        """Compute rebar weight in kg.

        Formula: weight = (pi/4) * d^2 * L * density * count
        where d is diameter in metres, L is length in metres,
        and density is 7850 kg/m3 for steel.

        Args:
            diameter_m: Bar diameter in metres.
            length_m: Bar length in metres.
            count: Number of bars.

        Returns:
            Total weight in kg.
        """
        cross_section_area = (math.pi / 4.0) * diameter_m ** 2
        weight_kg = cross_section_area * length_m * STEEL_DENSITY_KG_M3 * count
        return weight_kg
