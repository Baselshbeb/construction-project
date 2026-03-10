"""
Tests for the MaterialMapperAgent - verifies material mapping, waste factors,
aggregation, and edge cases.

Coach Simple explains:
    "We test that a wall correctly maps to concrete, steel, formwork, plaster,
    and paint, with the right quantities and waste factors."
"""

import pytest

from src.agents.material_mapper import MaterialMapperAgent


@pytest.fixture
def mapper():
    return MaterialMapperAgent()


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


# ---- Rule Matching Tests ----

class TestRuleMatching:
    def test_single_variant_always_matches(self, mapper):
        """If only one variant exists, it's always used."""
        rules = {"standard": {"materials": [{"name": "Test"}]}}
        result = mapper._find_matching_rule(rules, True, [])
        assert result == {"materials": [{"name": "Test"}]}

    def test_external_wall_with_concrete_material(self, mapper):
        """External wall with concrete should match concrete_external variant."""
        type_rules = mapper.element_rules.get("IfcWall", {})
        result = mapper._find_matching_rule(type_rules, True, ["Concrete C25/30"])
        assert result is not None
        # Should have concrete-related materials
        mat_names = [m["name"] for m in result["materials"]]
        assert any("Concrete" in n for n in mat_names)

    def test_internal_wall_matches_brick(self, mapper):
        """Internal wall without concrete material matches brick variant."""
        type_rules = mapper.element_rules.get("IfcWall", {})
        result = mapper._find_matching_rule(type_rules, False, ["Brick"])
        assert result is not None
        mat_names = [m["name"] for m in result["materials"]]
        assert any("brick" in n.lower() or "Brick" in n for n in mat_names)

    def test_is_external_none_falls_to_fallback(self, mapper):
        """Element with is_external=None should fall to the first variant."""
        type_rules = mapper.element_rules.get("IfcWall", {})
        result = mapper._find_matching_rule(type_rules, None, [])
        assert result is not None  # Should return fallback, not None

    def test_no_rules_for_type(self, mapper):
        """Unknown element type returns empty list."""
        element = make_element(1, "IfcStair")
        result = mapper._map_element(element, [])
        assert result == []


# ---- Material Mapping Tests ----

class TestMaterialMapping:
    def test_slab_produces_5_materials(self, mapper):
        """Slab maps to: concrete, steel, formwork, screed, ceiling plaster."""
        element = make_element(1, "IfcSlab", category="upper_floors")
        quantities = [
            {"description": "Slab volume", "quantity": 24.0, "unit": "m3"},
            {"description": "Slab area (top face)", "quantity": 120.0, "unit": "m2"},
            {"description": "Slab area (bottom face / soffit)", "quantity": 120.0, "unit": "m2"},
            {"description": "Formwork area (soffit + edges)", "quantity": 128.8, "unit": "m2"},
        ]
        result = mapper._map_element(element, quantities)
        assert len(result) == 5

        names = [m["description"] for m in result]
        assert any("Concrete" in n for n in names)
        assert "Reinforcement steel" in names

    def test_slab_concrete_waste_5_percent(self, mapper):
        """Slab concrete has 5% waste factor."""
        element = make_element(1, "IfcSlab", category="upper_floors")
        quantities = [
            {"description": "Slab volume", "quantity": 10.0, "unit": "m3"},
            {"description": "Slab area (top face)", "quantity": 50.0, "unit": "m2"},
            {"description": "Slab area (bottom face / soffit)", "quantity": 50.0, "unit": "m2"},
            {"description": "Formwork area (soffit + edges)", "quantity": 55.0, "unit": "m2"},
        ]
        result = mapper._map_element(element, quantities)

        concrete = next(m for m in result if "Concrete" in m["description"])
        assert concrete["waste_factor"] == 0.05
        # total = 10 * 1.05 = 10.5
        assert concrete["total_quantity"] == 10.5

    def test_slab_steel_multiplier_100(self, mapper):
        """Slab reinforcement uses 100 kg/m3 multiplier."""
        element = make_element(1, "IfcSlab", category="upper_floors")
        quantities = [
            {"description": "Slab volume", "quantity": 10.0, "unit": "m3"},
            {"description": "Slab area (top face)", "quantity": 50.0, "unit": "m2"},
            {"description": "Slab area (bottom face / soffit)", "quantity": 50.0, "unit": "m2"},
            {"description": "Formwork area (soffit + edges)", "quantity": 55.0, "unit": "m2"},
        ]
        result = mapper._map_element(element, quantities)

        steel = next(m for m in result if "Reinforcement" in m["description"])
        # base = 10 * 100 = 1000 kg, waste 3%, total = 1030
        assert steel["quantity"] == 1000.0
        assert steel["total_quantity"] == 1030.0

    def test_door_zero_waste(self, mapper):
        """Door materials have 0% waste."""
        element = make_element(1, "IfcDoor", category="doors")
        quantities = [
            {"description": "Door count", "quantity": 1, "unit": "nr"},
            {"description": "Door opening area (for wall deduction)", "quantity": 1.89, "unit": "m2"},
            {"description": "Door frame perimeter", "quantity": 5.1, "unit": "m"},
        ]
        result = mapper._map_element(element, quantities)
        for m in result:
            assert m["waste_factor"] == 0
            assert m["quantity"] == m["total_quantity"]

    def test_window_sill_has_10_percent_waste(self, mapper):
        """Window sill uses tiles.standard = 10% waste."""
        element = make_element(1, "IfcWindow", category="windows")
        quantities = [
            {"description": "Window count", "quantity": 1, "unit": "nr"},
            {"description": "Window opening area (for wall deduction)", "quantity": 1.8, "unit": "m2"},
            {"description": "Window sill length", "quantity": 1.2, "unit": "m"},
        ]
        result = mapper._map_element(element, quantities)
        sill = next((m for m in result if "sill" in m["description"].lower()), None)
        if sill:
            assert sill["waste_factor"] == 0.10


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
        """No elements -> no crash."""
        state = {
            "parsed_elements": [],
            "calculated_quantities": [],
            "processing_log": [],
        }
        result = await mapper.execute(state)
        assert result.get("material_list") is None or result.get("material_list") == []

    @pytest.mark.asyncio
    async def test_full_mapping(self, mapper):
        """End-to-end: element + quantities -> materials."""
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
        }
        result = await mapper.execute(state)
        materials = result["material_list"]
        assert len(materials) > 0

        # Should have concrete, steel, formwork for column
        descriptions = [m["description"] for m in materials]
        assert any("Concrete" in d for d in descriptions)
        assert any("Reinforcement" in d or "steel" in d.lower() for d in descriptions)
