"""
Tests for AI-integrated agents (Classifier, Material Mapper, Validator).

All tests use mocked LLMService to avoid real API calls.
These tests verify:
- AI response parsing and application
- Error handling when AI fails
- Edge cases in AI response processing
- Integration between AI results and pipeline state
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.classifier import ClassifierAgent
from src.agents.material_mapper import MaterialMapperAgent
from src.agents.validator import ValidatorAgent
from src.models.project import ProcessingStatus


def _make_state(**overrides):
    """Build a minimal pipeline state dict."""
    state = {
        "parsed_elements": [],
        "classified_elements": {},
        "calculated_quantities": [],
        "material_list": [],
        "building_info": {},
        "boq_data": None,
        "warnings": [],
        "errors": [],
        "status": ProcessingStatus.PENDING,
        "current_step": "",
        "processing_log": [],
    }
    state.update(overrides)
    return state


# =====================================================================
# Classifier Agent Tests
# =====================================================================

class TestClassifierAI:
    def _make_classifier(self, ai_response):
        """Create a classifier with mocked AI returning given response."""
        mock_llm = MagicMock()
        mock_llm.ask_json = AsyncMock(return_value=ai_response)
        return ClassifierAgent(llm_service=mock_llm)

    @pytest.mark.asyncio
    async def test_applies_ai_categories(self):
        """AI response categories are applied to elements."""
        classifier = self._make_classifier({
            "1": "frame",
            "2": "external_walls",
            "3": "doors",
        })
        state = _make_state(parsed_elements=[
            {"ifc_id": 1, "ifc_type": "IfcColumn", "name": "C1"},
            {"ifc_id": 2, "ifc_type": "IfcWall", "name": "W1"},
            {"ifc_id": 3, "ifc_type": "IfcDoor", "name": "D1"},
        ])

        result = await classifier.execute(state)

        assert result["parsed_elements"][0]["category"] == "frame"
        assert result["parsed_elements"][1]["category"] == "external_walls"
        assert result["parsed_elements"][2]["category"] == "doors"

    @pytest.mark.asyncio
    async def test_builds_classified_elements_index(self):
        """classified_elements dict groups element IDs by category."""
        classifier = self._make_classifier({
            "1": "frame",
            "2": "frame",
            "3": "doors",
        })
        state = _make_state(parsed_elements=[
            {"ifc_id": 1, "ifc_type": "IfcColumn", "name": "C1"},
            {"ifc_id": 2, "ifc_type": "IfcBeam", "name": "B1"},
            {"ifc_id": 3, "ifc_type": "IfcDoor", "name": "D1"},
        ])

        result = await classifier.execute(state)

        assert set(result["classified_elements"]["frame"]) == {1, 2}
        assert result["classified_elements"]["doors"] == [3]

    @pytest.mark.asyncio
    async def test_empty_elements_returns_early(self):
        """No elements -> no AI call, no crash."""
        mock_llm = MagicMock()
        mock_llm.ask_json = AsyncMock()
        classifier = ClassifierAgent(llm_service=mock_llm)

        state = _make_state()
        result = await classifier.execute(state)

        mock_llm.ask_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_processing_log_updated(self):
        """Processing log records classification summary."""
        classifier = self._make_classifier({"1": "frame"})
        state = _make_state(parsed_elements=[
            {"ifc_id": 1, "ifc_type": "IfcColumn", "name": "C1"},
        ])

        result = await classifier.execute(state)
        assert any("Classifier" in entry for entry in result["processing_log"])

    @pytest.mark.asyncio
    async def test_status_set_to_classifying(self):
        """Status is set to CLASSIFYING during execution."""
        classifier = self._make_classifier({"1": "frame"})
        state = _make_state(parsed_elements=[
            {"ifc_id": 1, "ifc_type": "IfcColumn", "name": "C1"},
        ])

        result = await classifier.execute(state)
        # After execution, status may still be CLASSIFYING (no status update at end)
        assert result["status"] == ProcessingStatus.CLASSIFYING


# =====================================================================
# Material Mapper Agent Tests
# =====================================================================

class TestMaterialMapperAI:
    def _make_mapper(self, ai_response):
        """Create a mapper with mocked AI returning given response."""
        mock_llm = MagicMock()
        mock_llm.ask_json = AsyncMock(return_value=ai_response)
        return MaterialMapperAgent(llm_service=mock_llm)

    @pytest.mark.asyncio
    async def test_maps_elements_to_materials(self):
        """AI materials are processed and added to material_list."""
        mapper = self._make_mapper({
            "elements": [{
                "element_id": 1,
                "materials": [
                    {
                        "name": "Concrete C30/37",
                        "unit": "m3",
                        "source": "Slab volume",
                        "multiplier": 1.0,
                        "waste_key": "concrete.standard",
                    },
                ],
            }]
        })

        state = _make_state(
            parsed_elements=[
                {"ifc_id": 1, "ifc_type": "IfcSlab", "name": "S1",
                 "category": "upper_floors", "materials": []},
            ],
            calculated_quantities=[
                {"element_id": 1, "quantities": [
                    {"description": "Slab volume", "quantity": 24.0},
                ]},
            ],
        )

        result = await mapper.execute(state)

        assert len(result["material_list"]) == 1
        mat = result["material_list"][0]
        assert mat["description"] == "Concrete C30/37"
        assert mat["quantity"] == 24.0
        assert mat["waste_factor"] == 0.05
        assert mat["total_quantity"] == 25.2

    @pytest.mark.asyncio
    async def test_batches_by_ifc_type(self):
        """Elements are grouped by IFC type for batch API calls."""
        mock_llm = MagicMock()

        async def check_batches(system_prompt, user_message, **kwargs):
            # Return empty elements to simplify
            return {"elements": []}

        mock_llm.ask_json = AsyncMock(side_effect=check_batches)
        mapper = MaterialMapperAgent(llm_service=mock_llm)

        state = _make_state(
            parsed_elements=[
                {"ifc_id": 1, "ifc_type": "IfcColumn", "name": "C1",
                 "category": "frame", "materials": []},
                {"ifc_id": 2, "ifc_type": "IfcColumn", "name": "C2",
                 "category": "frame", "materials": []},
                {"ifc_id": 3, "ifc_type": "IfcWall", "name": "W1",
                 "category": "external_walls", "materials": []},
            ],
            calculated_quantities=[
                {"element_id": 1, "quantities": []},
                {"element_id": 2, "quantities": []},
                {"element_id": 3, "quantities": []},
            ],
        )

        await mapper.execute(state)

        # Should be called twice: once for IfcColumn batch, once for IfcWall batch
        assert mock_llm.ask_json.call_count == 2

    @pytest.mark.asyncio
    async def test_aggregates_same_materials(self):
        """Same material from multiple elements is aggregated."""
        mapper = self._make_mapper({
            "elements": [
                {
                    "element_id": 1,
                    "materials": [{
                        "name": "Concrete C25/30",
                        "unit": "m3",
                        "source": "Column volume",
                        "multiplier": 1.0,
                        "waste_key": "concrete.standard",
                    }],
                },
                {
                    "element_id": 2,
                    "materials": [{
                        "name": "Concrete C25/30",
                        "unit": "m3",
                        "source": "Column volume",
                        "multiplier": 1.0,
                        "waste_key": "concrete.standard",
                    }],
                },
            ]
        })

        state = _make_state(
            parsed_elements=[
                {"ifc_id": 1, "ifc_type": "IfcColumn", "name": "C1",
                 "category": "frame", "materials": []},
                {"ifc_id": 2, "ifc_type": "IfcColumn", "name": "C2",
                 "category": "frame", "materials": []},
            ],
            calculated_quantities=[
                {"element_id": 1, "quantities": [
                    {"description": "Column volume", "quantity": 0.27},
                ]},
                {"element_id": 2, "quantities": [
                    {"description": "Column volume", "quantity": 0.35},
                ]},
            ],
        )

        result = await mapper.execute(state)

        # Should aggregate to single concrete entry
        concretes = [m for m in result["material_list"] if "Concrete" in m["description"]]
        assert len(concretes) == 1
        assert concretes[0]["quantity"] == 0.62  # 0.27 + 0.35

    @pytest.mark.asyncio
    async def test_empty_elements_returns_early(self):
        """No elements -> no AI call."""
        mock_llm = MagicMock()
        mock_llm.ask_json = AsyncMock()
        mapper = MaterialMapperAgent(llm_service=mock_llm)

        state = _make_state()
        await mapper.execute(state)

        mock_llm.ask_json.assert_not_called()


# =====================================================================
# Validator Agent Tests
# =====================================================================

class TestValidatorAI:
    @pytest.mark.asyncio
    async def test_ai_warnings_added(self):
        """AI review warnings are added to the warnings list."""
        mock_llm = MagicMock()
        mock_llm.ask_json = AsyncMock(return_value={
            "overall_assessment": "acceptable",
            "confidence": 0.85,
            "summary": "Generally reasonable BOQ",
            "issues": [
                {"severity": "warning", "message": "Missing waterproofing for basement"},
            ],
        })

        validator = ValidatorAgent(llm_service=mock_llm)
        state = _make_state(
            parsed_elements=[{"ifc_id": 1, "category": "frame"}],
            material_list=[
                {"description": "Concrete", "unit": "m3",
                 "quantity": 10, "total_quantity": 10.5},
            ],
            calculated_quantities=[{"element_id": 1, "quantities": []}],
        )

        result = await validator.execute(state)

        assert any("[AI Review]" in w for w in result["warnings"])
        assert result["validation_report"]["ai_assessment"] == "acceptable"

    @pytest.mark.asyncio
    async def test_ai_errors_added(self):
        """AI review errors are added to the errors list and cause FAIL."""
        mock_llm = MagicMock()
        mock_llm.ask_json = AsyncMock(return_value={
            "overall_assessment": "problematic",
            "confidence": 0.9,
            "summary": "Critical issues found",
            "issues": [
                {"severity": "error", "message": "No foundation materials found"},
            ],
        })

        validator = ValidatorAgent(llm_service=mock_llm)
        state = _make_state(
            parsed_elements=[{"ifc_id": 1, "category": "frame"}],
            material_list=[
                {"description": "Concrete", "unit": "m3",
                 "quantity": 10, "total_quantity": 10.5},
            ],
            calculated_quantities=[{"element_id": 1, "quantities": []}],
        )

        result = await validator.execute(state)

        assert any("[AI Review]" in e for e in result["errors"])
        assert result["status"] == ProcessingStatus.FAILED

    @pytest.mark.asyncio
    async def test_ai_failure_non_critical(self):
        """If AI validation fails, arithmetic checks still complete."""
        mock_llm = MagicMock()
        mock_llm.ask_json = AsyncMock(side_effect=RuntimeError("API error"))

        validator = ValidatorAgent(llm_service=mock_llm)
        state = _make_state(
            parsed_elements=[{"ifc_id": 1, "category": "frame"}],
            material_list=[
                {"description": "Concrete", "unit": "m3",
                 "quantity": 10, "total_quantity": 10.5},
            ],
            calculated_quantities=[{"element_id": 1, "quantities": []}],
        )

        result = await validator.execute(state)

        # Arithmetic checks still ran
        assert result["validation_report"]["checks"]["elements_parsed"] is True
        assert result["validation_report"]["checks"]["materials_mapped"] is True
        # Status should be COMPLETED (no arithmetic errors)
        assert result["status"] == ProcessingStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_ai_info_issues_logged_not_warned(self):
        """AI 'info' severity issues are logged but not added to warnings."""
        mock_llm = MagicMock()
        mock_llm.ask_json = AsyncMock(return_value={
            "overall_assessment": "good",
            "confidence": 0.95,
            "summary": "All good",
            "issues": [
                {"severity": "info", "message": "Steel ratio is on the high end"},
            ],
        })

        validator = ValidatorAgent(llm_service=mock_llm)
        state = _make_state(
            parsed_elements=[{"ifc_id": 1, "category": "frame"}],
            material_list=[
                {"description": "Concrete", "unit": "m3",
                 "quantity": 10, "total_quantity": 10.5},
            ],
            calculated_quantities=[{"element_id": 1, "quantities": []}],
        )

        result = await validator.execute(state)

        # Info issues should NOT appear in warnings
        assert not any("Steel ratio" in w for w in result["warnings"])
        # Status should be COMPLETED
        assert result["status"] == ProcessingStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_ai_assessment_in_report(self):
        """AI assessment details are included in the validation report."""
        mock_llm = MagicMock()
        mock_llm.ask_json = AsyncMock(return_value={
            "overall_assessment": "good",
            "confidence": 0.92,
            "summary": "Reasonable BOQ for a 2-storey house",
            "issues": [],
        })

        validator = ValidatorAgent(llm_service=mock_llm)
        state = _make_state(
            parsed_elements=[{"ifc_id": 1, "category": "frame"}],
            material_list=[
                {"description": "Concrete", "unit": "m3",
                 "quantity": 10, "total_quantity": 10.5},
            ],
            calculated_quantities=[{"element_id": 1, "quantities": []}],
        )

        result = await validator.execute(state)
        report = result["validation_report"]

        assert report["ai_assessment"] == "good"
        assert report["ai_confidence"] == 0.92
        assert report["ai_summary"] == "Reasonable BOQ for a 2-storey house"
