"""
Tests for the MaterialMapperAgent - verifies waste factors, aggregation,
AI response processing, and edge cases.

AI calls are mocked so tests don't need a real API key.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.material_mapper import MaterialMapperAgent


def _create_mock_llm():
    """Create a mock LLMService for material mapping."""
    mock = MagicMock()
    return mock


@pytest.fixture
def mapper():
    return MaterialMapperAgent(llm_service=_create_mock_llm())


def make_element(ifc_id, ifc_type, is_external=False, materials=None, category=None):
    """Helper to create a minimal element dict."""
    return {
        "ifc_id": ifc_id,
        "ifc_type": ifc_type,
        "name": f"Test {ifc_type}",
        "is_external": is_external,
        "materials": materials or [],
        "category": category,
    }


def make_calc_qty(element_id, quantities):
    """Helper to create a calculated quantities entry."""
    return {
        "element_id": element_id,
        "element_type": "IfcWall",
        "quantities": quantities,
    }


# ---- Waste Factor Tests ----

class TestWasteFactor:
    def test_valid_waste_key(self, mapper):
        assert mapper._get_waste_factor("concrete.standard") == 0.05
        assert mapper._get_waste_factor("reinforcement_steel.standard") == 0.03
        assert mapper._get_waste_factor("formwork.standard") == 0.10
        assert mapper._get_waste_factor("plaster.internal") == 0.10
        assert mapper._get_waste_factor("plaster.external") == 0.12
        assert mapper._get_waste_factor("paint.standard") == 0.10
        assert mapper._get_waste_factor("bricks.standard") == 0.05
        assert mapper._get_waste_factor("mortar.standard") == 0.10

    def test_invalid_format_returns_default(self, mapper):
        """Malformed key (no dot) returns 5% default."""
        assert mapper._get_waste_factor("concrete") == 0.05
        assert mapper._get_waste_factor("") == 0.05

    def test_unknown_category_returns_default(self, mapper):
        """Unknown category returns 5% default."""
        assert mapper._get_waste_factor("unknown.standard") == 0.05

    def test_unknown_level_returns_default(self, mapper):
        """Known category but unknown level returns 5% default."""
        assert mapper._get_waste_factor("concrete.unknown") == 0.05


# ---- _apply_material_rule Tests ----

class TestApplyMaterialRule:
    def test_basic_rule(self, mapper):
        """Rule with exact source match, multiplier 1.0, waste key."""
        rule = {
            "name": "Concrete C25/30",
            "unit": "m3",
            "source": "Column volume",
            "multiplier": 1.0,
            "waste_key": "concrete.standard",
        }
        qty_lookup = {"Column volume": 10.0}
        element = {"ifc_id": 1, "category": "frame"}

        result = mapper._apply_material_rule(rule, qty_lookup, element)

        assert result is not None
        assert result["description"] == "Concrete C25/30"
        assert result["unit"] == "m3"
        assert result["quantity"] == 10.0
        assert result["waste_factor"] == 0.05
        assert result["total_quantity"] == 10.5

    def test_multiplier_applied(self, mapper):
        """Multiplier (e.g., 150 kg/m3 steel ratio) is applied to base qty."""
        rule = {
            "name": "Reinforcement steel",
            "unit": "kg",
            "source": "Column volume",
            "multiplier": 150.0,
            "waste_key": "reinforcement_steel.standard",
        }
        qty_lookup = {"Column volume": 2.0}
        element = {"ifc_id": 1, "category": "frame"}

        result = mapper._apply_material_rule(rule, qty_lookup, element)

        assert result["quantity"] == 300.0
        # 300 * 1.03 = 309
        assert result["total_quantity"] == 309.0

    def test_partial_source_matching(self, mapper):
        """If exact source key doesn't match, try partial matching."""
        rule = {
            "name": "Concrete",
            "unit": "m3",
            "source": "volume",
            "multiplier": 1.0,
            "waste_key": "concrete.standard",
        }
        qty_lookup = {"Slab volume": 5.0}
        element = {"ifc_id": 1, "category": "upper_floors"}

        result = mapper._apply_material_rule(rule, qty_lookup, element)

        assert result is not None
        assert result["quantity"] == 5.0

    def test_missing_source_returns_none(self, mapper):
        """Rule with a source that doesn't match any quantity returns None."""
        rule = {
            "name": "Concrete",
            "unit": "m3",
            "source": "nonexistent quantity",
            "multiplier": 1.0,
            "waste_key": "concrete.standard",
        }
        qty_lookup = {"Column volume": 10.0}
        element = {"ifc_id": 1, "category": "frame"}

        result = mapper._apply_material_rule(rule, qty_lookup, element)
        assert result is None

    def test_waste_value_used_directly(self, mapper):
        """waste_value takes precedence when waste_key is absent."""
        rule = {
            "name": "Door unit",
            "unit": "nr",
            "source": "Door count",
            "multiplier": 1.0,
            "waste_value": 0.0,
        }
        qty_lookup = {"Door count": 1}
        element = {"ifc_id": 1, "category": "doors"}

        result = mapper._apply_material_rule(rule, qty_lookup, element)

        assert result["waste_factor"] == 0.0
        assert result["quantity"] == result["total_quantity"]

    def test_source_elements_tracked(self, mapper):
        """Result includes the element's ifc_id in source_elements."""
        rule = {
            "name": "Paint",
            "unit": "m2",
            "source": "Wall area",
            "multiplier": 1.0,
            "waste_key": "paint.standard",
        }
        qty_lookup = {"Wall area": 30.0}
        element = {"ifc_id": 42, "category": "external_walls"}

        result = mapper._apply_material_rule(rule, qty_lookup, element)
        assert result["source_elements"] == [42]


# ---- _process_ai_materials Tests ----

class TestProcessAIMaterials:
    def test_processes_ai_response(self, mapper):
        """Converts AI element result with materials list to material dicts."""
        elements = [make_element(1, "IfcColumn", category="frame")]
        qty_lookup = {
            1: [
                {"description": "Column volume", "quantity": 0.27},
                {"description": "Column surface area", "quantity": 3.6},
            ]
        }
        ai_elem_result = {
            "element_id": 1,
            "materials": [
                {
                    "name": "Concrete C25/30",
                    "unit": "m3",
                    "source": "Column volume",
                    "multiplier": 1.0,
                    "waste_key": "concrete.standard",
                },
                {
                    "name": "Formwork",
                    "unit": "m2",
                    "source": "Column surface area",
                    "multiplier": 1.0,
                    "waste_key": "formwork.standard",
                },
            ],
        }

        result = mapper._process_ai_materials(ai_elem_result, qty_lookup, elements)

        assert len(result) == 2
        assert result[0]["description"] == "Concrete C25/30"
        assert result[1]["description"] == "Formwork"

    def test_unknown_element_id_returns_empty(self, mapper):
        """AI result for unknown element_id returns empty list."""
        elements = [make_element(1, "IfcColumn")]
        qty_lookup = {}
        ai_elem_result = {
            "element_id": 999,
            "materials": [{"name": "Concrete", "unit": "m3", "source": "x"}],
        }

        result = mapper._process_ai_materials(ai_elem_result, qty_lookup, elements)
        assert result == []

    def test_no_element_id_returns_empty(self, mapper):
        """AI result without element_id field returns empty list."""
        result = mapper._process_ai_materials(
            {"materials": []}, {}, [make_element(1, "IfcColumn")]
        )
        assert result == []


# ---- Aggregation Tests ----

class TestAggregation:
    def test_same_materials_aggregated(self, mapper):
        """Two entries of the same material are summed."""
        materials = [
            {"description": "Concrete C25/30", "unit": "m3", "quantity": 6.0,
             "total_quantity": 6.3, "waste_factor": 0.05, "category": "external_walls",
             "source_elements": [1]},
            {"description": "Concrete C25/30", "unit": "m3", "quantity": 4.0,
             "total_quantity": 4.2, "waste_factor": 0.05, "category": "external_walls",
             "source_elements": [2]},
        ]
        result = mapper._aggregate_materials(materials)

        assert len(result) == 1
        assert result[0]["quantity"] == 10.0
        assert result[0]["total_quantity"] == 10.5
        assert set(result[0]["source_elements"]) == {1, 2}

    def test_different_units_not_aggregated(self, mapper):
        """Same description but different units stay separate."""
        materials = [
            {"description": "Steel", "unit": "kg", "quantity": 100, "total_quantity": 103,
             "waste_factor": 0.03, "category": "frame", "source_elements": [1]},
            {"description": "Steel", "unit": "m", "quantity": 50, "total_quantity": 51.5,
             "waste_factor": 0.03, "category": "frame", "source_elements": [2]},
        ]
        result = mapper._aggregate_materials(materials)
        assert len(result) == 2

    def test_sorted_by_category_then_description(self, mapper):
        """Result is sorted by (category, description)."""
        materials = [
            {"description": "Zzz Paint", "unit": "m2", "quantity": 10, "total_quantity": 11,
             "waste_factor": 0.1, "category": "a_walls", "source_elements": [1]},
            {"description": "Aaa Concrete", "unit": "m3", "quantity": 5, "total_quantity": 5.25,
             "waste_factor": 0.05, "category": "a_walls", "source_elements": [2]},
        ]
        result = mapper._aggregate_materials(materials)
        assert result[0]["description"] == "Aaa Concrete"
        assert result[1]["description"] == "Zzz Paint"


# ---- Execute Tests ----

class TestMapperExecute:
    @pytest.mark.asyncio
    async def test_empty_elements_no_crash(self, mapper):
        """No elements -> no crash, early return."""
        state = {
            "parsed_elements": [],
            "calculated_quantities": [],
            "processing_log": [],
        }
        result = await mapper.execute(state)
        assert result.get("material_list") is None or result.get("material_list") == []

    @pytest.mark.asyncio
    async def test_full_mapping_with_mocked_ai(self):
        """End-to-end: element + quantities -> materials (AI mocked)."""
        mock_llm = MagicMock()
        mock_llm.ask_json = AsyncMock(return_value={
            "elements": [
                {
                    "element_id": 1,
                    "materials": [
                        {
                            "name": "Concrete C25/30",
                            "unit": "m3",
                            "source": "Column volume",
                            "multiplier": 1.0,
                            "waste_key": "concrete.standard",
                        },
                        {
                            "name": "Reinforcement steel",
                            "unit": "kg",
                            "source": "Column volume",
                            "multiplier": 150.0,
                            "waste_key": "reinforcement_steel.standard",
                        },
                        {
                            "name": "Formwork",
                            "unit": "m2",
                            "source": "Column surface area (for formwork/plaster)",
                            "multiplier": 1.0,
                            "waste_key": "formwork.standard",
                        },
                    ],
                }
            ]
        })

        mapper = MaterialMapperAgent(llm_service=mock_llm)
        state = {
            "parsed_elements": [
                make_element(1, "IfcColumn", category="frame"),
            ],
            "calculated_quantities": [
                make_calc_qty(1, [
                    {"description": "Column volume", "quantity": 0.27, "unit": "m3"},
                    {"description": "Column surface area (for formwork/plaster)", "quantity": 3.6, "unit": "m2"},
                    {"description": "Column count", "quantity": 1, "unit": "nr"},
                ]),
            ],
            "processing_log": [],
            "warnings": [],
        }
        result = await mapper.execute(state)
        materials = result["material_list"]
        assert len(materials) == 3

        descriptions = [m["description"] for m in materials]
        assert "Concrete C25/30" in descriptions
        assert "Reinforcement steel" in descriptions
        assert "Formwork" in descriptions

    @pytest.mark.asyncio
    async def test_ai_failure_continues(self):
        """If AI call fails for one batch, other batches still processed."""
        call_count = 0

        async def mock_ask_json(system_prompt, user_message, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("API error")
            return {
                "elements": [
                    {
                        "element_id": 2,
                        "materials": [
                            {
                                "name": "Door unit",
                                "unit": "nr",
                                "source": "Door count",
                                "multiplier": 1.0,
                                "waste_value": 0.0,
                            }
                        ],
                    }
                ]
            }

        mock_llm = MagicMock()
        mock_llm.ask_json = AsyncMock(side_effect=mock_ask_json)

        mapper = MaterialMapperAgent(llm_service=mock_llm)
        state = {
            "parsed_elements": [
                make_element(1, "IfcColumn", category="frame"),
                make_element(2, "IfcDoor", category="doors"),
            ],
            "calculated_quantities": [
                make_calc_qty(1, [{"description": "Column volume", "quantity": 0.27}]),
                make_calc_qty(2, [{"description": "Door count", "quantity": 1}]),
            ],
            "processing_log": [],
            "warnings": [],
        }
        result = await mapper.execute(state)

        # Door materials should still be mapped despite column batch failure
        assert len(result["material_list"]) == 1
        assert result["material_list"][0]["description"] == "Door unit"
        assert any("failed" in w.lower() for w in result["warnings"])
