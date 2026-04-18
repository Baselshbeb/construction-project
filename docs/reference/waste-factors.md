# Waste Factors Reference

Waste factors account for the inevitable loss of materials during construction -- spillage, breakage, cutting, over-ordering, and other site realities. Metraj applies these factors automatically to convert net material quantities into the quantities that should actually be ordered.

The waste factors are defined in `src/data/waste_factors.json` and are referenced by the Material Mapper agent during the material estimation process.

---

## What Are Waste Factors

In construction, you never order exactly the net quantity of material you need. Some concrete spills, some bricks break, some tiles need cutting at edges, and some paint is lost to the roller. A **waste factor** is a decimal fraction added to the net quantity to account for this loss.

**Formula:**

```
total_quantity = base_quantity * (1 + waste_factor)
```

For example, if a wall requires 100 m2 of internal plaster and the waste factor is 0.10 (10%), the total quantity to order is:

```
100 * (1 + 0.10) = 110 m2
```

---

## Waste Factor Table

Each material category has one or more waste factor levels depending on site conditions, element complexity, or application method.

### Concrete

| Level | Factor | Percentage | Use Case |
|---|---|---|---|
| `concrete.standard` | 0.05 | 5% | Standard in-situ concrete for walls, slabs, beams |
| `concrete.pumped` | 0.03 | 3% | Pumped concrete (less spillage due to controlled delivery) |
| `concrete.foundation` | 0.07 | 7% | Foundation concrete (uneven ground, soil absorption, over-dig) |

*Waste sources: spillage during pouring, over-ordering, formwork gaps, leftover in pump lines.*

### Reinforcement Steel

| Level | Factor | Percentage | Use Case |
|---|---|---|---|
| `reinforcement_steel.standard` | 0.03 | 3% | Standard rebar cutting and bending |
| `reinforcement_steel.complex_shapes` | 0.05 | 5% | Complex shapes, stirrups, special bends requiring more cutting |

*Waste sources: cutting offcuts, bending scrap, lap splice overlaps.*

### Formwork

| Level | Factor | Percentage | Use Case |
|---|---|---|---|
| `formwork.standard` | 0.10 | 10% | New formwork panels (some damaged during stripping) |
| `formwork.reusable` | 0.05 | 5% | System formwork designed for multiple reuses |

*Waste sources: panel damage during stripping, cutting for non-standard shapes, cleaning loss.*

### Bricks

| Level | Factor | Percentage | Use Case |
|---|---|---|---|
| `bricks.standard` | 0.05 | 5% | Standard brick laying (straight walls) |
| `bricks.curved_walls` | 0.10 | 10% | Curved or complex-shaped walls requiring more cutting |

*Waste sources: breakage during transport and handling, cutting for bond patterns and corners.*

### Mortar

| Level | Factor | Percentage | Use Case |
|---|---|---|---|
| `mortar.standard` | 0.10 | 10% | Brick-laying and block-laying mortar |

*Waste sources: mixing excess, spillage during application, drying in mixer.*

### Plaster

| Level | Factor | Percentage | Use Case |
|---|---|---|---|
| `plaster.internal` | 0.10 | 10% | Internal wall and ceiling plaster |
| `plaster.external` | 0.12 | 12% | External cement render (higher waste due to weather exposure and rougher surfaces) |

*Waste sources: application droppings, uneven surface absorption, material drying in mixer.*

### Paint

| Level | Factor | Percentage | Use Case |
|---|---|---|---|
| `paint.standard` | 0.10 | 10% | Standard interior and exterior paint application |

*Waste sources: roller/brush absorption, dripping, overspray, leftover in cans.*

### Tiles

| Level | Factor | Percentage | Use Case |
|---|---|---|---|
| `tiles.standard` | 0.10 | 10% | Standard rectangular tile layout |
| `tiles.diagonal_pattern` | 0.15 | 15% | Diagonal or herringbone patterns requiring more edge cuts |

*Waste sources: cutting at edges and corners, breakage, pattern matching waste.*

### Waterproofing

| Level | Factor | Percentage | Use Case |
|---|---|---|---|
| `waterproofing.standard` | 0.10 | 10% | Sheet membrane or liquid-applied waterproofing |

*Waste sources: overlap requirements (typically 100-150mm), cutting waste at corners and penetrations.*

### Insulation

| Level | Factor | Percentage | Use Case |
|---|---|---|---|
| `insulation.standard` | 0.05 | 5% | Board or batt insulation |

*Waste sources: cutting around openings (doors, windows), fitting at corners, off-cut pieces too small to reuse.*

### Screed

| Level | Factor | Percentage | Use Case |
|---|---|---|---|
| `screed.standard` | 0.08 | 8% | Floor screed (sand-cement leveling layer) |

*Waste sources: uneven application, material left in mixer, leveling excess.*

### Timber

| Level | Factor | Percentage | Use Case |
|---|---|---|---|
| `timber.formwork` | 0.15 | 15% | Timber used for formwork (high waste from cutting to fit) |
| `timber.structural` | 0.05 | 5% | Structural timber (pre-cut, lower waste) |

*Waste sources: cutting offcuts, damage during handling, notching and drilling.*

### Glass

| Level | Factor | Percentage | Use Case |
|---|---|---|---|
| `glass.standard` | 0.02 | 2% | Window and curtain wall glazing |

*Very low waste -- glass is typically cut to exact dimensions at the factory. Waste accounts for occasional breakage during transport and installation.*

---

## How Waste Factors Are Applied in the Pipeline

1. The **Material Mapper Agent** sends element data to Claude AI
2. Claude returns material rules for each element, including a `waste_key` (e.g., `"concrete.standard"`) or a direct `waste_value` (e.g., `0.05`)
3. The agent looks up the waste factor from `waste_factors.json` using the dot-notation key:
   - `"concrete.standard"` is resolved as `waste_factors["concrete"]["standard"]` = 0.05
4. The total quantity is calculated: `base_quantity * (1 + waste_factor)`
5. When materials are aggregated across multiple elements, the waste factor is computed as a **weighted average** (weighted by base quantity)

For materials where waste does not apply (e.g., doors, windows, hardware sets), a `waste_value` of 0 is used directly.

---

## Customizing Waste Factors

To adjust waste factors for your region or project conditions:

1. Edit `src/data/waste_factors.json`
2. Modify the numeric values for existing categories
3. Add new categories or levels as needed

Example -- adding a custom waste factor for precast concrete:

```json
{
  "concrete": {
    "standard": 0.05,
    "pumped": 0.03,
    "foundation": 0.07,
    "precast": 0.02,
    "description": "Concrete waste due to spillage, over-ordering, formwork gaps"
  }
}
```

The AI will reference the new key if it recognizes the material context, or you can update the element rules in `element_rules.json` to explicitly use the new key.

---

## Regional Considerations

The waste factors in Metraj are industry averages suitable for most construction projects. However, actual waste varies by:

- **Region:** Developing markets may have higher waste due to less mechanization; prefabrication-heavy markets may have lower waste
- **Project scale:** Large projects can negotiate better material deliveries and achieve lower waste
- **Labor skill level:** Experienced crews generate less waste
- **Material quality:** Higher-quality materials may have lower breakage rates
- **Weather conditions:** Extreme heat or cold can increase concrete and mortar waste
- **Site access:** Difficult access increases handling damage

Always review the default waste factors against local experience before using the BOQ for procurement. The Audit Trail sheet in the Excel report shows the waste factor applied to each line item for easy review.
