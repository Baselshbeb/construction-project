"""
Prompt templates for the Material Mapper Agent.

Coach Simple explains:
    "We tell Claude: 'You're a quantity surveyor. Here's a concrete column
    that's 0.27 m3. What materials do we need to build it?' Claude knows
    that columns need concrete, steel, and formwork - and knows the right
    ratios even for unusual element types."
"""

from __future__ import annotations

import json
from typing import Any


MAPPER_SYSTEM_TEMPLATE = """\
You are an expert construction quantity surveyor specializing in material \
estimation (metraj). Given building elements with their IFC types, properties, \
and calculated quantities, determine ALL construction materials needed.

For each element, produce a materials list. Each material must have:
- name: Material description (e.g., "Concrete C25/30", "Reinforcement steel B500")
- unit: One of: m2, m3, m, kg, nr, set, litre
- source: Exact description of the calculated quantity to use as basis \
  (must match one of the element's quantity descriptions)
- multiplier: Factor to apply to source quantity (default 1.0). \
  For steel use kg/m3 ratios, for bricks use nr/m2 ratios, etc.
- waste_key: Key for waste factor lookup from the table below, OR
- waste_value: Direct waste factor as a decimal (e.g., 0.05 for 5%)
- note: Brief explanation (optional)

WASTE FACTORS (use these keys in waste_key):
{waste_factors}

REFERENCE EXAMPLES (standard concrete construction mappings):
{element_rules}

IMPORTANT MATERIAL ESTIMATION PRINCIPLES:
1. STRUCTURAL: Always include primary structural material (concrete/steel/timber) \
   + reinforcement + formwork where applicable
2. FINISHES: Include plaster, paint, tiles, screed as appropriate for the element \
   type and position (internal vs external)
3. WATERPROOFING: Ground slabs, basements, and wet areas need waterproofing membrane
4. INSULATION: External walls and roofs typically need thermal insulation
5. REINFORCEMENT RATIOS (kg of steel per m3 of concrete):
   - Foundations: 60-80 kg/m3
   - Walls: 60-80 kg/m3 (structural), less for non-structural
   - Slabs: 80-120 kg/m3
   - Columns: 130-180 kg/m3
   - Beams: 100-150 kg/m3
   - Stairs: 100-120 kg/m3
6. FORMWORK: All cast-in-place concrete elements need formwork
7. CONTEXT MATTERS: Check IFC materials list for hints (steel structure vs concrete, \
   timber frame, etc.). Adapt materials accordingly.
8. For doors/windows: Include the unit itself + frame + hardware. \
   These are counted items with 0% waste.
9. For unknown/complex elements: Use your construction engineering knowledge \
   to determine the most likely materials.

Respond with a JSON object containing an "elements" array."""

# Language-specific instructions appended to the system prompt
MAPPER_LANGUAGE_INSTRUCTIONS = {
    "en": "",
    "tr": (
        "\n\nLANGUAGE: Write ALL material names and descriptions in TURKISH. "
        "Examples: 'Beton C25/30', 'Donatı Çeliği B500', 'Kalıp', "
        "'Alçı Sıva', 'İç Cephe Boyası', 'Dış Cephe Boyası', "
        "'Su Yalıtım Membranı', 'Isı Yalıtımı'. "
        "Keep units in SI (m2, m3, kg, etc.). Keep JSON keys in English."
    ),
    "ar": (
        "\n\nLANGUAGE: Write ALL material names and descriptions in ARABIC. "
        "Examples: 'خرسانة C25/30', 'حديد تسليح B500', 'قوالب صب', "
        "'لياسة جبس', 'طلاء داخلي', 'طلاء خارجي', "
        "'غشاء عزل مائي', 'عزل حراري'. "
        "Keep units in SI (m2, m3, kg, etc.). Keep JSON keys in English."
    ),
}


def get_mapper_system_prompt(
    waste_factors: dict, element_rules: dict, language: str = "en",
) -> str:
    """Build the system prompt with waste factors, rules, and language injected."""
    # Clean up rules for readability - remove the _description key
    clean_rules = {k: v for k, v in element_rules.items() if k != "_description"}

    base = MAPPER_SYSTEM_TEMPLATE.format(
        waste_factors=json.dumps(waste_factors, indent=2),
        element_rules=json.dumps(clean_rules, indent=2),
    )
    return base + MAPPER_LANGUAGE_INSTRUCTIONS.get(language, "")


def build_mapper_message(elements: list[dict[str, Any]]) -> str:
    """Build the user message for a batch of elements.

    Each element includes its type, properties, IFC materials, and
    all calculated quantities.
    """
    batch = []
    for e in elements:
        entry: dict[str, Any] = {
            "element_id": e["element_id"],
            "ifc_type": e["ifc_type"],
        }
        if e.get("name"):
            entry["name"] = e["name"]
        if e.get("is_external") is not None:
            entry["is_external"] = e["is_external"]
        if e.get("category"):
            entry["category"] = e["category"]
        if e.get("ifc_materials"):
            entry["ifc_materials"] = e["ifc_materials"]
        if e.get("quantities"):
            entry["quantities"] = e["quantities"]

        batch.append(entry)

    return json.dumps({
        "element_count": len(batch),
        "elements": batch,
    }, indent=2)
