"""
Element Classifier Agent - categorizes building elements into BOQ sections
using Claude AI.

Coach Simple explains:
    "The parser gave us a pile of building pieces. Now we need to SORT them.
    We ask Claude - who knows construction inside and out - to look at each
    piece and tell us which pile it belongs to. Claude can handle even weird
    elements that simple rules would miss."

Pipeline position: SECOND agent
Input: ProjectState with parsed_elements
Output: ProjectState with category set on each element + classified_elements dict
"""

from __future__ import annotations

from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.project import ElementCategory, ProcessingStatus
from src.prompts.classifier_prompts import (
    CLASSIFIER_SYSTEM_PROMPT,
    build_classifier_message,
)
from src.services.llm_service import LLMService
from src.utils.logger import get_logger

logger = get_logger("classifier")

# Valid category values for validation
VALID_CATEGORIES = {cat.value for cat in ElementCategory}


class ClassifierAgent(BaseAgent):
    """Classifies building elements into BOQ categories using AI."""

    def __init__(self, llm_service: LLMService | None = None):
        super().__init__(
            name="classifier",
            description="Categorizes building elements into BOQ sections using AI",
        )
        self.llm = llm_service or LLMService()

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Classify all parsed elements into categories using Claude AI.

        Steps:
        1. Serialize all elements into compact format
        2. Send to Claude in one batch call
        3. Parse response and apply categories
        4. Build classified_elements index
        """
        self.log("Starting AI element classification...")
        state["status"] = ProcessingStatus.CLASSIFYING
        state["current_step"] = "Classifying elements"

        elements = state.get("parsed_elements", [])
        if not elements:
            self.log_warning("No elements to classify!")
            return state

        # Build the prompt message
        user_message = build_classifier_message(elements)

        # Call Claude AI
        try:
            ai_result = await self.llm.ask_json(
                system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                user_message=user_message,
                temperature=0.0,
            )
        except Exception as e:
            self.log_error(f"AI classification failed: {e}")
            state["warnings"].append(f"AI classification failed: {e}")
            state["errors"].append("Classification failed - no AI response")
            return state

        # Apply classifications from AI response
        classified: dict[str, list[int]] = {}
        unclassified = []

        for element in elements:
            elem_id = str(element["ifc_id"])
            category_str = ai_result.get(elem_id)

            if category_str and category_str in VALID_CATEGORIES:
                element["category"] = category_str
                if category_str not in classified:
                    classified[category_str] = []
                classified[category_str].append(element["ifc_id"])
            else:
                unclassified.append(element)
                self.log_warning(
                    f"AI did not classify: {element.get('ifc_type')} "
                    f"'{element.get('name')}' (got: {category_str})"
                )

        state["classified_elements"] = classified

        # Log summary
        self.log(f"Classified {len(elements) - len(unclassified)}/{len(elements)} elements:")
        for category, ids in sorted(classified.items()):
            self.log(f"  {category}: {len(ids)} elements")
        if unclassified:
            self.log_warning(f"  unclassified: {len(unclassified)} elements")

        state["processing_log"].append(
            f"Classifier: AI categorized {len(elements) - len(unclassified)} elements "
            f"into {len(classified)} categories"
        )

        return state
