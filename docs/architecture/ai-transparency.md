# AI Transparency

Metraj uses the Anthropic Claude API at three stages of its pipeline. This document explains exactly what data is sent to the AI, what decisions the AI makes, what safeguards are in place, and how AI errors are handled. Transparency about AI involvement is essential for users who need to trust the system's output.

---

## Which Agents Use AI

| Agent | AI Used | Model | Purpose |
|---|---|---|---|
| IFC Parser | No | -- | Deterministic IfcOpenShell parsing |
| **Classifier** | **Yes** | Claude Haiku | Categorize elements into BOQ sections |
| Calculator | No | -- | Deterministic quantity computation |
| **Material Mapper** | **Yes** | Claude Sonnet | Determine materials and quantities per element |
| BOQ Generator | No | -- | Deterministic section assembly |
| **Validator** | **Yes** | Claude Sonnet | Intelligent engineering review of the BOQ |

Three of six agents use AI. The other three are entirely code-driven and deterministic.

---

## What Data Is Sent to Claude

### Classifier Agent

For each element, the following fields are sent:

- `id` -- the IFC element ID (integer)
- `type` -- the IFC class name (e.g., "IfcWall", "IfcColumn")
- `name` -- the element name from the IFC file (e.g., "Basic Wall: 200mm Concrete")
- `storey` -- which floor the element is on (e.g., "Ground Floor")
- `is_external` -- whether the element is external (boolean)
- `thickness_mm` -- wall thickness in millimetres (if applicable)
- `materials` -- material names from the IFC file (e.g., ["Concrete", "Insulation"])

### Material Mapper Agent

For each element, the following is sent:

- `element_id` -- the IFC element ID
- `ifc_type` -- the IFC class name
- `name` -- the element name
- `is_external` -- external flag
- `category` -- the BOQ category assigned by the Classifier
- `ifc_materials` -- material names from the IFC file
- `quantities` -- calculated quantities (e.g., "Gross wall area: 30 m2", "Wall volume: 6 m3")

The system prompt also includes:
- The complete waste factors table
- Reference element-to-material mapping rules

### Validator Agent

A summary view is sent (not raw data), including:

- Building name, storey list, element type counts, category counts
- Material list with descriptions, units, quantities, waste factors
- Key ratios: total concrete (m3), total steel (kg), total floor area (m2), steel-per-concrete ratio
- BOQ summary: section count, line item count, section titles

### What Is NOT Sent

The following data is never transmitted to the AI:

- The full IFC file
- 3D geometry or coordinate data
- Property set values beyond IsExternal
- User identity or contact information
- File paths or server configuration
- API keys or credentials

---

## What Decisions the AI Makes

### Classifier Decisions

The AI decides which of 12 BOQ categories each element belongs to. For straightforward elements (IfcDoor, IfcWindow), this is simple. For ambiguous elements, the AI uses construction domain knowledge:

- Is a thick internal wall a partition (internal_walls) or load-bearing (frame)?
- Is a ground-level slab part of substructure or upper_floors?
- Is a IfcBuildingElementProxy a railing, a light fixture, or something else?

### Material Mapper Decisions

The AI decides:

- What construction materials are needed for each element type
- What source quantity to use for each material (e.g., wall volume for concrete, wall area for plaster)
- What multiplier to apply (e.g., 80 kg of steel per m3 of concrete for walls)
- Which waste factor category to reference

### Validator Decisions

The AI decides:

- Whether the overall BOQ is "REASONABLE", has "CONCERNS", or has "SIGNIFICANT_ISSUES"
- A confidence score (0.0 to 1.0)
- Specific issues with severity, category, message, and suggestion

---

## Safeguards

### Response Validation via Pydantic

Every AI response is validated through strict Pydantic models before being used:

- **ClassifierResponse:** Validates that each classification value is one of the 12 valid categories. Invalid categories are silently dropped.
- **MapperResponse / MaterialRule:** Validates material name, unit, source, multiplier (coerces string multipliers like "5x" to floats), and waste keys.
- **ValidatorResponse / ValidationIssue:** Validates severity levels (must be "error", "warning", or "info"), clamps confidence to 0.0-1.0.

If the AI response cannot be parsed into the expected Pydantic model, the system falls back gracefully rather than crashing.

### Retry on Parse Failure

The `LLMService.ask_json()` method implements automatic retries:

1. First attempt: send the prompt and try to parse the response as JSON
2. If JSON parsing fails, retry up to 2 additional times, including the parse error in the retry message so Claude can self-correct
3. JSON extraction is robust: it tries direct parsing, markdown fence stripping, and balanced-brace extraction

### Inter-Stage Gates

After each pipeline stage, the Orchestrator runs validation gates that check for catastrophic failures:

- After Classification: Fails if zero elements were classified; warns if more than 20% unclassified; fails if more than 50% unclassified
- After Material Mapping: Fails if zero materials were produced

These gates catch cases where the AI returned valid JSON but with empty or useless content.

### AI Error Downgrading

**This is a critical design decision.** In the Validator agent, all AI-reported issues -- even those the AI labels as "error" severity -- are downgraded to warnings. The rationale:

- Only deterministic arithmetic checks (negative quantities, impossible ratios) should be able to fail the pipeline
- AI assessments are subjective and can be wrong
- Users should always receive their BOQ, with AI concerns noted as warnings for human review
- This prevents the AI from blocking legitimate output based on conservative or incorrect assessments

### Prompt Caching

The LLM service uses Anthropic's prompt caching feature. System prompts are sent with `cache_control: {"type": "ephemeral"}`, meaning repeated calls with the same system prompt (common during batch processing) receive a significant cost discount on cached input tokens.

---

## Prompt Structure Overview

All prompts are stored in `src/prompts/` -- they are never hardcoded in agent files.

### Classifier Prompt Structure

```
System: You are an expert construction engineer specializing in building
        element classification for BOQ preparation.
        [12 category definitions with examples]
        [Classification guidelines per IFC type]
        Respond with a JSON object mapping element IDs to categories.

User:   {"elements": [...compact element data...], "count": N}
```

### Material Mapper Prompt Structure

```
System: You are an expert construction quantity surveyor specializing
        in material estimation (metraj).
        [Material rule format specification]
        [Complete waste factors table]
        [Reference element-to-material rules]
        [Reinforcement ratio guidelines]
        [Construction principles (8 rules)]
        [Language instruction if not English]
        Respond with a JSON object containing an "elements" array.

User:   {"element_count": N, "elements": [...enriched element data...]}
```

### Validator Prompt Structure

```
System: You are a senior quantity surveyor reviewing a BOQ.
        [5 review aspects: completeness, consistency, reasonableness,
         construction logic, missing items]
        [Context about IFC model scope]
        [Severity level definitions]
        [Language instruction if not English]
        Respond with a JSON object with assessment, confidence, issues, summary.

User:   {"building": {...}, "materials": [...], "key_ratios": {...},
         "boq_summary": {...}}
```

---

## What Users Can and Cannot Control

### Users Can

- Choose the output language (English, Turkish, Arabic), which affects material names and report labels
- Review all AI-generated content in the BOQ and Audit Trail
- See AI validation warnings in the final report
- Customize waste factors by editing `src/data/waste_factors.json`
- Customize reference material rules by editing `src/data/element_rules.json`
- Change the AI model via environment variables

### Users Cannot

- Disable AI for classification or material mapping (these stages require AI)
- Override individual AI decisions per element (the system processes all elements uniformly)
- Access or modify the prompts through the web interface (prompts are in source code)
- Prevent data from being sent to the Anthropic API (required for operation)

---

## Cost Considerations

Each IFC file processing run makes multiple API calls to Claude:

| Agent | Calls Per Run | Model | Typical Tokens |
|---|---|---|---|
| Classifier | 1 per 50 elements | Haiku | ~2K in, ~1K out per batch |
| Material Mapper | 1 per 50 elements (per type) | Sonnet | ~4K in, ~4K out per batch |
| Validator | 1 | Sonnet | ~3K in, ~2K out |

For a typical building with 100-200 elements, expect 5-10 API calls totaling roughly 30K-60K input tokens and 15K-30K output tokens. Prompt caching significantly reduces costs for the Material Mapper, which reuses the same system prompt across batches.
