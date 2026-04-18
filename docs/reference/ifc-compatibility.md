# IFC Compatibility

This document details which IFC schemas, element types, and BIM authoring tools are supported by Metraj, along with known limitations and unit handling.

---

## Supported IFC Schemas

| Schema | Status | Notes |
|---|---|---|
| **IFC2x3** | Fully supported | The most widely used IFC schema. All major BIM tools export this format. Uses `IfcWallStandardCase` for simple walls. |
| **IFC4** | Fully supported | The newer schema with improved geometry and property definitions. `IfcWallStandardCase` is deprecated in favor of `IfcWall` with predefined types. |
| IFC4x3 | Partial | IfcOpenShell supports reading IFC4x3 files, but newer entity types specific to infrastructure (bridges, roads) are not in the recognized element list. |

Metraj validates that uploaded files begin with the `ISO-10303-21` magic bytes, which identifies them as valid IFC/STEP files.

---

## Supported Building Element Types

The following IFC element types are recognized and processed by Metraj. They are defined in `BUILDING_ELEMENT_TYPES` in `src/services/ifc_service.py`:

| IFC Type | Description | Quantities Extracted |
|---|---|---|
| `IfcWall` | Walls (all types) | Length, Height, Width, Gross/Net Area, Gross/Net Volume |
| `IfcWallStandardCase` | Simple walls (IFC2x3) | Same as IfcWall |
| `IfcSlab` | Floor slabs, ground slabs, roof slabs | Length, Width, Depth, Area, Volume, Perimeter |
| `IfcColumn` | Structural columns | Height, CrossSectionArea, Volume, OuterSurfaceArea |
| `IfcBeam` | Structural beams | Length, CrossSectionArea, Volume, OuterSurfaceArea |
| `IfcDoor` | Doors | OverallWidth, OverallHeight, Area |
| `IfcWindow` | Windows | OverallWidth, OverallHeight, Area |
| `IfcStair` | Staircases | Volume, Area |
| `IfcStairFlight` | Individual stair flights | Volume, Area |
| `IfcRamp` | Ramps | Volume, Area |
| `IfcRampFlight` | Individual ramp flights | Volume, Area |
| `IfcRoof` | Roof structures | Same as IfcSlab |
| `IfcCovering` | Floor, wall, or ceiling coverings | Area, Volume |
| `IfcCurtainWall` | Curtain walls (glass facades) | Area |
| `IfcRailing` | Railings and balustrades | Length |
| `IfcFooting` | Foundations (spread, strip, pad) | Volume, Area |
| `IfcPile` | Driven or bored piles | Volume, Area |
| `IfcBuildingElementProxy` | Generic/unclassified elements | All available quantities |

Elements of types not in this list are logged as warnings and skipped. The warning message includes the unknown type name and count, allowing users to assess if important elements were missed.

---

## Quantity Key Aliases

Different BIM authoring tools export quantity properties with different names. Metraj handles this through a quantity alias system defined in `QTY_ALIASES` in `src/agents/calculator.py`. The calculator tries each alias in order and returns the first non-zero value.

| Canonical Name | Aliases (tried in order) |
|---|---|
| Length | `Length`, `NominalLength` |
| Height | `Height`, `NominalHeight`, `OverallHeight` |
| Width | `Width`, `NominalWidth`, `Thickness`, `OverallWidth` |
| Depth | `Depth`, `NominalDepth`, `SlabDepth`, `Thickness` |
| GrossArea | `GrossArea`, `GrossSideArea`, `GrossWallArea`, `GrossFloorArea`, `GrossFootprintArea`, `Area` |
| NetArea | `NetArea`, `NetSideArea`, `NetWallArea`, `NetFloorArea`, `NetFootprintArea` |
| GrossVolume | `GrossVolume`, `Volume` |
| NetVolume | `NetVolume` |
| Perimeter | `Perimeter`, `GrossPerimeter` |
| CrossSectionArea | `CrossSectionArea`, `GrossCrossSectionArea` |
| OuterSurfaceArea | `OuterSurfaceArea`, `GrossOuterSurfaceArea`, `GrossSurfaceArea` |

If none of the aliases produce a value, derived quantities are computed where possible (e.g., area from length times height, volume from area times depth).

---

## Tested BIM Authoring Tools

| Tool | Export Format | Status | Notes |
|---|---|---|---|
| **Autodesk Revit** | IFC2x3, IFC4 | Tested | The most common source of IFC files. Uses standard Qto property sets. Wall thickness exported as `Width` or `Thickness`. |
| **Graphisoft ArchiCAD** | IFC2x3, IFC4 | Tested | Uses `NominalWidth`, `NominalHeight`, `NominalLength` for some quantities. Material layer sets are well-supported. |
| **FreeCAD** | IFC2x3, IFC4 | Tested | Open-source BIM tool. Quantity property naming varies by version. May require manual quantity set assignment. |
| **Tekla Structures** | IFC2x3, IFC4 | Expected compatible | Uses standard Qto naming. Not extensively tested but alias system should handle variations. |
| **Bentley OpenBuildings** | IFC2x3, IFC4 | Expected compatible | Standard IFC export. Quantity naming may use different conventions. |
| **Allplan** | IFC2x3, IFC4 | Expected compatible | Nemetschek IFC export follows standard conventions. |

---

## Unit Normalization

IFC files can contain quantities in various units. Metraj includes automatic unit detection and normalization:

### Millimetre Detection

For dimensional quantities (Width, Depth, Thickness), values greater than 10 are assumed to be in millimetres and are automatically converted to metres by dividing by 1000.

**Rationale:** A wall width of 200 is almost certainly 200mm (0.2m), not 200m. The threshold of 10 is conservative -- no common building element has a thickness exceeding 10 metres.

**Affected quantities:** Width, Depth, Thickness only. Length, Height, Area, and Volume values are taken as-is because these can legitimately exceed 10 in their natural units.

### Quantity Derivation

When quantities are not directly available from the IFC file, they are computed from available data:

- **Wall area:** Length x Height (if GrossArea is not in Qto)
- **Slab area:** Length x Width (if GrossArea is not in Qto)
- **Volume:** Area x Depth/Width (if GrossVolume is not in Qto)
- **Perimeter:** 2 x (Length + Width) for slabs (if not in Qto)
- **Column surface area:** Estimated from CrossSectionArea and Height using circumscribed circle perimeter

---

## Known Limitations

### Curved and Complex Geometry

Metraj relies on Qto (quantity takeoff) properties embedded in the IFC file for measurements. If the BIM tool did not compute and export these quantities, the calculator falls back to deriving them from basic dimensions (length, height, width). This works well for rectangular elements but may be inaccurate for:

- Curved walls (the calculator does not compute arc lengths)
- Tapered columns or beams
- Non-planar slabs
- Complex roof geometry

**Recommendation:** Ensure your BIM tool exports Qto property sets with pre-computed quantities for complex geometry.

### MEP Elements

Mechanical, electrical, and plumbing elements (`IfcDistributionElement`, `IfcFlowSegment`, etc.) are not in the recognized element type list. MEP elements in the IFC file will be reported as unknown types. MEP material estimation is not currently supported.

### Structural Analysis Data

Metraj does not read or use structural analysis results (load cases, stress values). Reinforcement quantities are estimated using standard kg/m3 ratios, not from actual rebar schedules.

### Material Layer Accuracy

The IFC material layer information (e.g., "200mm concrete + 50mm insulation + 15mm plaster") is read and passed to the AI as context. However, individual layer thicknesses are not used for quantity calculations -- the overall wall thickness from Qto is used instead.

### Large File Performance

IFC files exceeding 100 MB may take several minutes to parse. The IfcOpenShell library loads the entire file into memory, so very large files (500+ MB) may require significant RAM. The API enforces a 500 MB file size limit.

### Property Set Availability

The quality of the estimation depends heavily on the quality of the IFC export. If the BIM model was exported without quantity sets (Qto), many quantities will need to be derived from basic dimensions, which is less accurate. If the `IsExternal` property is not set, the classifier will use AI judgment to determine whether walls are external or internal.
