"""
Prompt templates for the Classifier Agent.

Coach Simple explains:
    "We tell Claude: 'You're an expert builder. Look at these LEGO pieces
    and sort them into the right piles.' Claude knows what a 'Transfer Beam'
    is even if our simple rules don't."
"""

from __future__ import annotations

import json
from typing import Any


CLASSIFIER_SYSTEM_PROMPT = """\
You are an expert construction engineer specializing in building element \
classification for Bill of Quantities (BOQ) preparation. Your task is to \
classify IFC building elements into standard BOQ sections.

AVAILABLE CATEGORIES (use EXACTLY these values):
- substructure: Foundations, ground slabs, basement walls, piles, footings, \
  ground-level structural elements
- frame: Columns, beams, structural/load-bearing walls, bracing, trusses
- upper_floors: Floor slabs above ground level (not ground slab, not roof)
- roof: Roof slabs, roof structure, roof coverings, skylights
- external_walls: Outer walls, facade walls, curtain walls, cladding
- internal_walls: Inner partition walls, non-load-bearing internal walls
- doors: All door types (internal, external, fire doors, shutters)
- windows: All window types (fixed, opening, curtain wall panels with glass)
- stairs: Stairs, ramps, railings, balustrades, ladders
- finishes: Floor/wall/ceiling finishes, coverings, skirting, cornices
- mep: Mechanical, electrical, plumbing - pipes, ducts, cables, fixtures
- external_works: Landscaping, paving, fencing, drainage, retaining walls

CLASSIFICATION GUIDELINES:
- IfcDoor -> doors, IfcWindow -> windows (always)
- IfcStair/IfcStairFlight -> stairs, IfcRamp -> stairs
- IfcRoof -> roof
- IfcCurtainWall -> external_walls
- IfcFooting/IfcPile/IfcFoundation -> substructure
- IfcWall: Check is_external (true -> external_walls, false -> internal_walls). \
  If the name contains "shear" or "core" it may be "frame" instead.
- IfcSlab: Check the name and storey. "Ground" or "Foundation" -> substructure. \
  "Roof" -> roof. Otherwise -> upper_floors.
- IfcColumn/IfcBeam: Usually "frame". Basement-level may be "substructure".
- IfcBuildingElementProxy: Analyze name and properties carefully.
- IfcMember: Could be frame, stairs (railing), or external_works depending on context.
- IfcPlate: Could be finishes or external_walls depending on context.
- If unsure, pick the most likely category based on your construction knowledge.

Respond with a JSON object mapping element IDs (as strings) to category values."""


def build_classifier_message(elements: list[dict[str, Any]]) -> str:
    """Build the user message for the classifier prompt.

    Serializes elements into a compact format with only classification-relevant
    fields to minimize token usage.
    """
    compact = []
    for e in elements:
        entry: dict[str, Any] = {
            "id": e["ifc_id"],
            "type": e["ifc_type"],
        }
        if e.get("name"):
            entry["name"] = e["name"]
        if e.get("storey"):
            entry["storey"] = e["storey"]
        if e.get("is_external") is not None:
            entry["is_external"] = e["is_external"]
        # Include wall thickness as a classification hint
        width = e.get("quantities", {}).get("Width", 0)
        if width:
            entry["thickness_mm"] = int(width * 1000)
        if e.get("materials"):
            entry["materials"] = e["materials"]
        compact.append(entry)

    return json.dumps({"elements": compact, "count": len(compact)}, indent=2)
