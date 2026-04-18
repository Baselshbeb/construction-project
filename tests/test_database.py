"""
Tests for the Database service — verifies project CRUD operations,
corrections, and learned overrides using a temporary SQLite database.
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.services.database import Database


@pytest.fixture
def db_path():
    """Create a temporary database file path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def db(db_path):
    """Create and initialize a Database instance with a temp file."""
    database = Database(db_path=db_path)
    asyncio.run(database.initialize())
    return database


class TestDatabaseInitialization:
    def test_initialize_creates_tables(self, db_path):
        """initialize() creates the database file and tables without error."""
        database = Database(db_path=db_path)
        asyncio.run(database.initialize())
        assert Path(db_path).exists()

    def test_initialize_idempotent(self, db):
        """Calling initialize() twice does not raise an error."""
        asyncio.run(db.initialize())


class TestProjectCRUD:
    def test_create_and_get_project(self, db):
        """create_project + get_project round-trip preserves all fields."""
        created = asyncio.run(
            db.create_project("proj-1", "building.ifc", "/uploads/building.ifc", "en")
        )
        assert created["id"] == "proj-1"
        assert created["filename"] == "building.ifc"
        assert created["status"] == "uploaded"
        assert created["language"] == "en"

        fetched = asyncio.run(db.get_project("proj-1"))
        assert fetched is not None
        assert fetched["id"] == "proj-1"
        assert fetched["filename"] == "building.ifc"
        assert fetched["upload_path"] == "/uploads/building.ifc"

    def test_get_nonexistent_project_returns_none(self, db):
        """get_project returns None for a project that does not exist."""
        result = asyncio.run(db.get_project("nonexistent"))
        assert result is None

    def test_update_project_with_json_result(self, db):
        """update_project serializes and stores a JSON result correctly."""
        asyncio.run(
            db.create_project("proj-2", "house.ifc", "/uploads/house.ifc", "tr")
        )
        result_data = {
            "element_count": 50,
            "materials": [{"name": "Concrete", "quantity": 10.5}],
        }
        asyncio.run(db.update_project("proj-2", status="completed", result=result_data))

        fetched = asyncio.run(db.get_project("proj-2"))
        assert fetched["status"] == "completed"
        assert fetched["result"]["element_count"] == 50
        assert fetched["result"]["materials"][0]["name"] == "Concrete"

    def test_list_projects_returns_correct_count(self, db):
        """list_projects returns all created projects."""
        asyncio.run(db.create_project("p1", "a.ifc", "/a.ifc", "en"))
        asyncio.run(db.create_project("p2", "b.ifc", "/b.ifc", "en"))
        asyncio.run(db.create_project("p3", "c.ifc", "/c.ifc", "en"))

        projects = asyncio.run(db.list_projects())
        assert len(projects) == 3

    def test_delete_old_projects_removes_old_entries(self, db):
        """delete_old_projects removes entries older than max_age_days."""
        # Create a project with a manually set old creation date
        asyncio.run(db.create_project("old-1", "old.ifc", "/old.ifc", "en"))
        asyncio.run(db.create_project("new-1", "new.ifc", "/new.ifc", "en"))

        # Manually backdate the old project
        import aiosqlite

        async def backdate():
            old_date = (datetime.utcnow() - timedelta(days=60)).isoformat()
            async with aiosqlite.connect(db._db_path) as conn:
                await conn.execute(
                    "UPDATE projects SET created_at = ? WHERE id = ?",
                    (old_date, "old-1"),
                )
                await conn.commit()

        asyncio.run(backdate())

        deleted_count = asyncio.run(db.delete_old_projects(max_age_days=30))
        assert deleted_count == 1

        remaining = asyncio.run(db.list_projects())
        assert len(remaining) == 1
        assert remaining[0]["id"] == "new-1"


class TestCorrections:
    def test_save_and_get_corrections(self, db):
        """save_correction + get_corrections_for_project round-trip."""
        asyncio.run(db.create_project("proj-c", "test.ifc", "/test.ifc", "en"))

        correction = {
            "id": "corr-1",
            "project_id": "proj-c",
            "item_no": "1.1",
            "field_name": "quantity",
            "old_value": "10.0",
            "new_value": "12.5",
            "element_type": "IfcWall",
            "category": "Concrete",
            "created_at": datetime.utcnow().isoformat(),
        }
        asyncio.run(db.save_correction(correction))

        corrections = asyncio.run(db.get_corrections_for_project("proj-c"))
        assert len(corrections) == 1
        assert corrections[0]["item_no"] == "1.1"
        assert corrections[0]["new_value"] == "12.5"

    def test_get_corrections_empty_project(self, db):
        """get_corrections_for_project returns empty list for project with no corrections."""
        corrections = asyncio.run(db.get_corrections_for_project("no-such-project"))
        assert corrections == []


class TestLearnedOverrides:
    def test_upsert_learned_override_insert_then_update(self, db):
        """upsert_learned_override inserts on first call, updates on second."""
        # First insert
        asyncio.run(db.upsert_learned_override(
            element_type="IfcWall",
            category="Concrete",
            field_name="quantity",
            pattern="quantity",
            override_value="12.0",
            confidence=0.6,
        ))

        overrides = asyncio.run(db.get_learned_overrides("IfcWall", "Concrete"))
        assert len(overrides) == 1
        assert overrides[0]["override_value"] == "12.0"
        assert overrides[0]["usage_count"] == 1

        # Second upsert (same key) — should update
        asyncio.run(db.upsert_learned_override(
            element_type="IfcWall",
            category="Concrete",
            field_name="quantity",
            pattern="quantity",
            override_value="13.0",
            confidence=0.7,
        ))

        overrides = asyncio.run(db.get_learned_overrides("IfcWall", "Concrete"))
        assert len(overrides) == 1
        assert overrides[0]["override_value"] == "13.0"
        assert overrides[0]["usage_count"] == 2
        assert overrides[0]["confidence"] == 0.7

    def test_get_learned_overrides_filters_by_type(self, db):
        """get_learned_overrides filters by element_type and category."""
        asyncio.run(db.upsert_learned_override(
            "IfcWall", "Concrete", "quantity", "qty", "10", 0.6,
        ))
        asyncio.run(db.upsert_learned_override(
            "IfcSlab", "Concrete", "quantity", "qty", "20", 0.6,
        ))

        wall_overrides = asyncio.run(db.get_learned_overrides("IfcWall", "Concrete"))
        assert len(wall_overrides) == 1
        assert wall_overrides[0]["override_value"] == "10"

        slab_overrides = asyncio.run(db.get_learned_overrides("IfcSlab", "Concrete"))
        assert len(slab_overrides) == 1
        assert slab_overrides[0]["override_value"] == "20"
