# Accuracy and Limitations

Metraj is a tool that assists construction professionals with material estimation. This document provides an honest assessment of what the system does well, where its limitations lie, and what steps should be taken to verify the output.

---

## Accuracy Depends on IFC Model Quality

The most significant factor in estimation accuracy is the quality of the input IFC file. Metraj can only estimate materials based on the data available in the model.

### High-Accuracy Scenarios

Metraj produces its most reliable estimates when:

- The BIM model was exported with **quantity sets** (Qto) enabled, providing pre-computed areas, volumes, and lengths
- The **IsExternal** property is set on walls, so external and internal walls are correctly distinguished
- **Materials** are assigned to elements in the model (e.g., "Concrete C25/30" on a wall)
- Elements are properly assigned to **storeys**
- Standard element types are used (IfcWall, IfcSlab, IfcColumn, etc.) rather than generic geometry

### Reduced-Accuracy Scenarios

Accuracy is reduced when:

- Quantity sets are absent (Metraj derives quantities from basic dimensions, which is approximate for complex shapes)
- The IsExternal property is missing (the AI classifier guesses based on element name and position)
- Material assignments are missing (the AI uses default material assumptions)
- Elements are modeled as generic proxies (`IfcBuildingElementProxy`) rather than specific types

---

## Known Limitations

### Curved and Complex Geometry

Metraj's quantity calculator works with the dimensional properties in the IFC file (length, height, width) and pre-computed quantities (area, volume). For curved walls, tapered elements, or complex geometry, the calculator may not accurately derive quantities from basic dimensions alone. Pre-computed quantity sets from the BIM tool handle this correctly.

### MEP Not Supported

Mechanical, electrical, and plumbing elements are not currently supported. IFC elements like `IfcDistributionElement`, `IfcFlowSegment`, and `IfcFlowTerminal` are not in the recognized element list. MEP quantities must be estimated separately.

### Reinforcement Is Estimated

Reinforcement steel quantities are estimated using industry-standard kg/m3 ratios:

| Element | Steel Ratio |
|---|---|
| Foundations | 60-80 kg/m3 |
| Walls (structural) | 60-80 kg/m3 |
| Slabs | 80-120 kg/m3 |
| Columns | 130-180 kg/m3 |
| Beams | 100-150 kg/m3 |

Actual reinforcement quantities depend on structural analysis (load cases, spans, seismic requirements) which are not available in a typical IFC model. The estimates are suitable for budgeting but should not be used for rebar ordering without verification against structural drawings.

### Waste Factors Are Industry Averages

The waste factors applied are general industry averages. Actual waste varies significantly based on:

- Construction method (precast vs in-situ)
- Labor skill level
- Site conditions (access, weather)
- Material quality and supply chain
- Project scale

See [Waste Factors Reference](../reference/waste-factors.md) for the complete table and customization instructions.

### AI Can Make Mistakes

Three pipeline stages use Claude AI for decision-making:

- **Classification:** The AI may incorrectly categorize elements in unusual or ambiguous cases
- **Material mapping:** The AI may miss materials, suggest incorrect materials, or use wrong multipliers
- **Validation:** The AI review may flag non-issues or miss real problems

All AI decisions should be reviewed by a qualified professional. See [AI Transparency](../architecture/ai-transparency.md) for details on what the AI does and how errors are handled.

### Unit Rate Limitations

Metraj generates quantities only -- it does not include unit prices. The Rate and Amount columns in the BOQ are left blank for the user to fill in with current market prices.

### Temporary Works

Temporary construction works (scaffolding, shoring, dewatering, site offices) are not estimated. Only permanent materials that become part of the finished building are included.

### Finishes and Fixtures

Detailed finish specifications (tile patterns, paint systems, ceiling types) are only estimated if the corresponding elements are modeled in the IFC file. Generic finishing allowances are not automatically added.

### Site-Specific Conditions

The system does not account for site-specific conditions such as:

- Soil conditions affecting foundation design
- Seismic zone requirements
- Fire rating requirements (beyond what is in IFC properties)
- Local building code requirements
- Access constraints affecting construction method

---

## Validation Results

Every BOQ includes a validation report with two levels of checking:

### Arithmetic Checks (8 checks)

These are deterministic and reliable:

1. Elements were parsed from the IFC file
2. Elements were classified into categories
3. Quantities were calculated
4. Materials were mapped
5. No negative quantities exist
6. Concrete ratio is reasonable (0.1-1.5 m3/m2 of floor area)
7. All storeys have at least one element
8. Steel-to-concrete ratio is reasonable (50-200 kg/m3)

A result of "8/8 PASS" means all arithmetic checks passed. This does not guarantee correctness -- it means no obviously impossible values were detected.

### AI Engineering Review

The AI review checks for:

- Missing material categories (e.g., building with columns but no beams)
- Inconsistent ratios (e.g., plaster area much larger than wall area)
- Construction logic issues (e.g., timber frame with concrete columns)
- Missing typical items (e.g., no waterproofing for basement)

AI review findings are always reported as **warnings** (never errors), because AI assessments are subjective and may be incorrect. Review these warnings carefully -- they often highlight real issues but may also flag acceptable deviations.

---

## Recommendations for Professional Use

1. **Always have a qualified quantity surveyor review the output.** Metraj is an estimation tool, not a replacement for professional judgment.

2. **Check the Audit Trail.** The third sheet in the Excel report shows how each quantity was derived, including the waste factor and number of source elements. Use this to verify any line item that seems unusual.

3. **Verify critical items manually.** For high-value items (concrete, reinforcement steel), cross-check the quantities against the model using your BIM viewer.

4. **Adjust waste factors for your context.** The default waste factors are industry averages. If you know your site conditions warrant different values, adjust them before running the pipeline.

5. **Add items not covered by the model.** MEP, temporary works, and site-specific items will need to be estimated separately and added to the BOQ.

6. **Use the BOQ for budgeting, not procurement.** The output is most suitable for early-stage cost planning, feasibility studies, and budget estimates. For procurement-level quantities, verify against detailed construction drawings.

---

## Accuracy Disclaimer

Metraj provides material quantity estimates for planning and budgeting purposes. These estimates are generated from IFC building model data using automated calculations and AI-assisted material mapping. The estimates are not a substitute for professional quantity surveying.

Users should be aware that:

- Quantities are derived from the IFC model as-is. Errors or omissions in the model will be reflected in the estimates.
- Waste factors are industry averages and may not reflect site-specific conditions.
- Reinforcement quantities are estimated using standard ratios, not from structural analysis.
- AI-generated material lists may contain errors or omissions.
- The system does not account for local building codes, regulations, or site conditions.

All estimates should be reviewed and verified by a qualified quantity surveyor or construction professional before being used for procurement, tendering, or construction planning.
