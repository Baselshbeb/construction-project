# Frequently Asked Questions

---

### What IFC versions are supported?

Metraj supports **IFC2x3** and **IFC4** schemas. IFC4x3 files can be read but infrastructure-specific entity types (bridges, roads) are not recognized. The system detects the schema from the file header automatically.

---

### How accurate are the material estimates?

Accuracy depends primarily on the quality of the IFC model. When the model includes quantity sets (Qto) with pre-computed areas and volumes, estimates are generally reliable for budgeting purposes. When quantities must be derived from basic dimensions, accuracy is reduced for complex geometry. Reinforcement steel is estimated using industry-standard kg/m3 ratios (not from structural analysis), and waste factors are industry averages. All estimates should be reviewed by a qualified quantity surveyor. See [Accuracy and Limitations](../user-guide/accuracy-and-limitations.md).

---

### Can I customize the waste factors?

Yes. Edit `src/data/waste_factors.json` to change the waste percentages for any material category. You can also add new categories or levels. Changes take effect on the next pipeline run without requiring a server restart. See [Waste Factors Reference](../reference/waste-factors.md).

---

### What data is sent to the AI?

Element-level data is sent to the Anthropic Claude API: element IDs, IFC types, names, storey assignments, the IsExternal property, material names, and calculated quantities (areas, volumes). The full IFC file, 3D geometry, detailed property sets, and user identity are never sent. See [AI Transparency](../architecture/ai-transparency.md) for the complete list.

---

### How long is uploaded data kept?

Projects older than **30 days** are automatically deleted from the database on server startup. Uploaded IFC files and generated reports on disk should be cleaned up separately (automatic file cleanup is not implemented in the default configuration). See [Data Handling](../legal/data-handling.md).

---

### Can I use Metraj without an internet connection?

No. The AI-powered stages (Classification, Material Mapping, Validation) require access to the Anthropic Claude API, which is a cloud service. Without an API key and internet access, the pipeline will fail at the Classification stage.

---

### What languages are supported for the BOQ output?

Three languages are supported: **English**, **Turkish**, and **Arabic**. The language affects:
- BOQ section titles
- Material names (AI generates them in the selected language)
- Export labels (column headers, footer text)
- Arabic reports use right-to-left (RTL) layout

To add a new language, see the question below.

---

### How do I add a new language?

1. Add section titles to `BOQ_SECTIONS` in `src/translations/strings.py`
2. Add export labels to `EXPORT_LABELS` in the same file
3. Add language instructions to `MAPPER_LANGUAGE_INSTRUCTIONS` in `src/prompts/material_mapper_prompts.py`
4. Add language instructions to `VALIDATOR_LANGUAGE_INSTRUCTIONS` in `src/prompts/validator_prompts.py`
5. Add the language code to `SUPPORTED_LANGUAGES` in `src/agents/orchestrator.py`
6. Update the language validation pattern in `api/app.py` (the `language` query parameter regex)

The AI will generate material names and descriptions in the new language based on the instruction you provide in step 3.

---

### What if my IFC file has no quantity sets?

Metraj will still work, but with reduced accuracy. When Qto (quantity takeoff) properties are not present, the calculator derives quantities from basic dimensions:

- Wall area is computed as Length x Height
- Slab area is computed as Length x Width
- Volume is computed as Area x Depth

This is accurate for simple rectangular elements but approximate for complex geometry. The system logs a warning when all-zero quantities are detected. To improve accuracy, re-export your IFC file with the "Export base quantities" option enabled in your BIM tool.

---

### What is the maximum file size?

The API accepts IFC files up to **500 MB**. This limit is enforced at the API level. Very large files (approaching this limit) may require significant RAM for parsing and may take several minutes to process.

---

### Can I process multiple files at once?

Each file upload creates a separate project. You can upload multiple files in sequence -- each runs independently. There is a rate limit of 5 uploads per 60 seconds per client IP to prevent abuse.

---

### What happens if the pipeline fails partway through?

If any stage fails, the pipeline stops and reports the error. Successful stages are not rolled back -- you can see partial results in the project status. Common failure causes include:
- Empty IFC file (Parser fails)
- AI API errors (Classifier or Material Mapper fails)
- All elements having zero quantities (Calculator produces no results)

Failed projects can be retried using the reprocess endpoint.

---

### Can I reprocess a file with a different language?

Yes. Use the reprocess endpoint:

```
POST /api/projects/{project_id}/reprocess?language=tr
```

This re-runs the entire pipeline on the original IFC file with the new language setting. You do not need to re-upload the file.

---

### What BIM tools can export IFC files?

Most professional BIM tools support IFC export, including:
- **Autodesk Revit** (File > Export > IFC)
- **Graphisoft ArchiCAD** (File > Save As > IFC)
- **FreeCAD** (File > Export > IFC)
- **Tekla Structures**
- **Bentley OpenBuildings**
- **Allplan**
- **Vectorworks**

See [Uploading IFC Files](../user-guide/uploading-ifc.md) for detailed export instructions.

---

### Does Metraj support .ifczip or .ifcxml files?

No. Only plain `.ifc` files (STEP format) are supported. If you have an `.ifczip` file, extract the `.ifc` file from the archive before uploading. `.ifcxml` files use a different encoding and are not supported.

---

### Why are some elements listed as "unclassified"?

The AI classifier could not determine the appropriate BOQ category for these elements. Common reasons:
- The element is a `IfcBuildingElementProxy` with a generic name
- The element type is not commonly used in construction (e.g., custom furniture modeled as building elements)
- The AI encountered an unusual combination of type and name

Unclassified elements are logged as warnings. If more than 50% of elements are unclassified, the pipeline fails.

---

### How do I add support for a new IFC element type?

1. Add the IFC type name to `BUILDING_ELEMENT_TYPES` in `src/services/ifc_service.py`
2. Add a calculator method in `src/agents/calculator.py` (or rely on `_calc_generic` for basic quantity extraction)
3. Optionally add reference material rules in `src/data/element_rules.json`
4. The AI will handle classification and material mapping for the new type based on its construction knowledge

---

### Can I use a different AI model?

Yes. Set the `DEFAULT_MODEL` environment variable to any Claude model ID:

```env
DEFAULT_MODEL=claude-sonnet-4-5-20250929
```

The classifier always uses `claude-haiku-4-5-20251001` (hardcoded for speed). To change this, modify the `model` parameter in `src/agents/classifier.py`.

Note that Metraj is designed for the Anthropic Claude API and does not support other AI providers (OpenAI, etc.) without code modifications to `src/services/llm_service.py`.

---

### Is there an API rate limit?

The upload endpoint is rate-limited to **5 uploads per 60 seconds per client IP**. Other endpoints (project listing, status checking, downloading) are not rate-limited. The Anthropic API has its own rate limits that apply to AI calls.

---

### What does the validation score mean?

The validation score (e.g., "8/8 PASS") shows how many of the 8 arithmetic checks passed:
1. Elements parsed
2. Elements classified
3. Quantities calculated
4. Materials mapped
5. No negative quantities
6. Concrete ratio reasonable
7. All storeys have elements
8. Steel ratio reasonable

A score of "8/8 PASS" means no arithmetic issues were detected. The AI review results are shown separately as warnings and do not affect the pass/fail score.

---

### Where are the generated reports stored?

Reports are stored in the `output/` directory, organized by project ID:

```
output/
  a1b2c3d4-e5f6-7890/
    building_BOQ.xlsx
    building_BOQ.csv
    building_BOQ.json
```

Download them via the API at `/api/projects/{project_id}/download/{format}` or access them directly on disk.
