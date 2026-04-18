"""
SQLite-based project persistence for Metraj.

Replaces the in-memory dict in api/app.py with durable storage
using aiosqlite for async access.

Usage:
    from src.services.database import Database

    db = Database()
    await db.initialize()
    project = await db.create_project(project_id, filename, upload_path, language)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import aiosqlite

from src.utils.logger import get_logger

logger = get_logger("database")

# Database file lives at <project_root>/data/metraj.db
_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DB_PATH = _DB_DIR / "metraj.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    upload_path TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'uploaded',
    language    TEXT NOT NULL DEFAULT 'en',
    created_at  TEXT NOT NULL,
    result      TEXT,
    error       TEXT
);
"""

_CREATE_CORRECTIONS_SQL = """
CREATE TABLE IF NOT EXISTS corrections (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    item_no TEXT NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    element_type TEXT,
    category TEXT,
    created_at TEXT NOT NULL
);
"""

_CREATE_LEARNED_OVERRIDES_SQL = """
CREATE TABLE IF NOT EXISTS learned_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    element_type TEXT NOT NULL,
    category TEXT,
    field_name TEXT NOT NULL,
    pattern TEXT,
    override_value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    usage_count INTEGER DEFAULT 1,
    last_used TEXT,
    UNIQUE(element_type, category, field_name, pattern)
);
"""


def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    """Convert a database row to a plain dict, deserializing JSON fields."""
    data = dict(row)
    # Deserialize the result JSON blob back into a Python object.
    if data.get("result") is not None:
        try:
            data["result"] = json.loads(data["result"])
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to deserialize result JSON for project {}", data["id"])
    return data


class Database:
    """Async SQLite database for project persistence."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else _DB_PATH

    async def initialize(self) -> None:
        """Create the database directory and projects table if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE_SQL)
            await db.execute(_CREATE_CORRECTIONS_SQL)
            await db.execute(_CREATE_LEARNED_OVERRIDES_SQL)
            await db.commit()
        logger.info("Database initialized at {}", self._db_path)

    async def create_project(
        self,
        project_id: str,
        filename: str,
        upload_path: str,
        language: str = "en",
    ) -> dict[str, Any]:
        """Insert a new project and return it as a dict."""
        created_at = datetime.utcnow().isoformat()
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO projects (id, filename, upload_path, status, language, created_at)
                    VALUES (?, ?, ?, 'uploaded', ?, ?)
                    """,
                    (project_id, filename, upload_path, language, created_at),
                )
                await db.commit()
        except aiosqlite.IntegrityError:
            logger.error("Project {} already exists", project_id)
            raise ValueError(f"Project {project_id} already exists")

        logger.info("Created project {} ({})", project_id, filename)
        return {
            "id": project_id,
            "filename": filename,
            "upload_path": upload_path,
            "status": "uploaded",
            "language": language,
            "created_at": created_at,
            "result": None,
            "error": None,
        }

    async def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Fetch a single project by id, or None if not found."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return _row_to_dict(row)

    async def list_projects(self) -> list[dict[str, Any]]:
        """Return all projects ordered by creation date (newest first)."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM projects ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [_row_to_dict(row) for row in rows]

    async def update_project(self, project_id: str, **kwargs: Any) -> None:
        """Update one or more fields on an existing project.

        Accepted keyword arguments correspond to column names:
        status, language, result, error, filename, upload_path.

        The ``result`` value is automatically serialized to JSON text.
        """
        if not kwargs:
            return

        # Serialize result dict to JSON string for storage.
        if "result" in kwargs and kwargs["result"] is not None:
            try:
                kwargs["result"] = json.dumps(kwargs["result"], ensure_ascii=False)
            except (TypeError, ValueError) as exc:
                logger.error("Failed to serialize result for project {}: {}", project_id, exc)
                raise

        allowed_columns = {"filename", "upload_path", "status", "language", "result", "error"}
        invalid = set(kwargs.keys()) - allowed_columns
        if invalid:
            raise ValueError(f"Invalid column(s): {invalid}")

        set_clause = ", ".join(f"{col} = ?" for col in kwargs)
        values = list(kwargs.values()) + [project_id]

        async with aiosqlite.connect(self._db_path) as db:
            result = await db.execute(
                f"UPDATE projects SET {set_clause} WHERE id = ?",  # noqa: S608
                values,
            )
            await db.commit()
            if result.rowcount == 0:
                logger.warning("update_project: project {} not found", project_id)

    async def delete_old_projects(self, max_age_days: int = 30) -> int:
        """Delete projects older than *max_age_days* and return the count removed."""
        cutoff = (datetime.utcnow() - timedelta(days=max_age_days)).isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM projects WHERE created_at < ?", (cutoff,)
            )
            await db.commit()
            deleted = cursor.rowcount
        if deleted:
            logger.info("Deleted {} project(s) older than {} days", deleted, max_age_days)
        return deleted

    # ---- Corrections & Learned Overrides ----

    async def save_correction(self, correction_data: dict) -> None:
        """Insert a user correction into the corrections table.

        Args:
            correction_data: Dict with keys: id, project_id, item_no,
                field_name, old_value, new_value, element_type, category,
                created_at.
        """
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO corrections
                    (id, project_id, item_no, field_name, old_value,
                     new_value, element_type, category, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    correction_data["id"],
                    correction_data["project_id"],
                    correction_data["item_no"],
                    correction_data["field_name"],
                    correction_data.get("old_value"),
                    correction_data.get("new_value"),
                    correction_data.get("element_type"),
                    correction_data.get("category"),
                    correction_data["created_at"],
                ),
            )
            await db.commit()
        logger.debug("Saved correction {} for project {}", correction_data["id"], correction_data["project_id"])

    async def get_corrections_for_project(self, project_id: str) -> list[dict]:
        """Return all corrections for a given project.

        Args:
            project_id: The project to fetch corrections for.

        Returns:
            List of correction dicts.
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM corrections WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_learned_overrides(
        self, element_type: str, category: str | None = None
    ) -> list[dict]:
        """Return learned overrides for an element type and optional category.

        Args:
            element_type: IFC element type (e.g. IfcWall).
            category: Optional category filter.

        Returns:
            List of override dicts.
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            if category is not None:
                query = (
                    "SELECT * FROM learned_overrides "
                    "WHERE element_type = ? AND category = ?"
                )
                params: tuple = (element_type, category)
            else:
                query = "SELECT * FROM learned_overrides WHERE element_type = ?"
                params = (element_type,)
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def upsert_learned_override(
        self,
        element_type: str,
        category: str | None,
        field_name: str,
        pattern: str | None,
        override_value: str,
        confidence: float,
    ) -> None:
        """Insert or update a learned override.

        On conflict (element_type, category, field_name, pattern), updates
        the override_value, confidence, usage_count, and last_used.

        Args:
            element_type: IFC element type.
            category: Material / element category.
            field_name: The BOQ field this override applies to.
            pattern: Pattern key (material description or field name).
            override_value: The corrected value to apply.
            confidence: Computed confidence score.
        """
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO learned_overrides
                    (element_type, category, field_name, pattern,
                     override_value, confidence, usage_count, last_used)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(element_type, category, field_name, pattern)
                DO UPDATE SET
                    override_value = excluded.override_value,
                    confidence = excluded.confidence,
                    usage_count = usage_count + 1,
                    last_used = excluded.last_used
                """,
                (element_type, category, field_name, pattern, override_value, confidence, now),
            )
            await db.commit()
        logger.debug(
            "Upserted override for {}/{}/{} confidence={:.2f}",
            element_type, category, field_name, confidence,
        )

    async def boost_override_confidence(
        self, project_id: str, boost: float = 0.1
    ) -> None:
        """Increase confidence for overrides related to corrections from a project.

        Finds all corrections for the project, then boosts matching overrides
        by the given amount (capped at 0.95).

        Args:
            project_id: The project whose related overrides should be boosted.
            boost: Amount to increase confidence (default 0.1).
        """
        corrections = await self.get_corrections_for_project(project_id)
        if not corrections:
            logger.debug("No corrections found for project {} — nothing to boost", project_id)
            return

        async with aiosqlite.connect(self._db_path) as db:
            for corr in corrections:
                element_type = corr.get("element_type")
                category = corr.get("category")
                field_name = corr.get("field_name")
                new_value = corr.get("new_value")
                pattern = new_value if field_name == "description" else field_name

                await db.execute(
                    """
                    UPDATE learned_overrides
                    SET confidence = MIN(confidence + ?, 0.95)
                    WHERE element_type = ?
                      AND category = ?
                      AND field_name = ?
                      AND pattern = ?
                    """,
                    (boost, element_type, category, field_name, pattern),
                )
            await db.commit()
        logger.info("Boosted override confidence for {} correction(s) in project {}", len(corrections), project_id)
