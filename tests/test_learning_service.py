"""
Tests for the LearningService — verifies correction recording,
override computation, and confidence boosting using a temporary database.
"""

import asyncio
import os
import tempfile

import pytest

from src.services.database import Database
from src.services.learning_service import LearningService


@pytest.fixture
def db_path():
    """Create a temporary database file path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def db(db_path):
    """Create and initialize a Database instance."""
    database = Database(db_path=db_path)
    asyncio.run(database.initialize())
    return database


@pytest.fixture
def learning_svc(db):
    """Create a LearningService instance."""
    return LearningService(db)


class TestRecordCorrection:
    def test_record_correction_stores_data(self, learning_svc, db):
        """record_correction stores the correction in the database."""
        asyncio.run(db.create_project("proj-1", "test.ifc", "/test.ifc", "en"))
        asyncio.run(learning_svc.record_correction(
            project_id="proj-1",
            item_no="1.1",
            field_name="quantity",
            old_value="10.0",
            new_value="12.0",
            element_type="IfcWall",
            category="Concrete",
        ))

        corrections = asyncio.run(db.get_corrections_for_project("proj-1"))
        assert len(corrections) == 1
        assert corrections[0]["item_no"] == "1.1"
        assert corrections[0]["old_value"] == "10.0"
        assert corrections[0]["new_value"] == "12.0"

    def test_record_correction_creates_learned_override(self, learning_svc, db):
        """record_correction also creates a learned override entry."""
        asyncio.run(db.create_project("proj-2", "test.ifc", "/test.ifc", "en"))
        asyncio.run(learning_svc.record_correction(
            project_id="proj-2",
            item_no="2.1",
            field_name="quantity",
            old_value="5.0",
            new_value="6.0",
            element_type="IfcSlab",
            category="Concrete",
        ))

        overrides = asyncio.run(db.get_learned_overrides("IfcSlab", "Concrete"))
        assert len(overrides) == 1
        assert overrides[0]["override_value"] == "6.0"


class TestGetOverridesForElement:
    def test_returns_empty_when_no_overrides(self, learning_svc):
        """get_overrides_for_element returns empty list when no overrides exist."""
        overrides = asyncio.run(
            learning_svc.get_overrides_for_element("IfcBeam", "Steel")
        )
        assert overrides == []

    def test_returns_empty_when_below_threshold(self, learning_svc, db):
        """Overrides with usage_count < 3 are not returned."""
        asyncio.run(db.create_project("proj-3", "test.ifc", "/test.ifc", "en"))
        # Record only 1 correction (below the 3-correction threshold)
        asyncio.run(learning_svc.record_correction(
            project_id="proj-3",
            item_no="1.1",
            field_name="quantity",
            old_value="10",
            new_value="12",
            element_type="IfcColumn",
            category="Concrete",
        ))

        overrides = asyncio.run(
            learning_svc.get_overrides_for_element("IfcColumn", "Concrete")
        )
        # Should be empty because usage_count is only 1 (threshold is 3)
        assert overrides == []

    def test_returns_override_after_three_corrections(self, learning_svc, db):
        """After 3+ consistent corrections, the override is returned."""
        asyncio.run(db.create_project("proj-4", "test.ifc", "/test.ifc", "en"))

        # Record 3 corrections for the same element type/category/field
        for i in range(3):
            asyncio.run(learning_svc.record_correction(
                project_id="proj-4",
                item_no=f"1.{i}",
                field_name="quantity",
                old_value="10",
                new_value="12",
                element_type="IfcWall",
                category="Plaster",
            ))

        overrides = asyncio.run(
            learning_svc.get_overrides_for_element("IfcWall", "Plaster")
        )
        assert len(overrides) == 1
        assert overrides[0]["override_value"] == "12"
        assert overrides[0]["usage_count"] >= 3
        assert overrides[0]["confidence"] >= 0.6


class TestComputeOverrideConfidence:
    def test_single_correction_confidence(self):
        """A single correction with perfect consistency gives 0.6."""
        result = LearningService.compute_override_confidence(1, 1.0)
        assert result == pytest.approx(0.6)

    def test_three_corrections_confidence(self):
        """Three corrections with perfect consistency gives 0.8."""
        result = LearningService.compute_override_confidence(3, 1.0)
        assert result == pytest.approx(0.8)

    def test_confidence_capped_at_095(self):
        """Confidence is capped at 0.95 regardless of usage count."""
        result = LearningService.compute_override_confidence(100, 1.0)
        assert result == 0.95

    def test_low_consistency_reduces_confidence(self):
        """Low consistency ratio reduces the confidence score."""
        high_consistency = LearningService.compute_override_confidence(3, 1.0)
        low_consistency = LearningService.compute_override_confidence(3, 0.5)
        assert low_consistency < high_consistency

    def test_zero_consistency(self):
        """Zero consistency gives base confidence of 0.5."""
        result = LearningService.compute_override_confidence(5, 0.0)
        assert result == pytest.approx(0.5)

    def test_formula_is_correct(self):
        """Verify the formula: min(0.5 + (usage_count * 0.1) * consistency, 0.95)."""
        usage = 4
        consistency = 0.75
        expected = min(0.5 + (usage * 0.1) * consistency, 0.95)
        result = LearningService.compute_override_confidence(usage, consistency)
        assert result == pytest.approx(expected)


class TestApproveProjectCorrections:
    def test_approve_boosts_confidence(self, learning_svc, db):
        """approve_project_corrections boosts override confidence by 0.1."""
        asyncio.run(db.create_project("proj-5", "test.ifc", "/test.ifc", "en"))

        # Record a correction to create an override
        asyncio.run(learning_svc.record_correction(
            project_id="proj-5",
            item_no="1.1",
            field_name="quantity",
            old_value="10",
            new_value="12",
            element_type="IfcWall",
            category="Concrete",
        ))

        # Get initial confidence
        overrides_before = asyncio.run(db.get_learned_overrides("IfcWall", "Concrete"))
        initial_confidence = overrides_before[0]["confidence"]

        # Approve the project
        asyncio.run(learning_svc.approve_project_corrections("proj-5"))

        # Confidence should have increased
        overrides_after = asyncio.run(db.get_learned_overrides("IfcWall", "Concrete"))
        boosted_confidence = overrides_after[0]["confidence"]

        assert boosted_confidence == pytest.approx(
            min(initial_confidence + 0.1, 0.95)
        )

    def test_approve_empty_project_no_error(self, learning_svc):
        """Approving a project with no corrections does not raise an error."""
        asyncio.run(learning_svc.approve_project_corrections("nonexistent"))
