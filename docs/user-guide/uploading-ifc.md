# Uploading IFC Files

This guide is written for construction engineers and BIM coordinators who want to use Metraj to generate a Bill of Quantities from their building model.

---

## What Is an IFC File

IFC (Industry Foundation Classes) is an open international standard (ISO 16739) for exchanging building information between different software tools. An IFC file contains:

- The 3D geometry of every building element (walls, slabs, columns, beams, doors, windows, etc.)
- Properties of each element (material type, fire rating, whether it is external)
- Measured quantities (length, height, area, volume)
- Spatial structure (which floor each element belongs to)
- Material layer information (for multi-layer walls: concrete + insulation + plaster)

IFC files use the `.ifc` file extension and are plain text files in the STEP format. They can range from a few hundred kilobytes for a simple house to several hundred megabytes for a complex commercial building.

---

## Exporting IFC from Revit

1. Open your building model in Autodesk Revit
2. Go to **File > Export > IFC**
3. In the IFC Export dialog:
   - **IFC Version:** Select IFC2x3 Coordination View 2.0 or IFC4 Reference View
   - **File Type:** IFC (*.ifc)
   - Under **Property Sets:**
     - Check **Export Revit property sets**
     - Check **Export IFC common property sets** (this exports Pset_WallCommon, etc.)
   - Under **Quantity Sets:**
     - Check **Export base quantities** (this exports Qto_WallBaseQuantities, etc.)
   - Under **General:**
     - Check **Export element materials**
4. Choose a save location and click **Export**

**Important:** The "Export base quantities" option is essential. Without it, Metraj will need to derive quantities from basic dimensions, which is less accurate for complex geometry.

---

## Exporting IFC from ArchiCAD

1. Open your building model in Graphisoft ArchiCAD
2. Go to **File > Save As**
3. Select file type: **IFC Files (*.ifc)**
4. Click **Options** to open the IFC Translator settings:
   - Choose an appropriate translator (e.g., "General Translator" or "Coordination View 2.0")
   - Under **Data Conversion:**
     - Ensure property sets are exported (Pset and Qto)
     - Enable material export
5. Click **Save**

ArchiCAD uses `NominalWidth`, `NominalHeight`, and `NominalLength` for some quantities. Metraj's quantity alias system handles these automatically.

---

## Exporting IFC from FreeCAD

1. Open your building model in FreeCAD (BIM Workbench)
2. Select the building or site object in the model tree
3. Go to **File > Export** or **Arch > IFC Export**
4. In the export dialog:
   - Choose IFC2x3 or IFC4 schema
   - Enable quantity export if the option is available
5. Save the file

FreeCAD IFC export quality depends on the version and how the model was built. Models created with the BIM workbench tools (Arch Wall, Arch Slab, etc.) export most cleanly. For best results, ensure your model uses proper BIM objects rather than generic shapes.

---

## File Requirements

| Requirement | Details |
|---|---|
| File extension | `.ifc` (case-insensitive) |
| File format | Valid IFC/STEP format (must start with `ISO-10303-21`) |
| Maximum file size | 500 MB |
| IFC schema | IFC2x3 or IFC4 |
| Recommended exports | Quantity sets (Qto), property sets (Pset), materials |

---

## Tips for Better Results

### Include Quantity Sets

The single most important factor for accurate estimation is having quantity sets (Qto) in your IFC file. These are pre-computed quantities like GrossArea, NetArea, GrossVolume that your BIM tool calculates from the 3D geometry. Without them, Metraj derives quantities from basic dimensions, which is approximate.

### Set the IsExternal Property

For walls, the `IsExternal` property determines whether the wall is treated as an exterior wall (with external plaster, paint, and potentially insulation) or an interior wall (with plaster and paint on both sides). If this property is not set, the AI classifier will make its best judgment based on the wall name and position.

### Assign Materials

If your BIM model has materials assigned to elements (e.g., "Concrete C25/30", "Clay Brick"), this information is passed to the AI material mapper as context, resulting in more accurate material selections.

### Use Standard Element Types

Use proper BIM element types (Wall, Slab, Column, Beam) rather than generic geometry (Extrusion, Mesh). Metraj recognizes 18 specific IFC element types. Generic geometry exported as `IfcBuildingElementProxy` will still be processed, but with less specificity.

### Organize by Storey

Assign elements to their correct building storeys. Metraj uses storey information for:
- Calculating actual opening ratios per floor (doors + windows as a percentage of wall area)
- Identifying foundation-level elements for substructure classification
- Detecting missing elements per storey during validation

---

## What Happens After Upload

When you upload an IFC file, the following pipeline stages execute automatically:

### Stage 1: IFC Parsing (5-30 seconds)

The system reads your IFC file using IfcOpenShell and extracts every building element. For each element, it reads the element type, name, storey, quantities, properties, and materials. You will see the element count in the progress update.

### Stage 2: Classification (3-10 seconds)

Claude AI examines each element and assigns it to a BOQ section (substructure, frame, external walls, internal walls, etc.). This determines the organization of your final BOQ.

### Stage 3: Quantity Calculation (1-3 seconds)

The system computes construction-relevant quantities from the raw IFC data. For walls, this includes gross area, net area (with actual opening deductions), volume, and face areas for finishing. For slabs, it includes area, volume, perimeter, and formwork area.

### Stage 4: Material Mapping (5-15 seconds)

Claude AI acts as a virtual quantity surveyor, determining all construction materials needed for each element. This includes structural materials (concrete, steel, formwork), finishes (plaster, paint, tiles), and protective materials (waterproofing, insulation). Industry-standard waste factors are applied.

### Stage 5: BOQ Generation (1-2 seconds)

The materials are organized into a structured Bill of Quantities with numbered sections and items. Section titles are generated in your selected language.

### Stage 6: Validation (3-8 seconds)

Eight arithmetic checks verify the output (no negative quantities, reasonable concrete ratios, etc.), followed by an AI engineering review that looks for missing materials, unusual quantities, or construction logic issues.

### Export (1-3 seconds)

The BOQ is exported as Excel (.xlsx), CSV, and JSON files. The Excel file includes three sheets: the main BOQ, a material summary, and an audit trail.

### Progress Bar

The web interface shows a progress bar that updates after each stage. The progress percentages shown are:
- IFC Parsing: 17%
- Classification: 33%
- Quantity Calculation: 50%
- Material Mapping: 67%
- BOQ Generation: 83%
- Validation/Export: 95-100%

Total processing time for a typical residential building (50-200 elements) is 30-90 seconds. Larger commercial buildings may take 2-5 minutes.
