# Agent Pipeline

The Metraj pipeline consists of six agents that sequentially transform an IFC file into a validated Bill of Quantities. Each agent inherits from `BaseAgent` (in `src/agents/base_agent.py`) and implements an `execute(state)` method that reads from and writes to the shared pipeline state.

The pipeline is orchestrated by the `Orchestrator` class in `src/agents/orchestrator.py`, which runs each agent in sequence with inter-stage validation gates.

---

## 1. IFC Parser Agent

**File:** `src/agents/ifc_parser.py`
**Type:** Code-driven (no AI)
**Status:** `PARSING`

### Purpose

Reads the IFC file using IfcOpenShell and extracts all recognized building elements with their geometry data, properties, material layers, and storey assignments.

### Input

- `state["ifc_file_path"]` -- path to the IFC file on disk

### Output

- `state["parsed_elements"]` -- list of element data dictionaries
- `state["building_info"]` -- project/building metadata (name, storeys, schema version)

### Key Logic

The parser uses the `IFCService` wrapper (`src/services/ifc_service.py`) which:

1. Opens the IFC file with IfcOpenShell
2. Iterates over all recognized `BUILDING_ELEMENT_TYPES` (18 types including IfcWall, IfcSlab, IfcColumn, etc.)
3. For each element, extracts:
   - **Quantities** from Qto (quantity takeoff) property sets: Length, Height, Width, Area, Volume, Perimeter
   - **Properties** from Pset (property) sets: IsExternal, FireRating, LoadBearing, etc.
   - **Materials** from material associations: individual materials, layer sets, or material lists
   - **Container** (storey assignment) via spatial containment
   - **Type name** (e.g., "Basic Wall: 200mm Concrete")
4. For doors and windows, also extracts `OverallWidth` and `OverallHeight` attributes
5. Logs warnings for unrecognized element types found in the file

### Configuration

The list of recognized building element types is defined in `BUILDING_ELEMENT_TYPES` in `src/services/ifc_service.py`. To add support for additional IFC types, add them to this list.

---

## 2. Classifier Agent

**File:** `src/agents/classifier.py`
**Type:** AI-powered (Claude API)
**Status:** `CLASSIFYING`

### Purpose

Categorizes each parsed building element into one of 12 standard BOQ sections using Claude AI. This determines which section of the BOQ each element's materials will appear in.

### Input

- `state["parsed_elements"]` -- the list of parsed elements from Stage 1

### Output

- Each element in `state["parsed_elements"]` receives a `category` field
- `state["classified_elements"]` -- dict mapping category names to lists of element IDs

### Key Logic

1. Elements are serialized into a compact JSON format containing only classification-relevant fields: `ifc_id`, `ifc_type`, `name`, `storey`, `is_external`, wall thickness, and IFC materials
2. Elements are batched in groups of 50 to avoid exceeding LLM token limits
3. Each batch is sent to Claude with a detailed system prompt defining the 12 categories and classification guidelines
4. The AI response (a flat JSON dict mapping element IDs to categories) is validated through the `ClassifierResponse` Pydantic model
5. Invalid categories are silently filtered; unclassified elements are logged as warnings

### Categories

| Category | Description |
|---|---|
| `substructure` | Foundations, ground slabs, basement walls, piles, footings |
| `frame` | Columns, beams, structural/load-bearing walls, bracing |
| `upper_floors` | Floor slabs above ground level |
| `roof` | Roof slabs, structure, and coverings |
| `external_walls` | Outer walls, facade walls, curtain walls |
| `internal_walls` | Inner partition walls |
| `doors` | All door types |
| `windows` | All window types |
| `stairs` | Stairs, ramps, railings |
| `finishes` | Floor/wall/ceiling finishes |
| `mep` | Mechanical, electrical, plumbing |
| `external_works` | Landscaping, paving, fencing |

### Configuration

- **Model:** `claude-haiku-4-5-20251001` (hardcoded for speed, as classification is a simpler task)
- **Temperature:** 0.0 (deterministic)
- **Max tokens:** 4,096 per batch
- **Batch size:** 50 elements

---

## 3. Calculator Agent

**File:** `src/agents/calculator.py`
**Type:** Code-driven (no AI)
**Status:** `CALCULATING`

### Purpose

Computes construction-relevant quantities from the raw IFC geometry data. Transforms measurements like "length=10, height=3" into actionable quantities like "gross wall area=30 m2, net wall area=25.5 m2, wall volume=6 m3".

### Input

- `state["parsed_elements"]` -- elements with quantities from IFC and categories from Classifier

### Output

- `state["calculated_quantities"]` -- list of per-element quantity breakdowns

### Key Logic

**Opening deduction:** The calculator performs two passes over elements:

1. **First pass:** Collects all door and window opening areas per storey, and all gross wall areas per storey
2. **Second pass:** Computes the actual opening ratio per storey (opening area / wall area, capped at 60%). This ratio is used to deduct openings from wall areas instead of using a hardcoded percentage.

**Quantity key aliases:** Different IFC exporters (Revit, ArchiCAD, FreeCAD) use different names for the same quantity. The calculator resolves this using the `QTY_ALIASES` dictionary. For example, "Width" is also searched as "NominalWidth", "Thickness", and "OverallWidth".

**Unit normalization:** The calculator detects values likely in millimetres (e.g., a wall width of 200 when the expected unit is metres) and converts them: any Width, Depth, or Thickness value greater than 10 is divided by 1000.

**Element-specific calculators:**

| Element Type | Quantities Computed |
|---|---|
| IfcWall | Gross area (one side), net area (minus openings), volume, both-sides area (internal) or internal+external face areas, wall length |
| IfcSlab | Top face area, soffit area, volume, perimeter, formwork area (soffit + edges) |
| IfcColumn | Volume, surface area (for formwork/plaster), count |
| IfcBeam | Volume, length, surface area |
| IfcDoor | Count, opening area (for wall deduction), frame perimeter |
| IfcWindow | Count, opening area, sill length |
| IfcStair | Volume, area, count |
| IfcRoof | Same as slab |
| IfcFooting/IfcPile | Volume, area |
| Other types | All non-zero quantities from Qto sets with auto-detected units |

---

## 4. Material Mapper Agent

**File:** `src/agents/material_mapper.py`
**Type:** AI-powered (Claude API)
**Status:** `MAPPING_MATERIALS`

### Purpose

Determines the complete list of construction materials needed for each building element, including quantities, multipliers, and waste factors. This is the core estimation step.

### Input

- `state["parsed_elements"]` -- elements with categories
- `state["calculated_quantities"]` -- per-element quantities from Calculator

### Output

- `state["material_list"]` -- aggregated list of unique materials with total quantities

### Key Logic

1. Elements are grouped by IFC type and batched (max 50 per batch)
2. Each element is enriched with its calculated quantities before sending to Claude
3. The system prompt includes:
   - The complete waste factors table from `waste_factors.json`
   - Reference material rules from `element_rules.json`
   - Reinforcement ratio guidelines (e.g., columns: 130-180 kg/m3)
   - Language-specific instructions (material names in Turkish or Arabic if selected)
4. Claude returns a JSON array of material rules for each element, specifying: material name, unit, source quantity, multiplier, and waste key
5. The response is validated through the `MapperResponse` Pydantic model
6. For each material rule, the agent:
   - Looks up the source quantity by description (with fuzzy matching fallback)
   - Applies the multiplier (e.g., 80 kg steel per m3 of concrete)
   - Looks up the waste factor from `waste_factors.json`
   - Computes: `total_quantity = base_quantity * (1 + waste_factor)`
7. Materials are aggregated across all elements using normalized names (fuzzy deduplication handles AI inconsistencies like "Internal plaster" vs "Interior plaster")
8. Weighted-average waste factors are computed for aggregated materials

### Material Name Normalization

The `_normalize_material_name()` function handles common AI inconsistencies:
- Case normalization
- Parenthetical stripping: "Concrete C25/30 (pumped)" becomes "Concrete C25/30"
- Synonym resolution: "interior" to "internal", "exterior" to "external"
- Unicode normalization for Turkish/Arabic characters

### Configuration

- **Model:** Default model (Claude Sonnet)
- **Temperature:** 0.0
- **Max tokens:** 8,192 per batch
- **Batch size:** 50 elements per type group

---

## 5. BOQ Generator Agent

**File:** `src/agents/boq_generator.py`
**Type:** Code-driven (no AI)
**Status:** `GENERATING_BOQ`

### Purpose

Assembles the aggregated material list into a structured Bill of Quantities with numbered sections, item numbers, and organized layout.

### Input

- `state["material_list"]` -- aggregated materials from Material Mapper
- `state["building_info"]` -- project metadata

### Output

- `state["boq_data"]` -- structured BOQ dict with sections and items

### Key Logic

1. Materials are grouped by their category
2. Sections are created in a fixed display order:
   1. Substructure
   2. Frame (Columns and Beams)
   3. External Walls
   4. Internal Walls and Partitions
   5. Upper Floor Slabs
   6. Roof
   7. Doors
   8. Windows
   9. Stairs and Ramps
   10. Finishes
   11. MEP
   12. External Works
3. Empty sections are omitted
4. Each item gets a hierarchical item number (e.g., "2.03" = Section 2, Item 3)
5. Items include base quantity, waste factor, total quantity (with waste), and placeholders for rate and amount
6. Section titles are localized based on the selected language
7. Uncategorized materials are placed in an "Other Items" section

### Section Titles by Language

| Category | English | Turkish | Arabic |
|---|---|---|---|
| substructure | Substructure | Altyapi | البنية التحتية |
| frame | Structural Frame (Columns & Beams) | Tasiyici Sistem (Kolon ve Kirisler) | الهيكل الإنشائي |
| external_walls | External Walls | Dis Duvarlar | الجدران الخارجية |
| internal_walls | Internal Walls & Partitions | Ic Duvarlar ve Bolmeler | الجدران الداخلية والفواصل |

---

## 6. Validator Agent

**File:** `src/agents/validator.py`
**Type:** Hybrid (arithmetic + AI)
**Status:** `VALIDATING`

### Purpose

Cross-checks the entire pipeline output using both deterministic arithmetic checks and an AI-powered engineering review. Produces a validation report with a pass/fail score.

### Input

- Full pipeline state including `parsed_elements`, `material_list`, `calculated_quantities`, `building_info`, and `boq_data`

### Output

- `state["validation_report"]` -- detailed validation results
- `state["warnings"]` -- accumulated warnings
- `state["errors"]` -- fatal errors
- `state["status"]` -- set to `COMPLETED` or `FAILED`

### Arithmetic Checks

| Check | Condition | Severity |
|---|---|---|
| Elements parsed | At least one element exists | Error if none |
| Elements classified | All elements have a category | Warning for unclassified |
| Quantities calculated | At least one quantity result exists | Error if none |
| Materials mapped | At least one material exists | Error if none |
| No negative quantities | All quantities >= 0 | Error per negative |
| Concrete ratio reasonable | 0.1-1.5 m3/m2 of floor area | Warning if outside range |
| All storeys have elements | No empty storeys | Warning for empty storeys |
| Steel ratio reasonable | 50-200 kg/m3 of concrete | Warning if outside range |

### AI Engineering Review

After arithmetic checks, the Validator sends a summary of the entire BOQ to Claude for intelligent review. The AI checks for:

- **Completeness:** Missing material categories for the building type
- **Consistency:** Material ratios that do not make sense (e.g., plaster area vs wall area)
- **Reasonableness:** Quantities reasonable for a building of this size
- **Construction logic:** Contradictory material combinations
- **Missing items:** Typical items that should be present (e.g., waterproofing for basements)

**Critical design decision:** All AI-reported issues are downgraded to warnings, regardless of the severity the AI assigns. Only the deterministic arithmetic checks can cause the pipeline to fail. This ensures the AI cannot block report generation based on subjective assessments.

### Configuration

- **Model:** Default model (Claude Sonnet)
- **Temperature:** 0.1 (slightly creative to catch more issues)
- Arithmetic checks are not configurable
