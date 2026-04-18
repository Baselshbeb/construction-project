"""
Project-level data models - the shared state that flows through all agents.

Coach Simple explains:
    "Think of ProjectState like a clipboard that gets passed from worker to worker
    on a construction site. The first worker (Parser) writes what elements the
    building has. The next worker (Calculator) adds the measurements. The next
    (Material Mapper) adds the shopping list. Each worker reads what the previous
    ones wrote and adds their own part."

All agents read from and write to ProjectState. It's the single source of truth.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ElementCategory(str, Enum):
    """Categories for organizing building elements in the BOQ.

    Coach Simple: "Like sorting LEGO pieces into labeled boxes -
    all walls go in one box, all floors in another, etc."
    """

    SUBSTRUCTURE = "substructure"           # Foundations, ground slab, basement
    FRAME = "frame"                         # Columns, beams, structural walls
    UPPER_FLOORS = "upper_floors"           # Floor slabs above ground
    ROOF = "roof"                           # Roof structure and covering
    EXTERNAL_WALLS = "external_walls"       # Outer walls
    INTERNAL_WALLS = "internal_walls"       # Inner partition walls
    DOORS = "doors"                         # All door types
    WINDOWS = "windows"                     # All window types
    STAIRS = "stairs"                       # Stairs and ramps
    FINISHES = "finishes"                   # Floor, wall, ceiling finishes
    MEP = "mep"                             # Mechanical, electrical, plumbing
    EXTERNAL_WORKS = "external_works"       # Landscaping, paving, fencing


class ProcessingStatus(str, Enum):
    """Status of the processing pipeline."""

    PENDING = "pending"
    PARSING = "parsing"
    CLASSIFYING = "classifying"
    CALCULATING = "calculating"
    MAPPING_MATERIALS = "mapping_materials"
    GENERATING_BOQ = "generating_boq"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class ParsedElement(BaseModel):
    """A single building element extracted from the IFC file.

    Coach Simple: "Each LEGO piece from the box, with a label
    telling you its name, size, color, and which pile it belongs to."
    """

    ifc_id: int = Field(description="Unique ID of this element in the IFC file")
    ifc_type: str = Field(description="IFC class name, e.g. 'IfcWall', 'IfcSlab'")
    name: Optional[str] = Field(default=None, description="Human-readable name")
    storey: Optional[str] = Field(default=None, description="Which floor this element is on")
    properties: dict[str, Any] = Field(default_factory=dict, description="Property sets (Pset)")
    quantities: dict[str, float] = Field(
        default_factory=dict,
        description="Quantity sets (Qto) - e.g. {'Length': 5.0, 'Height': 3.0}",
    )
    materials: list[str] = Field(default_factory=list, description="Material names from IFC")
    material_layers: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Material layers with thicknesses [{name, thickness_m, is_ventilated}]",
    )
    openings: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-wall openings from IfcRelVoidsElement [{opening_id, width, height, area}]",
    )
    quantity_source: str = Field(
        default="qto",
        description="Source of quantity data: 'qto', 'geometry', 'mixed', or 'none'",
    )
    is_external: Optional[bool] = Field(default=None, description="Is this an external element?")
    category: Optional[ElementCategory] = Field(
        default=None, description="BOQ category (set by Classifier Agent)"
    )

    model_config = {"frozen": False}


class BuildingInfo(BaseModel):
    """High-level information about the building."""

    project_name: Optional[str] = None
    site_name: Optional[str] = None
    building_name: Optional[str] = None
    storeys: list[str] = Field(default_factory=list)
    schema_version: Optional[str] = None
    total_entities: int = 0


class ProjectState(BaseModel):
    """The central state object that flows through the entire agent pipeline.

    Coach Simple: "This is the master clipboard. Every agent reads it,
    does their job, writes their results back, and passes it to the next agent."
    """

    # --- Input ---
    ifc_file_path: str = Field(description="Path to the uploaded IFC file")
    project_config: dict[str, Any] = Field(
        default_factory=dict,
        description="User configuration (building type, region, detail level)",
    )

    # --- After IFC Parsing ---
    building_info: Optional[BuildingInfo] = Field(
        default=None, description="High-level building metadata"
    )
    parsed_elements: list[ParsedElement] = Field(
        default_factory=list, description="All building elements extracted from IFC"
    )

    # --- After Classification ---
    classified_elements: dict[str, list[int]] = Field(
        default_factory=dict,
        description="Category -> list of element ifc_ids",
    )

    # --- After Quantity Calculation ---
    calculated_quantities: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Calculated quantities for each element",
    )

    # --- After Material Mapping ---
    material_list: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Complete list of materials with quantities",
    )

    # --- After BOQ Generation ---
    boq_data: Optional[dict[str, Any]] = Field(
        default=None, description="Structured BOQ data"
    )
    boq_file_paths: dict[str, str] = Field(
        default_factory=dict,
        description="Format -> file path for generated reports",
    )

    # --- Validation ---
    validation_report: Optional[dict[str, Any]] = Field(
        default=None, description="Validation results"
    )
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    # --- Metadata ---
    status: ProcessingStatus = Field(default=ProcessingStatus.PENDING)
    current_step: str = Field(default="")
    processing_log: list[str] = Field(default_factory=list)

    model_config = {"frozen": False}
