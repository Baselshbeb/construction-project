"""
IFC Parser Agent - extracts all building elements from an IFC file.

Coach Simple explains:
    "This is the first worker on the assembly line. You hand them a big
    box (the IFC file), and they open it, pull out every single piece,
    write down what each piece is (wall, column, door...), measure it,
    note its material, and write it all on the clipboard (ProjectState)."

This agent is mostly code-driven (not AI). It uses IfcOpenShell via
the IFCService to extract structured data from the IFC file.

Pipeline position: FIRST agent in the pipeline
Input: ProjectState with ifc_file_path
Output: ProjectState with building_info + parsed_elements filled in
"""

from __future__ import annotations

from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.project import BuildingInfo, ParsedElement, ProcessingStatus
from src.services.ifc_service import IFCService


class IFCParserAgent(BaseAgent):
    """Parses an IFC file and extracts all building elements."""

    def __init__(self):
        super().__init__(
            name="ifc_parser",
            description="Extracts building elements, quantities, and materials from IFC files",
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Parse the IFC file and populate state with building data.

        Steps:
        1. Open the IFC file
        2. Extract project/building metadata
        3. Extract all building elements with quantities & materials
        4. Convert to ParsedElement models
        5. Update state
        """
        self.log("Starting IFC parsing...")
        state["status"] = ProcessingStatus.PARSING
        state["current_step"] = "Parsing IFC file"

        ifc_path = state["ifc_file_path"]

        # Step 1: Open the file
        self.log(f"Opening: {ifc_path}")
        try:
            service = IFCService(ifc_path)
        except FileNotFoundError as e:
            self.log_error(str(e))
            state["errors"].append(str(e))
            state["status"] = ProcessingStatus.FAILED
            return state

        # Step 2: Extract building metadata
        self.log("Extracting building info...")
        project_info = service.get_project_info()
        storeys = service.get_storeys()

        building_info = BuildingInfo(
            project_name=project_info.get("project_name"),
            site_name=project_info.get("site_name"),
            building_name=project_info.get("building_name"),
            storeys=[s["name"] for s in storeys],
            schema_version=project_info.get("schema"),
            total_entities=project_info.get("total_entities", 0),
        )
        state["building_info"] = building_info.model_dump()

        self.log(
            f"Building: {building_info.building_name}, "
            f"{len(storeys)} storeys, "
            f"{building_info.total_entities} entities"
        )

        # Step 3: Extract all building elements
        self.log("Extracting building elements...")
        raw_elements, unknown_types = service.extract_all_elements()

        # Warn about unrecognized element types in the IFC file
        if unknown_types:
            unknown_summary = ", ".join(
                f"{t} ({c})" for t, c in sorted(unknown_types.items())
            )
            self.log_warning(f"Unrecognized IFC element types (skipped): {unknown_summary}")
            state["warnings"].append(
                f"IFC file contains unrecognized element types that were skipped: "
                f"{unknown_summary}. These elements are not included in the BOQ."
            )

        # Step 4: Convert to ParsedElement models
        parsed_elements = []
        failed_elements = state.get("failed_elements", [])
        skipped_elements = state.get("skipped_elements", [])

        for raw in raw_elements:
            try:
                # Validate quantities are numeric
                clean_quantities: dict[str, float] = {}
                for qname, qval in raw.get("quantities", {}).items():
                    try:
                        clean_quantities[qname] = float(qval)
                    except (TypeError, ValueError):
                        self.log_warning(
                            f"Non-numeric quantity '{qname}={qval}' in element "
                            f"{raw.get('ifc_id')} — skipping this quantity"
                        )

                # Filter out "Unknown" materials
                raw_materials = raw.get("materials", [])
                clean_materials = [
                    m for m in raw_materials if m and m != "Unknown"
                ]
                if raw_materials and not clean_materials:
                    skipped_elements.append({
                        "ifc_id": raw.get("ifc_id"),
                        "ifc_type": raw.get("ifc_type"),
                        "reason": "No material info in IFC (was 'Unknown')",
                    })

                element = ParsedElement(
                    ifc_id=raw["ifc_id"],
                    ifc_type=raw["ifc_type"],
                    name=raw.get("name"),
                    storey=raw.get("storey"),
                    properties=raw.get("properties", {}),
                    quantities=clean_quantities,
                    materials=clean_materials,
                    is_external=raw.get("is_external"),
                )
                parsed_elements.append(element)
            except Exception as e:
                self.log_warning(
                    f"Skipping element {raw.get('ifc_id')}: {e}"
                )
                failed_elements.append({
                    "ifc_id": raw.get("ifc_id"),
                    "ifc_type": raw.get("ifc_type"),
                    "reason": str(e),
                })

        # Step 5: Update state
        state["parsed_elements"] = [e.model_dump() for e in parsed_elements]
        state["failed_elements"] = failed_elements
        state["skipped_elements"] = skipped_elements

        if failed_elements:
            state["warnings"].append(
                f"{len(failed_elements)} element(s) failed during parsing "
                f"and were excluded from the BOQ."
            )

        # Log summary
        type_counts: dict[str, int] = {}
        for elem in parsed_elements:
            type_counts[elem.ifc_type] = type_counts.get(elem.ifc_type, 0) + 1

        self.log(f"Parsed {len(parsed_elements)} elements:")
        for ifc_type, count in sorted(type_counts.items()):
            self.log(f"  {ifc_type}: {count}")

        state["processing_log"].append(
            f"IFC Parser: extracted {len(parsed_elements)} elements "
            f"from {building_info.building_name}"
        )

        return state
