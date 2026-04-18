# Element Rules Reference

The element rules file (`src/data/element_rules.json`) provides reference mappings from IFC building element types to their required construction materials. These rules are included in the Material Mapper's system prompt as examples for Claude AI to follow and adapt.

The rules are not applied rigidly -- Claude uses them as a starting point and applies construction engineering knowledge to adapt the materials based on each element's specific properties (external vs internal, material layers, storey location, etc.).

---

## Rule Structure

Each IFC element type can have multiple rule variants based on conditions:

```json
{
  "IfcWall": {
    "concrete_external": {
      "condition": {"is_external": true, "material_contains": "concrete"},
      "materials": [
        {
          "name": "Concrete C25/30",
          "unit": "m3",
          "source": "Wall volume",
          "waste": "concrete.standard"
        }
      ]
    },
    "brick_internal": {
      "condition": {"is_external": false},
      "materials": [...]
    }
  }
}
```

**Fields per material rule:**

| Field | Description | Example |
|---|---|---|
| `name` | Material description | "Concrete C25/30" |
| `unit` | Measurement unit | "m3", "m2", "kg", "nr", "set" |
| `source` | Quantity description to look up from Calculator output | "Wall volume" |
| `multiplier` | Factor applied to source quantity (default: 1.0) | 80 (for steel kg per m3) |
| `waste` | Waste factor key from waste_factors.json | "concrete.standard" |
| `waste_value` | Direct waste factor (alternative to `waste`) | 0 (for doors/windows) |
| `note` | Explanation for the estimation logic | "~80 kg/m3 for structural walls" |

---

## IfcWall -- External Concrete Wall

**Condition:** `is_external = true`, material contains "concrete"

| Material | Unit | Source Quantity | Multiplier | Waste Key | Notes |
|---|---|---|---|---|---|
| Concrete C25/30 | m3 | Wall volume | 1.0 | concrete.standard (5%) | Structural concrete for the wall body |
| Reinforcement steel | kg | Wall volume | 80 | reinforcement_steel.standard (3%) | ~80 kg/m3 for structural walls |
| Formwork (wall) | m2 | Gross wall area (one side) | 2 | formwork.standard (10%) | Both sides of wall |
| External plaster (cement render) | m2 | External face area | 1.0 | plaster.external (12%) | Weather-resistant render |
| Internal plaster | m2 | Internal face area | 1.0 | plaster.internal (10%) | Interior finish |
| External paint | m2 | External face area | 1.0 | paint.standard (10%) | Exterior coating |
| Internal paint | m2 | Internal face area | 1.0 | paint.standard (10%) | Interior coating |

---

## IfcWall -- Internal Brick Wall

**Condition:** `is_external = false` (default for internal walls)

| Material | Unit | Source Quantity | Multiplier | Waste Key | Notes |
|---|---|---|---|---|---|
| Clay bricks (standard) | nr | Net wall area (minus openings, one side) | 50 | bricks.standard (5%) | ~50 bricks per m2 for 100mm wall |
| Mortar (brick laying) | m3 | Net wall area (minus openings, one side) | 0.03 | mortar.standard (10%) | ~0.03 m3 per m2 |
| Internal plaster (both sides) | m2 | Net wall area (both sides) | 1.0 | plaster.internal (10%) | Plaster on both faces |
| Internal paint (both sides) | m2 | Net wall area (both sides) | 1.0 | paint.standard (10%) | Paint on both faces |

---

## IfcWall -- Internal Concrete Wall

**Condition:** `is_external = false`, material contains "concrete"

| Material | Unit | Source Quantity | Multiplier | Waste Key | Notes |
|---|---|---|---|---|---|
| Concrete C25/30 | m3 | Wall volume | 1.0 | concrete.standard (5%) | Structural concrete |
| Reinforcement steel | kg | Wall volume | 60 | reinforcement_steel.standard (3%) | 60 kg/m3 for internal concrete walls |
| Formwork (wall) | m2 | Gross wall area (one side) | 2 | formwork.standard (10%) | Both sides |
| Internal plaster (both sides) | m2 | Net wall area (both sides) | 1.0 | plaster.internal (10%) | Plaster on both faces |
| Internal paint (both sides) | m2 | Net wall area (both sides) | 1.0 | paint.standard (10%) | Paint on both faces |

---

## IfcSlab

**Condition:** Standard (all slabs)

| Material | Unit | Source Quantity | Multiplier | Waste Key | Notes |
|---|---|---|---|---|---|
| Concrete C30/37 | m3 | Slab volume | 1.0 | concrete.standard (5%) | Higher grade for slabs |
| Reinforcement steel | kg | Slab volume | 100 | reinforcement_steel.standard (3%) | ~100 kg/m3 for slabs |
| Formwork (slab) | m2 | Formwork area (soffit + edges) | 1.0 | formwork.standard (10%) | Soffit and edge formwork |
| Floor screed (50mm) | m2 | Slab area (top face) | 1.0 | screed.standard (8%) | Leveling layer on top |
| Ceiling plaster (soffit) | m2 | Slab area (bottom face / soffit) | 1.0 | plaster.internal (10%) | Ceiling finish below |

---

## IfcColumn

**Condition:** Standard (all columns)

| Material | Unit | Source Quantity | Multiplier | Waste Key | Notes |
|---|---|---|---|---|---|
| Concrete C30/37 | m3 | Column volume | 1.0 | concrete.standard (5%) | Higher grade for columns |
| Reinforcement steel | kg | Column volume | 150 | reinforcement_steel.standard (3%) | ~150 kg/m3 -- highest ratio |
| Formwork (column) | m2 | Column surface area | 1.0 | formwork.standard (10%) | Column formwork |

---

## IfcBeam

**Condition:** Standard (all beams)

| Material | Unit | Source Quantity | Multiplier | Waste Key | Notes |
|---|---|---|---|---|---|
| Concrete C30/37 | m3 | Beam volume | 1.0 | concrete.standard (5%) | Higher grade for beams |
| Reinforcement steel | kg | Beam volume | 120 | reinforcement_steel.standard (3%) | ~120 kg/m3 for beams |
| Formwork (beam) | m2 | Beam surface area | 1.0 | formwork.standard (10%) | Beam formwork |

---

## IfcDoor

**Condition:** Standard (all doors)

| Material | Unit | Source Quantity | Multiplier | Waste Key | Notes |
|---|---|---|---|---|---|
| Door leaf (complete) | nr | Door count | 1.0 | 0% | Pre-manufactured, no waste |
| Door frame | nr | Door count | 1.0 | 0% | Pre-manufactured |
| Door hardware (handle, lock, hinges) | set | Door count | 1.0 | 0% | Complete hardware set |

Doors are counted items -- each door in the IFC model produces exactly 1 unit of each material. No waste factor is applied because these are pre-manufactured components ordered to specification.

---

## IfcWindow

**Condition:** Standard (all windows)

| Material | Unit | Source Quantity | Multiplier | Waste Key | Notes |
|---|---|---|---|---|---|
| Window unit (complete, double glazed) | nr | Window count | 1.0 | 0% | Pre-manufactured |
| Window sill (marble/stone) | m | Window sill length | 1.0 | tiles.standard (10%) | Cut to length, some waste |

Windows, like doors, are counted items. The window sill uses the sill length quantity and has a 10% waste factor for cutting.

---

## Worked Example

Consider an external concrete wall with the following calculated quantities:

- Gross wall area (one side): 30.0 m2
- Net wall area (minus openings, one side): 25.5 m2
- Wall volume: 6.0 m3
- Internal face area: 25.5 m2
- External face area: 25.5 m2

Applying the **concrete_external** rules:

| Material | Source | Base Qty | Multiplier | Net Qty | Waste | Total Qty |
|---|---|---|---|---|---|---|
| Concrete C25/30 | Wall volume (6.0 m3) | 6.0 m3 | x1.0 | 6.0 m3 | 5% | 6.300 m3 |
| Reinforcement steel | Wall volume (6.0 m3) | 6.0 m3 | x80 | 480.0 kg | 3% | 494.400 kg |
| Formwork (wall) | Gross area (30.0 m2) | 30.0 m2 | x2 | 60.0 m2 | 10% | 66.000 m2 |
| External plaster | External face (25.5 m2) | 25.5 m2 | x1.0 | 25.5 m2 | 12% | 28.560 m2 |
| Internal plaster | Internal face (25.5 m2) | 25.5 m2 | x1.0 | 25.5 m2 | 10% | 28.050 m2 |
| External paint | External face (25.5 m2) | 25.5 m2 | x1.0 | 25.5 m2 | 10% | 28.050 m2 |
| Internal paint | Internal face (25.5 m2) | 25.5 m2 | x1.0 | 25.5 m2 | 10% | 28.050 m2 |

These quantities are then aggregated with all other walls of the same type in the building to produce the final BOQ line items.

---

## Customizing Element Rules

To modify the reference rules:

1. Edit `src/data/element_rules.json`
2. Add new element types, rule variants, or materials
3. The changes will be included in the AI's system prompt on the next pipeline run

Note that Claude AI uses these rules as references, not rigid templates. The AI may:
- Add materials not in the rules (e.g., waterproofing for basement walls)
- Adjust multipliers based on the specific element properties
- Skip materials that do not apply to the specific context
- Use different waste keys based on element complexity
