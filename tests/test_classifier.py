"""
Tests for the ClassifierAgent with mocked AI.

The AI is mocked with a deterministic classifier that simulates
what Claude would return, so tests don't need a real API key.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.models.project import ElementCategory, ProcessingStatus
from src.agents.ifc_parser import IFCParserAgent
from src.agents.classifier import ClassifierAgent

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_IFC = FIXTURES_DIR / "simple_house.ifc"


def _mock_classify(elements_json: str) -> dict:
    """Simulate AI classification based on IFC types and properties.

    This mirrors the logic that Claude AI would apply, using the same
    rules described in the classifier system prompt.
    """
    data = json.loads(elements_json)
    result = {}

    for elem in data["elements"]:
        elem_id = str(elem["id"])
        ifc_type = elem["type"]
        name = elem.get("name", "").lower()
        is_external = elem.get("is_external")

        if ifc_type == "IfcDoor":
            result[elem_id] = "doors"
        elif ifc_type == "IfcWindow":
            result[elem_id] = "windows"
        elif ifc_type in ("IfcColumn", "IfcBeam"):
            result[elem_id] = "frame"
        elif ifc_type in ("IfcStair", "IfcStairFlight"):
            result[elem_id] = "stairs"
        elif ifc_type == "IfcRoof":
            result[elem_id] = "roof"
        elif ifc_type in ("IfcFooting", "IfcPile"):
            result[elem_id] = "substructure"
        elif ifc_type == "IfcWall":
            if is_external:
                result[elem_id] = "external_walls"
            else:
                result[elem_id] = "internal_walls"
        elif ifc_type == "IfcSlab":
            if "ground" in name or "foundation" in name:
                result[elem_id] = "substructure"
            elif "roof" in name:
                result[elem_id] = "roof"
            else:
                result[elem_id] = "upper_floors"
        else:
            result[elem_id] = "frame"

    return result


def _create_mock_llm():
    """Create a mock LLMService that returns deterministic classifications."""
    mock = MagicMock()

    async def mock_ask_json(system_prompt, user_message, **kwargs):
        return _mock_classify(user_message)

    mock.ask_json = AsyncMock(side_effect=mock_ask_json)
    return mock


def _get_parsed_state() -> dict:
    """Helper: run the parser first to get a state with parsed elements."""
    agent = IFCParserAgent()
    state = {
        "ifc_file_path": str(SAMPLE_IFC),
        "project_config": {},
        "parsed_elements": [],
        "building_info": None,
        "classified_elements": {},
        "calculated_quantities": [],
        "material_list": [],
        "boq_data": None,
        "boq_file_paths": {},
        "validation_report": None,
        "warnings": [],
        "errors": [],
        "status": ProcessingStatus.PENDING,
        "current_step": "",
        "processing_log": [],
    }
    return asyncio.run(agent.execute(state))


class TestClassifierAgent:
    """Tests for the Classifier Agent with mocked AI."""

    def setup_method(self):
        self.state = _get_parsed_state()

    def test_classifier_runs(self):
        classifier = ClassifierAgent(llm_service=_create_mock_llm())
        result = asyncio.run(classifier.execute(self.state))

        assert len(result["classified_elements"]) > 0

        for elem in result["parsed_elements"]:
            assert elem["category"] is not None, (
                f"Element {elem['name']} ({elem['ifc_type']}) has no category"
            )

    def test_external_walls_classified(self):
        classifier = ClassifierAgent(llm_service=_create_mock_llm())
        result = asyncio.run(classifier.execute(self.state))

        ext_wall_ids = result["classified_elements"].get(
            ElementCategory.EXTERNAL_WALLS.value, []
        )
        assert len(ext_wall_ids) == 8

    def test_internal_walls_classified(self):
        classifier = ClassifierAgent(llm_service=_create_mock_llm())
        result = asyncio.run(classifier.execute(self.state))

        int_wall_ids = result["classified_elements"].get(
            ElementCategory.INTERNAL_WALLS.value, []
        )
        assert len(int_wall_ids) == 5

    def test_doors_classified(self):
        classifier = ClassifierAgent(llm_service=_create_mock_llm())
        result = asyncio.run(classifier.execute(self.state))

        door_ids = result["classified_elements"].get(
            ElementCategory.DOORS.value, []
        )
        assert len(door_ids) == 8

    def test_windows_classified(self):
        classifier = ClassifierAgent(llm_service=_create_mock_llm())
        result = asyncio.run(classifier.execute(self.state))

        window_ids = result["classified_elements"].get(
            ElementCategory.WINDOWS.value, []
        )
        assert len(window_ids) == 10

    def test_columns_classified_as_frame(self):
        classifier = ClassifierAgent(llm_service=_create_mock_llm())
        result = asyncio.run(classifier.execute(self.state))

        frame_ids = result["classified_elements"].get(
            ElementCategory.FRAME.value, []
        )
        assert len(frame_ids) == 22

    def test_slabs_classified(self):
        classifier = ClassifierAgent(llm_service=_create_mock_llm())
        result = asyncio.run(classifier.execute(self.state))

        upper = result["classified_elements"].get(ElementCategory.UPPER_FLOORS.value, [])
        roof = result["classified_elements"].get(ElementCategory.ROOF.value, [])
        sub = result["classified_elements"].get(ElementCategory.SUBSTRUCTURE.value, [])
        assert len(upper) == 1
        assert len(roof) == 1
        assert len(sub) == 1

    def test_all_elements_accounted_for(self):
        classifier = ClassifierAgent(llm_service=_create_mock_llm())
        result = asyncio.run(classifier.execute(self.state))

        total_classified = sum(
            len(ids)
            for ids in result["classified_elements"].values()
        )
        assert total_classified == 56

    def test_invalid_category_ignored(self):
        """AI returning an invalid category should not crash."""
        mock_llm = MagicMock()
        mock_llm.ask_json = AsyncMock(
            return_value={"1": "invalid_category", "2": "frame"}
        )

        classifier = ClassifierAgent(llm_service=mock_llm)
        state = {
            "parsed_elements": [
                {"ifc_id": 1, "ifc_type": "IfcWall", "name": "W1"},
                {"ifc_id": 2, "ifc_type": "IfcColumn", "name": "C1"},
            ],
            "classified_elements": {},
            "warnings": [],
            "errors": [],
            "status": ProcessingStatus.PENDING,
            "current_step": "",
            "processing_log": [],
        }
        result = asyncio.run(classifier.execute(state))

        assert result["classified_elements"].get("frame") == [2]
        assert result["parsed_elements"][0].get("category") is None

    def test_ai_failure_handled_gracefully(self):
        """If AI call fails, errors are logged but no crash."""
        mock_llm = MagicMock()
        mock_llm.ask_json = AsyncMock(side_effect=RuntimeError("API error"))

        classifier = ClassifierAgent(llm_service=mock_llm)
        state = {
            "parsed_elements": [
                {"ifc_id": 1, "ifc_type": "IfcWall", "name": "W1"},
            ],
            "classified_elements": {},
            "warnings": [],
            "errors": [],
            "status": ProcessingStatus.PENDING,
            "current_step": "",
            "processing_log": [],
        }
        result = asyncio.run(classifier.execute(state))
        assert any("Classification failed" in e for e in result["errors"])
