"""
Tests for the CalculatorAgent - verifies quantity calculations against
manual hand calculations.

Coach Simple explains:
    "We're checking that the calculator's math is correct. If a wall
    is 10m long and 3m high, the area should be 30 m2. If the slab
    is 12m x 10m x 0.2m thick, the volume should be 24 m3."
"""

import math
import pytest

from src.agents.calculator import CalculatorAgent


@pytest.fixture
def calculator():
    return CalculatorAgent()


def make_element(ifc_type, quantities=None, properties=None, is_external=False, name="Test"):
    """Helper to create a minimal element dict."""
    return {
        "ifc_id": 1,
        "ifc_type": ifc_type,
        "name": name,
        "storey": "Ground Floor",
        "quantities": quantities or {},
        "properties": properties or {},
        "is_external": is_external,
        "category": None,
    }


def get_qty(quantities, description):
    """Find a quantity by description from the list."""
    for q in quantities:
        if q["description"] == description:
            return q["quantity"]
    return None


# ---- Wall Tests ----

class TestWallCalculations:
    def test_wall_with_all_qto_values(self, calculator):
        """Wall with full IFC quantity set - uses actual values, no fallbacks."""
        elem = make_element("IfcWall", {
            "Length": 10.0,
            "Height": 3.0,
            "Width": 0.2,
            "GrossArea": 30.0,
            "NetArea": 25.0,
            "GrossVolume": 6.0,
            "NetVolume": 5.0,
        }, is_external=False)

        result = calculator._calculate_for_element(elem)

        assert get_qty(result, "Gross wall area (one side)") == 30.0
        assert get_qty(result, "Net wall area (minus openings, one side)") == 25.0
        assert get_qty(result, "Wall volume") == 5.0
        assert get_qty(result, "Net wall area (both sides, for plaster/paint)") == 50.0
        assert get_qty(result, "Wall length (for skirting/coving)") == 10.0

    def test_wall_area_fallback(self, calculator):
        """Wall without GrossArea - falls back to Length * Height."""
        elem = make_element("IfcWall", {
            "Length": 8.0,
            "Height": 3.5,
            "Width": 0.25,
        })

        result = calculator._calculate_for_element(elem)
        # Gross area = 8 * 3.5 = 28.0
        assert get_qty(result, "Gross wall area (one side)") == 28.0

    def test_wall_net_area_fallback(self, calculator):
        """Wall without NetArea - deducts 15% from gross area."""
        elem = make_element("IfcWall", {
            "Length": 10.0,
            "Height": 3.0,
            "Width": 0.2,
        })

        result = calculator._calculate_for_element(elem)
        # Gross = 30, Net = 30 * 0.85 = 25.5
        assert get_qty(result, "Gross wall area (one side)") == 30.0
        assert get_qty(result, "Net wall area (minus openings, one side)") == 25.5

    def test_wall_volume_fallback(self, calculator):
        """Wall without volume - calculates from area * width."""
        elem = make_element("IfcWall", {
            "Length": 10.0,
            "Height": 3.0,
            "Width": 0.2,
        })

        result = calculator._calculate_for_element(elem)
        # gross_volume = 30 * 0.2 = 6.0, net_volume = 6.0 * 0.85 = 5.1
        assert get_qty(result, "Wall volume") == 5.1

    def test_external_wall_produces_two_face_areas(self, calculator):
        """External wall produces separate internal/external face areas."""
        elem = make_element("IfcWall", {
            "GrossArea": 30.0,
            "NetArea": 25.0,
        }, is_external=True)

        result = calculator._calculate_for_element(elem)

        # Should NOT have "both sides" quantity
        assert get_qty(result, "Net wall area (both sides, for plaster/paint)") is None
        # Should have separate face areas
        assert get_qty(result, "Internal face area (for plaster/paint)") == 25.0
        assert get_qty(result, "External face area (for ext. plaster/paint)") == 25.0

    def test_internal_wall_produces_both_sides(self, calculator):
        """Internal wall produces doubled area for both-sides plaster."""
        elem = make_element("IfcWall", {
            "GrossArea": 20.0,
            "NetArea": 17.0,
        }, is_external=False)

        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Net wall area (both sides, for plaster/paint)") == 34.0

    def test_wall_skirting_only_with_length(self, calculator):
        """Skirting quantity only appears when Length is provided."""
        # With length
        elem_with = make_element("IfcWall", {"Length": 5.0, "GrossArea": 15.0})
        result_with = calculator._calculate_for_element(elem_with)
        assert get_qty(result_with, "Wall length (for skirting/coving)") == 5.0

        # Without length
        elem_without = make_element("IfcWall", {"GrossArea": 15.0})
        result_without = calculator._calculate_for_element(elem_without)
        assert get_qty(result_without, "Wall length (for skirting/coving)") is None

    def test_wall_standard_case_same_as_wall(self, calculator):
        """IfcWallStandardCase uses the same calculator as IfcWall."""
        elem = make_element("IfcWallStandardCase", {
            "GrossArea": 20.0, "NetArea": 18.0
        })
        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Gross wall area (one side)") == 20.0


# ---- Slab Tests ----

class TestSlabCalculations:
    def test_slab_with_all_values(self, calculator):
        """Slab with full quantities from IFC."""
        elem = make_element("IfcSlab", {
            "Area": 120.0,
            "GrossVolume": 24.0,
            "Perimeter": 44.0,
            "Depth": 0.2,
        })

        result = calculator._calculate_for_element(elem)

        assert get_qty(result, "Slab area (top face)") == 120.0
        assert get_qty(result, "Slab area (bottom face / soffit)") == 120.0
        assert get_qty(result, "Slab volume") == 24.0
        assert get_qty(result, "Slab perimeter") == 44.0
        # Formwork = soffit(120) + edges(44*0.2=8.8) = 128.8
        assert get_qty(result, "Formwork area (soffit + edges)") == 128.8

    def test_slab_area_fallback(self, calculator):
        """Slab without Area - falls back to Length * Width."""
        elem = make_element("IfcSlab", {
            "Length": 12.0,
            "Width": 10.0,
            "Depth": 0.2,
        })

        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Slab area (top face)") == 120.0

    def test_slab_volume_fallback(self, calculator):
        """Slab without volume - calculates from area * depth."""
        elem = make_element("IfcSlab", {
            "Length": 12.0,
            "Width": 10.0,
            "Depth": 0.2,
        })

        result = calculator._calculate_for_element(elem)
        # Volume = 120 * 0.2 = 24.0
        assert get_qty(result, "Slab volume") == 24.0

    def test_slab_perimeter_fallback(self, calculator):
        """Slab without perimeter - calculates from 2*(L+W)."""
        elem = make_element("IfcSlab", {
            "Length": 12.0,
            "Width": 10.0,
            "Depth": 0.2,
        })

        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Slab perimeter") == 44.0

    def test_slab_formwork_calculation(self, calculator):
        """Formwork = soffit area + (perimeter * depth)."""
        elem = make_element("IfcSlab", {
            "Area": 100.0,
            "Perimeter": 40.0,
            "Depth": 0.25,
        })

        result = calculator._calculate_for_element(elem)
        # formwork = 100 + (40 * 0.25) = 110.0
        assert get_qty(result, "Formwork area (soffit + edges)") == 110.0

    def test_roof_delegates_to_slab(self, calculator):
        """IfcRoof produces identical output to IfcSlab."""
        qto = {"Area": 80.0, "GrossVolume": 16.0, "Perimeter": 36.0, "Depth": 0.2}
        slab_result = calculator._calculate_for_element(make_element("IfcSlab", qto))
        roof_result = calculator._calculate_for_element(make_element("IfcRoof", qto))

        assert len(slab_result) == len(roof_result)
        for s, r in zip(slab_result, roof_result):
            assert s["description"] == r["description"]
            assert s["quantity"] == r["quantity"]


# ---- Column Tests ----

class TestColumnCalculations:
    def test_column_with_surface_area(self, calculator):
        """Column with OuterSurfaceArea from IFC."""
        elem = make_element("IfcColumn", {
            "Length": 3.0,
            "CrossSectionArea": 0.09,
            "GrossVolume": 0.27,
            "OuterSurfaceArea": 3.6,
        })

        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Column volume") == 0.27
        assert get_qty(result, "Column surface area (for formwork/plaster)") == 3.6
        assert get_qty(result, "Column count") == 1

    def test_column_estimated_surface(self, calculator):
        """Column without OuterSurfaceArea - estimates from square cross-section."""
        elem = make_element("IfcColumn", {
            "Length": 3.0,
            "CrossSectionArea": 0.09,  # 0.3m x 0.3m
            "GrossVolume": 0.27,
        })

        result = calculator._calculate_for_element(elem)
        # side = sqrt(0.09) = 0.3, surface = 4 * 0.3 * 3.0 = 3.6
        assert get_qty(result, "Column surface area (estimated)") == 3.6
        assert get_qty(result, "Column surface area (for formwork/plaster)") is None

    def test_column_volume_fallback(self, calculator):
        """Column volume from CrossSectionArea * Length when no volume given."""
        elem = make_element("IfcColumn", {
            "Length": 3.5,
            "CrossSectionArea": 0.16,
        })

        result = calculator._calculate_for_element(elem)
        # volume = 0.16 * 3.5 = 0.56
        assert get_qty(result, "Column volume") == 0.56


# ---- Beam Tests ----

class TestBeamCalculations:
    def test_beam_with_surface(self, calculator):
        elem = make_element("IfcBeam", {
            "Length": 6.0,
            "GrossVolume": 0.36,
            "OuterSurfaceArea": 4.8,
        })

        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Beam volume") == 0.36
        assert get_qty(result, "Beam length") == 6.0
        assert get_qty(result, "Beam surface area (for formwork)") == 4.8

    def test_beam_without_surface(self, calculator):
        """Beam without OuterSurfaceArea - no surface area quantity."""
        elem = make_element("IfcBeam", {
            "Length": 5.0,
            "GrossVolume": 0.3,
        })

        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Beam surface area (for formwork)") is None
        assert len(result) == 2  # volume + length only


# ---- Door/Window Tests ----

class TestDoorWindowCalculations:
    def test_door_with_dimensions(self, calculator):
        elem = make_element("IfcDoor", {
            "Width": 0.9,
            "Height": 2.1,
        })

        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Door count") == 1
        # Area = 0.9 * 2.1 = 1.89
        assert get_qty(result, "Door opening area (for wall deduction)") == 1.89
        # Frame = 2*2.1 + 0.9 = 5.1
        assert get_qty(result, "Door frame perimeter") == 5.1

    def test_door_with_zero_dimensions(self, calculator):
        """Door with missing dimensions - frame perimeter is 0."""
        elem = make_element("IfcDoor", {})
        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Door frame perimeter") == 0

    def test_window_with_dimensions(self, calculator):
        elem = make_element("IfcWindow", {
            "Width": 1.2,
            "Height": 1.5,
        })

        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Window count") == 1
        # Area = 1.2 * 1.5 = 1.8
        assert get_qty(result, "Window opening area (for wall deduction)") == 1.8
        assert get_qty(result, "Window sill length") == 1.2

    def test_window_sill_zero_without_width(self, calculator):
        elem = make_element("IfcWindow", {"Height": 1.5})
        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Window sill length") == 0


# ---- Other Element Types ----

class TestOtherElements:
    def test_stair_with_volume_and_area(self, calculator):
        elem = make_element("IfcStair", {
            "GrossVolume": 2.5,
            "GrossArea": 8.0,
        })
        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Stair volume") == 2.5
        assert get_qty(result, "Stair area") == 8.0
        assert get_qty(result, "Stair count") == 1

    def test_stair_without_volume(self, calculator):
        """Stair without volume - only area and count."""
        elem = make_element("IfcStair", {"GrossArea": 6.0})
        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Stair volume") is None
        assert get_qty(result, "Stair area") == 6.0
        assert get_qty(result, "Stair count") == 1

    def test_foundation(self, calculator):
        elem = make_element("IfcFooting", {
            "GrossVolume": 5.0,
            "GrossArea": 12.0,
        })
        result = calculator._calculate_for_element(elem)
        assert get_qty(result, "Foundation volume") == 5.0
        assert get_qty(result, "Foundation area") == 12.0

    def test_generic_element(self, calculator):
        """Unknown element type uses generic calculator."""
        elem = make_element("IfcCurtainWall", {
            "TotalArea": 25.0,
            "NetVolume": 3.5,
            "Length": 10.0,
        })
        result = calculator._calculate_for_element(elem)
        # Should map area/volume/length to correct units
        descs = {q["description"]: q for q in result}
        assert descs["TotalArea"]["unit"] == "m2"
        assert descs["NetVolume"]["unit"] == "m3"
        assert descs["Length"]["unit"] == "m"

    def test_generic_skips_zero_and_negative(self, calculator):
        """Generic calculator skips zero and negative values."""
        elem = make_element("IfcCurtainWall", {
            "GoodArea": 10.0,
            "ZeroArea": 0.0,
            "BadArea": -5.0,
        })
        result = calculator._calculate_for_element(elem)
        assert len(result) == 1
        assert result[0]["description"] == "GoodArea"


# ---- Agent Execute Tests ----

class TestCalculatorExecute:
    @pytest.mark.asyncio
    async def test_empty_elements_no_crash(self, calculator):
        """No elements -> no crash, returns state unchanged."""
        state = {"parsed_elements": [], "processing_log": []}
        result = await calculator.execute(state)
        assert "calculated_quantities" not in result

    @pytest.mark.asyncio
    async def test_execute_produces_quantities(self, calculator):
        """Execute processes all elements and produces calculated_quantities."""
        state = {
            "parsed_elements": [
                make_element("IfcWall", {"GrossArea": 30.0, "NetArea": 25.0}),
                make_element("IfcSlab", {"Area": 100.0, "GrossVolume": 20.0, "Depth": 0.2}),
            ],
            "processing_log": [],
        }
        result = await calculator.execute(state)
        assert len(result["calculated_quantities"]) == 2
        # Each should have quantities list
        assert len(result["calculated_quantities"][0]["quantities"]) > 0
        assert len(result["calculated_quantities"][1]["quantities"]) > 0
