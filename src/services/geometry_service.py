"""
Geometry Service - computes quantities from 3D IFC geometry.

This service provides a fallback when IFC Quantity Sets (Qto) are missing
or incomplete. It uses IfcOpenShell's geometry kernel to tessellate 3D
shapes and compute volumes, areas, and bounding box dimensions directly
from the model geometry.

Usage:
    from src.services.geometry_service import GeometryService
    geo = GeometryService(ifc_model)
    quantities = geo.compute_element_geometry(element)
    # Returns: {"volume": 6.0, "area": 30.0, "footprint_area": 2.0, ...}
"""

from __future__ import annotations

from typing import Any, Optional

import ifcopenshell
import ifcopenshell.geom

from src.utils.logger import get_logger

logger = get_logger("geometry_service")

# Try importing shape utilities — may not be available in all builds
try:
    import ifcopenshell.util.shape as shape_util
    HAS_SHAPE_UTIL = True
except ImportError:
    HAS_SHAPE_UTIL = False
    logger.warning("ifcopenshell.util.shape not available; geometry fallback disabled")


class GeometryService:
    """Computes element quantities from 3D IFC geometry.

    Acts as a fallback when Qto property sets are missing. Caches
    computed results per element ID to avoid redundant geometry processing.
    """

    def __init__(self, model: ifcopenshell.file):
        self.model = model
        self._cache: dict[int, dict[str, float]] = {}
        self._settings = ifcopenshell.geom.settings()
        # Use world coordinates so bounding boxes are in the global frame
        self._settings.set(self._settings.USE_WORLD_COORDS, True)
        self._failures: list[dict[str, Any]] = []

    @property
    def failures(self) -> list[dict[str, Any]]:
        """Elements that failed geometry computation."""
        return list(self._failures)

    def compute_element_geometry(self, element) -> dict[str, float]:
        """Compute quantities from an element's 3D geometry.

        Returns a dict with keys matching standard Qto names so the values
        can be merged directly into the element's quantities dict.

        Returns an empty dict if geometry is unavailable or computation fails.
        """
        eid = element.id()

        # Check cache
        if eid in self._cache:
            return self._cache[eid]

        # Skip if no geometry module
        if not HAS_SHAPE_UTIL:
            return {}

        # Skip if element has no representation
        if not getattr(element, "Representation", None):
            return {}

        result: dict[str, float] = {}

        try:
            shape = ifcopenshell.geom.create_shape(self._settings, element)
            geom = shape.geometry

            # Volume
            volume = shape_util.get_volume(geom)
            if volume and volume > 0:
                result["GrossVolume"] = volume

            # Total surface area
            area = shape_util.get_area(geom)
            if area and area > 0:
                result["GrossSurfaceArea"] = area

            # Footprint area (projection onto XY plane)
            try:
                footprint = shape_util.get_footprint_area(geom)
                if footprint and footprint > 0:
                    result["FootprintArea"] = footprint
            except Exception:
                pass

            # Side area (largest vertical face area — useful for walls)
            try:
                side_area = shape_util.get_side_area(geom)
                if side_area and side_area > 0:
                    result["GrossSideArea"] = side_area
                    result["GrossArea"] = side_area
            except Exception:
                pass

            # Top area (useful for slabs, roofs)
            try:
                top_area = shape_util.get_top_area(geom)
                if top_area and top_area > 0:
                    result["TopArea"] = top_area
            except Exception:
                pass

            # Outer surface area (useful for columns, beams)
            try:
                outer = shape_util.get_outer_surface_area(geom)
                if outer and outer > 0:
                    result["OuterSurfaceArea"] = outer
            except Exception:
                pass

            # Bounding box for dimensional quantities
            try:
                bbox = shape_util.get_bbox(geom)
                if bbox is not None:
                    # bbox is typically [[min_x, min_y, min_z], [max_x, max_y, max_z]]
                    min_pt = bbox[0]
                    max_pt = bbox[1]
                    dx = abs(max_pt[0] - min_pt[0])
                    dy = abs(max_pt[1] - min_pt[1])
                    dz = abs(max_pt[2] - min_pt[2])

                    # Assign to standard quantity names based on element type
                    ifc_type = element.is_a()
                    if ifc_type in ("IfcWall", "IfcWallStandardCase"):
                        # Wall: longest horizontal = Length, vertical = Height, shortest = Width
                        dims = sorted([dx, dy], reverse=True)
                        result.setdefault("Length", dims[0])
                        result.setdefault("Height", dz)
                        result.setdefault("Width", dims[1])
                    elif ifc_type == "IfcSlab":
                        # Slab: two horizontal dims, vertical = Depth
                        result.setdefault("Length", max(dx, dy))
                        result.setdefault("Width", min(dx, dy))
                        result.setdefault("Depth", dz)
                        result.setdefault("Area", dx * dy)
                    elif ifc_type in ("IfcColumn",):
                        # Column: vertical = Height, horizontal = cross-section
                        result.setdefault("Height", dz)
                        result.setdefault("CrossSectionArea", dx * dy)
                    elif ifc_type in ("IfcBeam",):
                        # Beam: longest horizontal = Length
                        result.setdefault("Length", max(dx, dy))
                        result.setdefault("CrossSectionArea", min(dx, dy) * dz)
                    elif ifc_type in ("IfcDoor", "IfcWindow"):
                        result.setdefault("Width", max(dx, dy))
                        result.setdefault("Height", dz)
                        result.setdefault("Area", max(dx, dy) * dz)
                    else:
                        # Generic: store all dimensions
                        result.setdefault("Length", max(dx, dy))
                        result.setdefault("Height", dz)
                        result.setdefault("Width", min(dx, dy))
            except Exception:
                pass

            if result:
                logger.debug(
                    f"Geometry computed for {element.is_a()} #{eid}: "
                    f"{', '.join(f'{k}={v:.3f}' for k, v in result.items())}"
                )

        except Exception as e:
            # Geometry computation failed — this is expected for some elements
            # (e.g., NULL representation, unsupported geometry types)
            self._failures.append({
                "ifc_id": eid,
                "ifc_type": element.is_a(),
                "error": str(e),
            })
            logger.debug(f"Geometry fallback unavailable for {element.is_a()} #{eid}: {e}")

        self._cache[eid] = result
        return result

    def compute_all_elements(
        self, elements: list, only_missing_qto: bool = True,
    ) -> dict[int, dict[str, float]]:
        """Compute geometry for multiple elements.

        Args:
            elements: List of IFC elements.
            only_missing_qto: If True, only compute for elements that lack
                Qto data. If False, compute for all elements.

        Returns:
            Dict mapping element ID to computed quantities.
        """
        import ifcopenshell.util.element

        results: dict[int, dict[str, float]] = {}
        computed = 0
        skipped = 0

        for elem in elements:
            if only_missing_qto:
                # Check if element already has Qto quantities
                qtos = ifcopenshell.util.element.get_psets(elem, qtos_only=True)
                has_qto = any(
                    isinstance(v, (int, float)) and v > 0
                    for qto in qtos.values()
                    for k, v in qto.items()
                    if k != "id"
                )
                if has_qto:
                    skipped += 1
                    continue

            result = self.compute_element_geometry(elem)
            if result:
                results[elem.id()] = result
                computed += 1

        logger.info(
            f"Geometry computed for {computed} elements, "
            f"skipped {skipped} (had Qto), "
            f"{len(self._failures)} failures"
        )
        return results
