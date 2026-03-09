"""
Tests for the Element Classifier Agent.
"""

import asyncio
from pathlib import Path

from src.models.project import ElementCategory, ProcessingStatus
from src.agents.ifc_parser import IFCParserAgent
from src.agents.classifier import ClassifierAgent

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_IFC = FIXTURES_DIR / "simple_house.ifc"


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
    """Tests for the Classifier Agent."""

    def setup_method(self):
        self.state = _get_parsed_state()

    def test_classifier_runs(self):
        classifier = ClassifierAgent()
        result = asyncio.run(classifier.execute(self.state))

        # classified_elements should be populated
        assert len(result["classified_elements"]) > 0

        # Every element should have a category
        for elem in result["parsed_elements"]:
            assert elem["category"] is not None, (
                f"Element {elem['name']} ({elem['ifc_type']}) has no category"
            )

    def test_external_walls_classified(self):
        classifier = ClassifierAgent()
        result = asyncio.run(classifier.execute(self.state))

        ext_wall_ids = result["classified_elements"].get(
            ElementCategory.EXTERNAL_WALLS.value, []
        )
        # 8 external walls (4 per floor)
        assert len(ext_wall_ids) == 8

    def test_internal_walls_classified(self):
        classifier = ClassifierAgent()
        result = asyncio.run(classifier.execute(self.state))

        int_wall_ids = result["classified_elements"].get(
            ElementCategory.INTERNAL_WALLS.value, []
        )
        # 5 internal walls (2 ground + 3 first floor)
        assert len(int_wall_ids) == 5

    def test_doors_classified(self):
        classifier = ClassifierAgent()
        result = asyncio.run(classifier.execute(self.state))

        door_ids = result["classified_elements"].get(
            ElementCategory.DOORS.value, []
        )
        assert len(door_ids) == 8

    def test_windows_classified(self):
        classifier = ClassifierAgent()
        result = asyncio.run(classifier.execute(self.state))

        window_ids = result["classified_elements"].get(
            ElementCategory.WINDOWS.value, []
        )
        assert len(window_ids) == 10

    def test_columns_classified_as_frame(self):
        classifier = ClassifierAgent()
        result = asyncio.run(classifier.execute(self.state))

        frame_ids = result["classified_elements"].get(
            ElementCategory.FRAME.value, []
        )
        # 12 columns + 10 beams = 22 frame elements
        assert len(frame_ids) == 22

    def test_slabs_classified(self):
        classifier = ClassifierAgent()
        result = asyncio.run(classifier.execute(self.state))

        # Slabs are split across categories based on their name/location:
        # "Ground Floor Slab" -> substructure (1)
        # "First Floor Slab" -> upper_floors (1)
        # "Roof Slab" -> roof (1)
        upper = result["classified_elements"].get(ElementCategory.UPPER_FLOORS.value, [])
        roof = result["classified_elements"].get(ElementCategory.ROOF.value, [])
        sub = result["classified_elements"].get(ElementCategory.SUBSTRUCTURE.value, [])
        assert len(upper) == 1
        assert len(roof) == 1
        assert len(sub) == 1

    def test_all_elements_accounted_for(self):
        classifier = ClassifierAgent()
        result = asyncio.run(classifier.execute(self.state))

        total_classified = sum(
            len(ids)
            for ids in result["classified_elements"].values()
        )
        # All 56 elements should be classified
        assert total_classified == 56
