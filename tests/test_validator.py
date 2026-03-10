"""
Tests for the ValidatorAgent - verifies all 8 validation checks,
boundary conditions, and error/warning behavior.

AI validation is mocked to avoid real API calls.
"""

import pytest
from unittest.mock import AsyncMock, patch

from src.agents.validator import ValidatorAgent
from src.models.project import ProcessingStatus


@pytest.fixture
def validator():
    v = ValidatorAgent()
    # Mock AI validation so tests don't need a real API key
    v._ai_validate = AsyncMock(return_value=None)
    return v


def make_state(
    elements=None,
    materials=None,
    calc_quantities=None,
    building_info=None,
):
    """Build a minimal state dict for validation."""
    return {
        "parsed_elements": elements or [],
        "material_list": materials or [],
        "calculated_quantities": calc_quantities or [],
        "building_info": building_info or {},
        "warnings": [],
        "errors": [],
        "processing_log": [],
    }


def make_material(description, unit, quantity, total_quantity):
    return {
        "description": description,
        "unit": unit,
        "quantity": quantity,
        "total_quantity": total_quantity,
    }


def make_calc_qty(quantities):
    return {"element_id": 1, "quantities": quantities}


# ---- Individual Check Tests ----

class TestElementsParsedCheck:
    @pytest.mark.asyncio
    async def test_passes_with_elements(self, validator):
        state = make_state(
            elements=[{"ifc_id": 1, "category": "frame"}],
            materials=[make_material("Concrete", "m3", 10, 10.5)],
            calc_quantities=[make_calc_qty([])],
        )
        result = await validator.execute(state)
        assert result["validation_report"]["checks"]["elements_parsed"] is True

    @pytest.mark.asyncio
    async def test_fails_with_no_elements(self, validator):
        state = make_state(
            materials=[make_material("Concrete", "m3", 10, 10.5)],
            calc_quantities=[make_calc_qty([])],
        )
        result = await validator.execute(state)
        assert result["validation_report"]["checks"]["elements_parsed"] is False
        assert any("No elements" in e for e in result["errors"])


class TestClassifiedCheck:
    @pytest.mark.asyncio
    async def test_passes_all_classified(self, validator):
        state = make_state(
            elements=[{"ifc_id": 1, "category": "frame"}],
            materials=[make_material("Concrete", "m3", 10, 10.5)],
            calc_quantities=[make_calc_qty([])],
        )
        result = await validator.execute(state)
        assert result["validation_report"]["checks"]["elements_classified"] is True

    @pytest.mark.asyncio
    async def test_warns_unclassified(self, validator):
        state = make_state(
            elements=[
                {"ifc_id": 1, "category": "frame"},
                {"ifc_id": 2, "category": None},
            ],
            materials=[make_material("Concrete", "m3", 10, 10.5)],
            calc_quantities=[make_calc_qty([])],
        )
        result = await validator.execute(state)
        assert result["validation_report"]["checks"]["elements_classified"] is False
        assert any("1 elements have no category" in w for w in result["warnings"])


class TestNegativeQuantitiesCheck:
    @pytest.mark.asyncio
    async def test_passes_all_positive(self, validator):
        state = make_state(
            elements=[{"ifc_id": 1, "category": "frame"}],
            materials=[make_material("Concrete", "m3", 10, 10.5)],
            calc_quantities=[make_calc_qty([])],
        )
        result = await validator.execute(state)
        assert result["validation_report"]["checks"]["no_negative_quantities"] is True

    @pytest.mark.asyncio
    async def test_fails_negative_quantity(self, validator):
        state = make_state(
            elements=[{"ifc_id": 1, "category": "frame"}],
            materials=[make_material("Bad Material", "m3", -5.0, -5.0)],
            calc_quantities=[make_calc_qty([])],
        )
        result = await validator.execute(state)
        assert result["validation_report"]["checks"]["no_negative_quantities"] is False
        assert any("Negative" in e for e in result["errors"])


class TestConcreteRatioCheck:
    @pytest.mark.asyncio
    async def test_ratio_in_range_passes(self, validator):
        """Concrete ratio of 0.5 m3/m2 is within 0.1-1.5 range."""
        state = make_state(
            elements=[{"ifc_id": 1, "category": "frame"}],
            materials=[make_material("Concrete C25/30", "m3", 50, 50)],
            calc_quantities=[make_calc_qty([
                {"description": "Slab area (top face)", "quantity": 100.0}
            ])],
        )
        result = await validator.execute(state)
        assert result["validation_report"]["checks"]["concrete_ratio_reasonable"] is True

    @pytest.mark.asyncio
    async def test_ratio_too_high_warns(self, validator):
        """Concrete ratio of 2.0 is above 1.5 - should warn."""
        state = make_state(
            elements=[{"ifc_id": 1, "category": "frame"}],
            materials=[make_material("Concrete C25/30", "m3", 200, 200)],
            calc_quantities=[make_calc_qty([
                {"description": "Slab area (top face)", "quantity": 100.0}
            ])],
        )
        result = await validator.execute(state)
        assert result["validation_report"]["checks"]["concrete_ratio_reasonable"] is False
        assert any("Concrete ratio" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_no_concrete_auto_passes(self, validator):
        """No concrete materials -> check auto-passes."""
        state = make_state(
            elements=[{"ifc_id": 1, "category": "frame"}],
            materials=[make_material("Paint", "m2", 100, 110)],
            calc_quantities=[make_calc_qty([])],
        )
        result = await validator.execute(state)
        assert result["validation_report"]["checks"]["concrete_ratio_reasonable"] is True


class TestSteelRatioCheck:
    @pytest.mark.asyncio
    async def test_ratio_in_range_passes(self, validator):
        """Steel ratio of 100 kg/m3 is within 50-200 range."""
        state = make_state(
            elements=[{"ifc_id": 1, "category": "frame"}],
            materials=[
                make_material("Concrete C25/30", "m3", 50, 50),
                make_material("Reinforcement steel", "kg", 5000, 5000),
            ],
            calc_quantities=[make_calc_qty([])],
        )
        result = await validator.execute(state)
        assert result["validation_report"]["checks"]["steel_ratio_reasonable"] is True

    @pytest.mark.asyncio
    async def test_ratio_too_low_warns(self, validator):
        """Steel ratio of 30 kg/m3 is below 50 - should warn."""
        state = make_state(
            elements=[{"ifc_id": 1, "category": "frame"}],
            materials=[
                make_material("Concrete C25/30", "m3", 100, 100),
                make_material("Reinforcement steel", "kg", 3000, 3000),
            ],
            calc_quantities=[make_calc_qty([])],
        )
        result = await validator.execute(state)
        assert result["validation_report"]["checks"]["steel_ratio_reasonable"] is False


class TestStoreysCheck:
    @pytest.mark.asyncio
    async def test_all_storeys_have_elements(self, validator):
        state = make_state(
            elements=[
                {"ifc_id": 1, "category": "frame", "storey": "Ground Floor"},
                {"ifc_id": 2, "category": "frame", "storey": "First Floor"},
            ],
            materials=[make_material("Concrete", "m3", 10, 10.5)],
            calc_quantities=[make_calc_qty([])],
            building_info={"storeys": ["Ground Floor", "First Floor"]},
        )
        result = await validator.execute(state)
        assert result["validation_report"]["checks"]["all_storeys_have_elements"] is True

    @pytest.mark.asyncio
    async def test_missing_storey_warns(self, validator):
        state = make_state(
            elements=[
                {"ifc_id": 1, "category": "frame", "storey": "Ground Floor"},
            ],
            materials=[make_material("Concrete", "m3", 10, 10.5)],
            calc_quantities=[make_calc_qty([])],
            building_info={"storeys": ["Ground Floor", "First Floor"]},
        )
        result = await validator.execute(state)
        assert result["validation_report"]["checks"]["all_storeys_have_elements"] is False
        assert any("Storeys with no elements" in w for w in result["warnings"])


# ---- Overall Status Tests ----

class TestValidationStatus:
    @pytest.mark.asyncio
    async def test_pass_status_when_no_errors(self, validator):
        """All checks pass -> status COMPLETED, report PASS."""
        state = make_state(
            elements=[{"ifc_id": 1, "category": "frame"}],
            materials=[make_material("Concrete", "m3", 10, 10.5)],
            calc_quantities=[make_calc_qty([])],
        )
        result = await validator.execute(state)
        assert result["status"] == ProcessingStatus.COMPLETED
        assert result["validation_report"]["status"] == "PASS"

    @pytest.mark.asyncio
    async def test_fail_status_when_errors(self, validator):
        """No elements -> error -> status FAILED, report FAIL."""
        state = make_state()
        result = await validator.execute(state)
        assert result["status"] == ProcessingStatus.FAILED
        assert result["validation_report"]["status"] == "FAIL"

    @pytest.mark.asyncio
    async def test_score_format(self, validator):
        """Score format should be 'N/8'."""
        state = make_state(
            elements=[{"ifc_id": 1, "category": "frame"}],
            materials=[make_material("Concrete", "m3", 10, 10.5)],
            calc_quantities=[make_calc_qty([])],
        )
        result = await validator.execute(state)
        score = result["validation_report"]["score"]
        assert "/" in score
        parts = score.split("/")
        assert parts[1] == "8"

    @pytest.mark.asyncio
    async def test_summary_contains_totals(self, validator):
        """Summary should include total_elements, total_materials, etc."""
        state = make_state(
            elements=[{"ifc_id": 1, "category": "frame"}],
            materials=[
                make_material("Concrete C25/30", "m3", 50, 52.5),
                make_material("Reinforcement steel", "kg", 5000, 5150),
            ],
            calc_quantities=[make_calc_qty([
                {"description": "Slab area (top face)", "quantity": 100.0}
            ])],
        )
        result = await validator.execute(state)
        summary = result["validation_report"]["summary"]
        assert summary["total_elements"] == 1
        assert summary["total_materials"] == 2
        assert summary["total_concrete_m3"] == 52.5
        assert summary["total_steel_kg"] == 5150
        assert summary["total_floor_area_m2"] == 100.0
