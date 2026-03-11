"""
Validation Agent - cross-checks all quantities and materials for errors
using both arithmetic checks and Claude AI intelligent review.

Coach Simple explains:
    "Before we hand the shopping list to the client, we need someone
    to double-check it. First we run quick math checks (any negatives?
    is the concrete ratio reasonable?). Then we ask Claude - a senior
    engineer - to review the whole BOQ and spot things math can't catch,
    like missing waterproofing or contradictory materials."

Pipeline position: LAST agent (after BOQ Generator)
Input: ProjectState with material_list and calculated_quantities
Output: ProjectState with validation_report, warnings, errors
"""

from __future__ import annotations

from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.project import ProcessingStatus
from src.prompts.validator_prompts import (
    VALIDATOR_SYSTEM_PROMPT,
    build_validator_message,
)
from src.services.llm_service import LLMService
from src.utils.logger import get_logger

logger = get_logger("validator")


class ValidatorAgent(BaseAgent):
    """Validates quantities and materials using arithmetic checks + AI review."""

    def __init__(self, llm_service: LLMService | None = None):
        super().__init__(
            name="validator",
            description="Cross-checks quantities and materials for errors and inconsistencies",
        )
        self.llm = llm_service or LLMService()

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Validate the entire pipeline output."""
        self.log("Starting validation...")
        state["status"] = ProcessingStatus.VALIDATING
        state["current_step"] = "Validating results"

        warnings = list(state.get("warnings", []))
        errors = list(state.get("errors", []))

        elements = state.get("parsed_elements", [])
        materials = state.get("material_list", [])
        calc_quantities = state.get("calculated_quantities", [])
        building_info = state.get("building_info", {})

        checks = {
            "elements_parsed": False,
            "elements_classified": False,
            "quantities_calculated": False,
            "materials_mapped": False,
            "no_negative_quantities": False,
            "concrete_ratio_reasonable": False,
            "all_storeys_have_elements": False,
            "steel_ratio_reasonable": False,
        }

        # --- Check 1: Elements were parsed ---
        if elements:
            checks["elements_parsed"] = True
            self.log(f"  Elements parsed: {len(elements)}")
        else:
            errors.append("No elements were parsed from the IFC file")

        # --- Check 2: All elements classified ---
        unclassified = [e for e in elements if not e.get("category")]
        if not unclassified:
            checks["elements_classified"] = True
        else:
            warnings.append(
                f"{len(unclassified)} elements have no category assigned"
            )

        # --- Check 3: Quantities calculated ---
        if calc_quantities:
            checks["quantities_calculated"] = True
        else:
            errors.append("No quantities were calculated")

        # --- Check 4: Materials mapped ---
        if materials:
            checks["materials_mapped"] = True
            self.log(f"  Materials mapped: {len(materials)} unique items")
        else:
            errors.append("No materials were mapped")

        # --- Check 5: No negative quantities ---
        negative_found = False
        for mat in materials:
            if mat.get("quantity", 0) < 0 or mat.get("total_quantity", 0) < 0:
                negative_found = True
                errors.append(
                    f"Negative quantity for {mat['description']}: {mat['quantity']}"
                )
        if not negative_found:
            checks["no_negative_quantities"] = True

        # --- Check 6: Concrete ratio reasonable ---
        total_concrete = sum(
            m["total_quantity"]
            for m in materials
            if "concrete" in m["description"].lower() and m["unit"] == "m3"
        )
        total_floor_area = sum(
            q["quantity"]
            for cq in calc_quantities
            for q in cq.get("quantities", [])
            if "slab area (top" in q.get("description", "").lower()
        )

        if total_floor_area > 0 and total_concrete > 0:
            ratio = total_concrete / total_floor_area
            self.log(f"  Concrete ratio: {ratio:.2f} m3/m2 floor area")
            if 0.1 <= ratio <= 1.5:
                checks["concrete_ratio_reasonable"] = True
            else:
                warnings.append(
                    f"Concrete ratio ({ratio:.2f} m3/m2) seems unusual. "
                    f"Expected 0.1-1.5 m3/m2 for typical buildings."
                )
        else:
            checks["concrete_ratio_reasonable"] = True  # Can't check, pass

        # --- Check 7: All storeys have elements ---
        storeys = building_info.get("storeys", []) if isinstance(building_info, dict) else []
        if storeys:
            storeys_with_elements = set(
                e.get("storey") for e in elements if e.get("storey")
            )
            missing_storeys = set(storeys) - storeys_with_elements
            if not missing_storeys:
                checks["all_storeys_have_elements"] = True
            else:
                warnings.append(
                    f"Storeys with no elements: {missing_storeys}"
                )
        else:
            checks["all_storeys_have_elements"] = True

        # --- Check 8: Steel-to-concrete ratio ---
        total_steel = sum(
            m["total_quantity"]
            for m in materials
            if "reinforcement" in m["description"].lower() and m["unit"] == "kg"
        )

        if total_concrete > 0 and total_steel > 0:
            steel_ratio = total_steel / total_concrete
            self.log(f"  Steel ratio: {steel_ratio:.0f} kg/m3 concrete")
            if 50 <= steel_ratio <= 200:
                checks["steel_ratio_reasonable"] = True
            else:
                warnings.append(
                    f"Steel-to-concrete ratio ({steel_ratio:.0f} kg/m3) "
                    f"seems unusual. Expected 50-200 kg/m3."
                )
        else:
            checks["steel_ratio_reasonable"] = True

        # --- AI-powered intelligent validation ---
        # AI issues are advisory - they should NEVER block the pipeline.
        # Even AI "errors" are downgraded to warnings because only the
        # arithmetic checks above should be able to fail the pipeline.
        ai_assessment = await self._ai_validate(state)
        if ai_assessment:
            for issue in ai_assessment.get("issues", []):
                severity = issue.get("severity", "info")
                message = issue.get("message", "")
                if severity in ("error", "warning"):
                    warnings.append(f"[AI Review] {message}")
                else:
                    self.log(f"  [AI Info] {message}")

        # --- Build validation report ---
        passed = sum(1 for v in checks.values() if v)
        total = len(checks)

        validation_report = {
            "checks": checks,
            "passed": passed,
            "total": total,
            "score": f"{passed}/{total}",
            "status": "PASS" if not errors else "FAIL",
            "summary": {
                "total_elements": len(elements),
                "total_materials": len(materials),
                "total_concrete_m3": round(total_concrete, 2),
                "total_steel_kg": round(total_steel, 2),
                "total_floor_area_m2": round(total_floor_area, 2),
            },
        }

        # Add AI assessment to report if available
        if ai_assessment:
            validation_report["ai_assessment"] = ai_assessment.get("overall_assessment")
            validation_report["ai_confidence"] = ai_assessment.get("confidence")
            validation_report["ai_summary"] = ai_assessment.get("summary")

        state["validation_report"] = validation_report
        state["warnings"] = warnings
        state["errors"] = errors

        if errors:
            state["status"] = ProcessingStatus.FAILED
            self.log_error(f"Validation FAILED: {len(errors)} errors, {len(warnings)} warnings")
        else:
            state["status"] = ProcessingStatus.COMPLETED
            self.log(f"Validation PASSED: {passed}/{total} checks, {len(warnings)} warnings")

        state["processing_log"].append(
            f"Validator: {passed}/{total} checks passed, "
            f"{len(warnings)} warnings, {len(errors)} errors"
        )

        return state

    async def _ai_validate(self, state: dict[str, Any]) -> dict[str, Any] | None:
        """Run AI-powered intelligent validation on the full BOQ.

        Returns the AI's assessment or None if the call fails.
        """
        try:
            user_message = build_validator_message(
                elements=state.get("parsed_elements", []),
                materials=state.get("material_list", []),
                building_info=state.get("building_info"),
                boq_data=state.get("boq_data"),
                calc_quantities=state.get("calculated_quantities"),
            )

            result = await self.llm.ask_json(
                system_prompt=VALIDATOR_SYSTEM_PROMPT,
                user_message=user_message,
                temperature=0.1,
            )

            self.log(f"  AI assessment: {result.get('overall_assessment', 'N/A')}")
            if result.get("summary"):
                self.log(f"  AI summary: {result['summary']}")

            return result

        except Exception as e:
            self.log_warning(f"AI validation failed (non-critical): {e}")
            return None
