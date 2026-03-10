"""
End-to-end pipeline test - runs the full pipeline from IFC file to BOQ output
and validates the final results against expected values.

Coach Simple explains:
    "This is the big test. We take our sample house, run the ENTIRE pipeline
    from start to finish, and check if the final shopping list makes sense.
    It's like test-driving a car after assembling all the parts."
"""

import tempfile
import pytest
from pathlib import Path

from src.agents.orchestrator import Orchestrator
from src.models.project import ProcessingStatus


SAMPLE_IFC = Path("tests/fixtures/simple_house.ifc")


@pytest.fixture
def orchestrator():
    return Orchestrator()


@pytest.mark.skipif(not SAMPLE_IFC.exists(), reason="Sample IFC file not found")
class TestFullPipeline:
    """End-to-end tests using the sample house IFC file."""

    @pytest.mark.asyncio
    async def test_pipeline_completes_successfully(self, orchestrator):
        """The full pipeline should complete without errors."""
        state = await orchestrator.run(str(SAMPLE_IFC))
        assert state["status"] == ProcessingStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_elements_parsed(self, orchestrator):
        """Parser should find all 56 elements in the sample house."""
        state = await orchestrator.run(str(SAMPLE_IFC))
        assert len(state["parsed_elements"]) == 56

    @pytest.mark.asyncio
    async def test_all_elements_classified(self, orchestrator):
        """Every element should have a category after classification."""
        state = await orchestrator.run(str(SAMPLE_IFC))
        for elem in state["parsed_elements"]:
            assert elem.get("category") is not None, (
                f"Element {elem['ifc_id']} ({elem['name']}) has no category"
            )

    @pytest.mark.asyncio
    async def test_materials_generated(self, orchestrator):
        """Pipeline should produce a non-empty material list."""
        state = await orchestrator.run(str(SAMPLE_IFC))
        materials = state["material_list"]
        assert len(materials) > 0

        # Should have concrete
        concrete = [m for m in materials if "concrete" in m["description"].lower()]
        assert len(concrete) > 0, "No concrete materials found"

        # Should have steel
        steel = [m for m in materials if "reinforcement" in m["description"].lower()]
        assert len(steel) > 0, "No reinforcement steel found"

    @pytest.mark.asyncio
    async def test_concrete_quantity_reasonable(self, orchestrator):
        """Total concrete should be reasonable for a 2-story house."""
        state = await orchestrator.run(str(SAMPLE_IFC))
        materials = state["material_list"]

        total_concrete = sum(
            m["total_quantity"]
            for m in materials
            if "concrete" in m["description"].lower() and m["unit"] == "m3"
        )

        # A 2-story house (12x10m) should have ~50-200 m3 of concrete
        assert 30 < total_concrete < 300, (
            f"Total concrete {total_concrete:.1f} m3 seems unreasonable"
        )

    @pytest.mark.asyncio
    async def test_steel_quantity_reasonable(self, orchestrator):
        """Total steel should be reasonable for the concrete volume."""
        state = await orchestrator.run(str(SAMPLE_IFC))
        materials = state["material_list"]

        total_concrete = sum(
            m["total_quantity"]
            for m in materials
            if "concrete" in m["description"].lower() and m["unit"] == "m3"
        )
        total_steel = sum(
            m["total_quantity"]
            for m in materials
            if "reinforcement" in m["description"].lower() and m["unit"] == "kg"
        )

        if total_concrete > 0:
            ratio = total_steel / total_concrete
            # 50-200 kg/m3 is the expected range
            assert 40 < ratio < 250, (
                f"Steel ratio {ratio:.0f} kg/m3 seems unreasonable"
            )

    @pytest.mark.asyncio
    async def test_boq_data_structure(self, orchestrator):
        """BOQ data should have proper structure with sections and items."""
        state = await orchestrator.run(str(SAMPLE_IFC))
        boq = state["boq_data"]

        assert boq is not None
        assert boq["total_sections"] > 0
        assert boq["total_line_items"] > 0
        assert len(boq["sections"]) > 0

        for section in boq["sections"]:
            assert "section_no" in section
            assert "title" in section
            assert len(section["items"]) > 0
            for item in section["items"]:
                assert "item_no" in item
                assert "description" in item
                assert "unit" in item
                assert "quantity" in item
                assert item["quantity"] >= 0

    @pytest.mark.asyncio
    async def test_validation_passes(self, orchestrator):
        """Validation should pass for the sample house."""
        state = await orchestrator.run(str(SAMPLE_IFC))
        vr = state["validation_report"]

        assert vr is not None
        assert vr["status"] == "PASS"
        # At least 6 of 8 checks should pass
        assert vr["passed"] >= 6

    @pytest.mark.asyncio
    async def test_no_errors(self, orchestrator):
        """Pipeline should complete without errors."""
        state = await orchestrator.run(str(SAMPLE_IFC))
        assert len(state["errors"]) == 0

    @pytest.mark.asyncio
    async def test_reports_exported(self, orchestrator):
        """All 3 report formats should be generated."""
        state = await orchestrator.run(str(SAMPLE_IFC))
        paths = state["boq_file_paths"]

        assert "xlsx" in paths
        assert "csv" in paths
        assert "json" in paths

        # Files should exist on disk
        for fmt, path in paths.items():
            assert Path(path).exists(), f"{fmt} report not found at {path}"

    @pytest.mark.asyncio
    async def test_building_info_extracted(self, orchestrator):
        """Building info should be extracted from IFC."""
        state = await orchestrator.run(str(SAMPLE_IFC))
        bi = state["building_info"]
        assert bi is not None
        assert len(bi.get("storeys", [])) > 0


class TestPipelineEdgeCases:
    """Test pipeline behavior with edge cases."""

    @pytest.mark.asyncio
    async def test_nonexistent_file(self, orchestrator):
        """Pipeline should handle missing files gracefully."""
        state = await orchestrator.run("nonexistent_file.ifc")
        assert state["status"] == ProcessingStatus.FAILED
        assert len(state["errors"]) > 0

    @pytest.mark.asyncio
    async def test_processing_log_populated(self, orchestrator):
        """Processing log should record steps."""
        if not SAMPLE_IFC.exists():
            pytest.skip("Sample IFC file not found")

        state = await orchestrator.run(str(SAMPLE_IFC))
        log = state["processing_log"]
        assert len(log) > 0
        # Should mention various stages
        log_text = " ".join(log)
        assert "Parser" in log_text or "parser" in log_text
