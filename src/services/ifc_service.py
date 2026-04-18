"""
IFC Service - wrapper around IfcOpenShell for common operations.

Coach Simple explains:
    "IfcOpenShell is the tool that reads IFC files, but it speaks a very
    technical language. This service is like a translator - it takes the
    complicated IfcOpenShell commands and wraps them in simple functions
    like 'get all walls' or 'get this wall's measurements'."

This service is used by the IFC Parser Agent and other agents that need
to read building data from IFC files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.unit

from src.utils.logger import get_logger

logger = get_logger("ifc_service")

# All building element types we care about
BUILDING_ELEMENT_TYPES = [
    "IfcWall",
    "IfcWallStandardCase",
    "IfcSlab",
    "IfcColumn",
    "IfcBeam",
    "IfcDoor",
    "IfcWindow",
    "IfcStair",
    "IfcStairFlight",
    "IfcRamp",
    "IfcRampFlight",
    "IfcRoof",
    "IfcCovering",
    "IfcCurtainWall",
    "IfcRailing",
    "IfcFooting",
    "IfcPile",
    "IfcBuildingElementProxy",
]


class IFCService:
    """Wrapper around IfcOpenShell for reading building data from IFC files.

    Usage:
        service = IFCService("path/to/building.ifc")
        walls = service.get_elements_by_type("IfcWall")
        for wall in walls:
            quantities = service.get_element_quantities(wall)
    """

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"IFC file not found: {self.file_path}")

        logger.info(f"Opening IFC file: {self.file_path.name}")
        self.model = ifcopenshell.open(str(self.file_path))
        logger.info(
            f"Loaded: schema={self.model.schema}, "
            f"entities={len(list(self.model))}"
        )

    # ------------------------------------------------------------------
    # Project & Building info
    # ------------------------------------------------------------------

    def get_project_info(self) -> dict[str, Any]:
        """Get high-level project metadata."""
        info: dict[str, Any] = {
            "schema": self.model.schema,
            "total_entities": len(list(self.model)),
        }

        projects = self.model.by_type("IfcProject")
        if projects:
            info["project_name"] = projects[0].Name

        sites = self.model.by_type("IfcSite")
        if sites:
            info["site_name"] = sites[0].Name

        buildings = self.model.by_type("IfcBuilding")
        if buildings:
            info["building_name"] = buildings[0].Name

        return info

    def get_storeys(self) -> list[dict[str, Any]]:
        """Get all building storeys with their elevations."""
        storeys = []
        for storey in self.model.by_type("IfcBuildingStorey"):
            storeys.append({
                "name": storey.Name,
                "elevation": storey.Elevation or 0.0,
                "ifc_id": storey.id(),
            })
        # Sort by elevation
        storeys.sort(key=lambda s: s["elevation"])
        return storeys

    # ------------------------------------------------------------------
    # Element retrieval
    # ------------------------------------------------------------------

    def get_elements_by_type(self, ifc_type: str) -> list:
        """Get all elements of a specific IFC type."""
        try:
            return list(self.model.by_type(ifc_type))
        except RuntimeError:
            # Type doesn't exist in this schema
            return []

    def get_all_building_elements(self) -> list:
        """Get all building elements of recognized types."""
        elements = []
        seen_ids = set()
        for ifc_type in BUILDING_ELEMENT_TYPES:
            for elem in self.get_elements_by_type(ifc_type):
                eid = elem.id()
                if eid not in seen_ids:
                    seen_ids.add(eid)
                    elements.append(elem)
        return elements

    def count_elements_by_type(self) -> dict[str, int]:
        """Count elements grouped by IFC type."""
        counts = {}
        for ifc_type in BUILDING_ELEMENT_TYPES:
            elems = self.get_elements_by_type(ifc_type)
            if elems:
                counts[ifc_type] = len(elems)
        return counts

    # ------------------------------------------------------------------
    # Element properties & quantities
    # ------------------------------------------------------------------

    def get_element_quantities(self, element) -> dict[str, float]:
        """Get all quantity set (Qto) values for an element.

        Returns dict like: {"Length": 10.0, "Height": 3.0, "GrossArea": 30.0, ...}
        """
        all_quantities: dict[str, float] = {}
        qtos = ifcopenshell.util.element.get_psets(element, qtos_only=True)
        for qto_name, quantities in qtos.items():
            for key, value in quantities.items():
                if key == "id":
                    continue
                if isinstance(value, (int, float)):
                    all_quantities[key] = float(value)
        return all_quantities

    def get_element_properties(self, element) -> dict[str, Any]:
        """Get all property set (Pset) values for an element.

        Returns dict like: {"IsExternal": True, "FireRating": "2HR", ...}
        """
        all_properties: dict[str, Any] = {}
        psets = ifcopenshell.util.element.get_psets(element, psets_only=True)
        for pset_name, properties in psets.items():
            for key, value in properties.items():
                if key == "id":
                    continue
                all_properties[key] = value
        return all_properties

    def get_element_material(self, element) -> list[str]:
        """Get material name(s) for an element.

        Returns a list because elements can have multiple material layers.
        """
        materials = []
        material = ifcopenshell.util.element.get_material(element)
        if material is None:
            return materials

        # Single material
        if hasattr(material, "Name") and material.Name:
            materials.append(material.Name)

        # Material layer set (e.g., layered wall: concrete + insulation + plaster)
        if material.is_a("IfcMaterialLayerSetUsage") or material.is_a("IfcMaterialLayerSet"):
            layer_set = material
            if material.is_a("IfcMaterialLayerSetUsage"):
                layer_set = material.ForLayerSet
            if hasattr(layer_set, "MaterialLayers"):
                for layer in layer_set.MaterialLayers:
                    if layer.Material and layer.Material.Name:
                        materials.append(layer.Material.Name)

        # Material list (multiple discrete materials)
        if material.is_a("IfcMaterialList"):
            for mat in material.Materials:
                if mat.Name:
                    materials.append(mat.Name)

        return materials

    def get_element_container(self, element) -> Optional[str]:
        """Get the storey/container name for an element."""
        container = ifcopenshell.util.element.get_container(element)
        if container:
            return container.Name
        return None

    def get_element_type_name(self, element) -> Optional[str]:
        """Get the type name of an element (e.g., 'Basic Wall: 200mm Concrete')."""
        elem_type = ifcopenshell.util.element.get_type(element)
        if elem_type and hasattr(elem_type, "Name"):
            return elem_type.Name
        return None

    # ------------------------------------------------------------------
    # Full element extraction (combines all the above)
    # ------------------------------------------------------------------

    def extract_element_data(
        self, element, geometry_service=None,
    ) -> dict[str, Any]:
        """Extract all relevant data from a single building element.

        This is the main method the IFC Parser Agent uses.
        Combines quantities, properties, materials, location, and optionally
        geometry-derived quantities as a fallback.

        Args:
            element: The IFC element to extract data from.
            geometry_service: Optional GeometryService for 3D geometry fallback
                when Qto data is missing.
        """
        ifc_type = element.is_a()

        qto_quantities = self.get_element_quantities(element)

        # Track data source for confidence scoring
        quantity_source = "qto" if qto_quantities else "none"

        # Geometry fallback: fill missing quantities from 3D geometry
        if geometry_service:
            has_critical = any(
                qto_quantities.get(k, 0) > 0
                for k in ("GrossVolume", "NetVolume", "GrossArea", "NetArea",
                          "Area", "Length", "Height")
            )
            if not has_critical:
                geo_quantities = geometry_service.compute_element_geometry(element)
                if geo_quantities:
                    # Merge geometry values into quantities (Qto takes priority)
                    for key, val in geo_quantities.items():
                        qto_quantities.setdefault(key, val)
                    quantity_source = "geometry" if not has_critical else "mixed"

        data = {
            "ifc_id": element.id(),
            "ifc_type": ifc_type,
            "name": element.Name,
            "storey": self.get_element_container(element),
            "type_name": self.get_element_type_name(element),
            "quantities": qto_quantities,
            "quantity_source": quantity_source,
            "properties": self.get_element_properties(element),
            "materials": self.get_element_material(element),
        }

        # Extract is_external from properties
        data["is_external"] = data["properties"].get("IsExternal", None)

        # For doors and windows, add overall dimensions
        if ifc_type in ("IfcDoor", "IfcWindow"):
            if hasattr(element, "OverallWidth") and element.OverallWidth:
                data["quantities"].setdefault("Width", element.OverallWidth)
            if hasattr(element, "OverallHeight") and element.OverallHeight:
                data["quantities"].setdefault("Height", element.OverallHeight)

        # Extract per-wall openings (for Phase 2 per-wall deduction)
        if ifc_type in ("IfcWall", "IfcWallStandardCase"):
            data["openings"] = self.get_wall_openings(element)

        # Extract material layers with thicknesses (for Phase 2)
        data["material_layers"] = self.get_material_layers(element)

        return data

    def get_wall_openings(self, wall_element) -> list[dict[str, Any]]:
        """Get all openings (doors/windows) in a wall via IfcRelVoidsElement.

        Returns a list of opening dicts with area, width, height, and the
        type of filling (door/window) if present.
        """
        openings: list[dict[str, Any]] = []

        if not hasattr(wall_element, "HasOpenings"):
            return openings

        for rel_void in wall_element.HasOpenings:
            opening_elem = rel_void.RelatedOpeningElement
            if not opening_elem:
                continue

            opening_data: dict[str, Any] = {
                "opening_id": opening_elem.id(),
                "width": 0,
                "height": 0,
                "area": 0,
                "filling_type": None,
            }

            # Get opening dimensions from Qto
            oqto = self.get_element_quantities(opening_elem)
            opening_data["width"] = oqto.get("Width", 0)
            opening_data["height"] = oqto.get("Height", 0)
            opening_data["area"] = oqto.get("Area", 0)

            if not opening_data["area"] and opening_data["width"] and opening_data["height"]:
                opening_data["area"] = opening_data["width"] * opening_data["height"]

            # Check what fills the opening (door or window)
            if hasattr(opening_elem, "HasFillings"):
                for fill_rel in opening_elem.HasFillings:
                    filling = fill_rel.RelatedBuildingElement
                    if filling:
                        opening_data["filling_type"] = filling.is_a()
                        # Use filling dimensions if opening dimensions are missing
                        if not opening_data["area"]:
                            fqto = self.get_element_quantities(filling)
                            w = fqto.get("Width", 0)
                            h = fqto.get("Height", 0)
                            if w and h:
                                opening_data["width"] = w
                                opening_data["height"] = h
                                opening_data["area"] = w * h

            if opening_data["area"] > 0:
                openings.append(opening_data)

        return openings

    def get_material_layers(self, element) -> list[dict[str, Any]]:
        """Get material layers with thicknesses for composite elements.

        Returns a list of layer dicts with name, thickness (in metres),
        and whether the layer is ventilated (cavity).
        """
        layers: list[dict[str, Any]] = []

        material = ifcopenshell.util.element.get_material(element)
        if material is None:
            return layers

        layer_set = None
        if material.is_a("IfcMaterialLayerSetUsage"):
            layer_set = material.ForLayerSet
        elif material.is_a("IfcMaterialLayerSet"):
            layer_set = material

        if layer_set and hasattr(layer_set, "MaterialLayers"):
            for layer in layer_set.MaterialLayers:
                layer_data: dict[str, Any] = {
                    "name": layer.Material.Name if layer.Material else "Unknown",
                    "thickness_m": (layer.LayerThickness or 0) / 1000.0,
                    "is_ventilated": getattr(layer, "IsVentilated", False) or False,
                }
                layers.append(layer_data)

        return layers

    def discover_element_types(self) -> dict[str, int]:
        """Find ALL element types in the IFC file, including unrecognized ones.

        Returns a dict of {ifc_type: count} for all IfcElement subtypes.
        """
        all_types: dict[str, int] = {}
        try:
            for entity in self.model.by_type("IfcElement"):
                type_name = entity.is_a()
                all_types[type_name] = all_types.get(type_name, 0) + 1
        except Exception as e:
            logger.warning(f"Element type discovery failed: {e}")
        return all_types

    def get_unknown_element_types(self) -> dict[str, int]:
        """Return element types present in the file but NOT in our recognized list."""
        all_types = self.discover_element_types()
        known = set(BUILDING_ELEMENT_TYPES)
        return {t: c for t, c in all_types.items() if t not in known}

    def extract_all_elements(self, geometry_service=None) -> tuple:
        """Extract data from ALL building elements.

        Args:
            geometry_service: Optional GeometryService for 3D geometry
                fallback when Qto data is missing.

        Returns:
            Tuple of (extracted_elements, unknown_types).
        """
        elements = self.get_all_building_elements()
        logger.info(f"Extracting data from {len(elements)} building elements")

        # Warn about unknown element types in the file
        unknown = self.get_unknown_element_types()
        if unknown:
            unknown_summary = ", ".join(f"{t}({c})" for t, c in sorted(unknown.items()))
            logger.warning(
                f"IFC file contains unrecognized element types: {unknown_summary}. "
                f"These elements will be skipped. Consider adding them to BUILDING_ELEMENT_TYPES."
            )

        extracted = []
        qto_count = 0
        geo_count = 0
        for element in elements:
            try:
                data = self.extract_element_data(element, geometry_service)
                extracted.append(data)
                # Track quantity sources
                src = data.get("quantity_source", "none")
                if src == "qto":
                    qto_count += 1
                elif src in ("geometry", "mixed"):
                    geo_count += 1
            except Exception as e:
                logger.warning(
                    f"Failed to extract element {element.id()} "
                    f"({element.is_a()}): {e}"
                )

        logger.info(
            f"Successfully extracted {len(extracted)} elements "
            f"(Qto: {qto_count}, geometry fallback: {geo_count})"
        )
        return extracted, unknown
