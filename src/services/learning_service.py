"""
Learning service for Metraj — records user corrections and builds
learned overrides that improve future pipeline runs.

Usage:
    from src.services.learning_service import LearningService

    learning_svc = LearningService(db)
    await learning_svc.record_correction(project_id, item_no, "quantity", "10", "12", "IfcWall", "Concrete")
"""

from __future__ import annotations

from src.services.database import Database
from src.utils.logger import get_logger

logger = get_logger("learning_service")


class LearningService:
    """Records user corrections on BOQ items and manages learned overrides
    that improve accuracy of future pipeline runs."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def record_correction(
        self,
        project_id: str,
        item_no: str,
        field_name: str,
        old_value: str,
        new_value: str,
        element_type: str,
        category: str,
    ) -> None:
        """Store a user correction and update (or create) a learned override.

        Args:
            project_id: The project this correction belongs to.
            item_no: The BOQ line-item number that was edited.
            field_name: Which field was changed (quantity, description, unit, waste_factor).
            old_value: The original value before user edit.
            new_value: The corrected value from the user.
            element_type: IFC element type (e.g. IfcWall).
            category: Material / element category.
        """
        import uuid
        from datetime import datetime

        correction_data = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "item_no": item_no,
            "field_name": field_name,
            "old_value": old_value,
            "new_value": new_value,
            "element_type": element_type,
            "category": category,
            "created_at": datetime.utcnow().isoformat(),
        }

        await self._db.save_correction(correction_data)
        logger.info(
            "Recorded correction for project={} item={} field={}: {} -> {}",
            project_id, item_no, field_name, old_value, new_value,
        )

        # Determine the pattern key for the override
        # For material-related corrections use the description (new_value),
        # for quantity corrections use the field_name itself.
        pattern = new_value if field_name == "description" else field_name

        # Check existing overrides to compute consistency
        existing_overrides = await self._db.get_learned_overrides(element_type, category)
        match = None
        for ov in existing_overrides:
            if ov["field_name"] == field_name and ov["pattern"] == pattern:
                match = ov
                break

        if match:
            new_count = match["usage_count"] + 1
            # Simple consistency heuristic: if new_value equals current override,
            # consistency is perfect; otherwise it's reduced.
            consistency = 1.0 if match["override_value"] == new_value else 0.5
            confidence = self.compute_override_confidence(new_count, consistency)
            override_value = new_value
            await self._db.upsert_learned_override(
                element_type=element_type,
                category=category,
                field_name=field_name,
                pattern=pattern,
                override_value=override_value,
                confidence=confidence,
            )
        else:
            confidence = self.compute_override_confidence(1, 1.0)
            await self._db.upsert_learned_override(
                element_type=element_type,
                category=category,
                field_name=field_name,
                pattern=pattern,
                override_value=new_value,
                confidence=confidence,
            )

    async def get_overrides_for_element(
        self, element_type: str, category: str
    ) -> list[dict]:
        """Return learned overrides for a given element type and category.

        Only returns overrides with confidence >= 0.6 and usage_count >= 3.

        Args:
            element_type: IFC element type (e.g. IfcWall).
            category: Material / element category.

        Returns:
            List of override dicts with keys: field_name, pattern,
            override_value, confidence, usage_count.
        """
        all_overrides = await self._db.get_learned_overrides(element_type, category)
        return [
            {
                "field_name": ov["field_name"],
                "pattern": ov["pattern"],
                "override_value": ov["override_value"],
                "confidence": ov["confidence"],
                "usage_count": ov["usage_count"],
            }
            for ov in all_overrides
            if ov["confidence"] >= 0.6 and ov["usage_count"] >= 3
        ]

    @staticmethod
    def compute_override_confidence(
        usage_count: int, consistency_ratio: float
    ) -> float:
        """Compute confidence score for a learned override.

        Formula: min(0.5 + (usage_count * 0.1) * consistency_ratio, 0.95)

        Args:
            usage_count: How many times this override has been applied.
            consistency_ratio: Fraction of corrections in the same direction
                (0.0 to 1.0).

        Returns:
            Confidence score capped at 0.95.
        """
        return min(0.5 + (usage_count * 0.1) * consistency_ratio, 0.95)

    async def approve_project_corrections(self, project_id: str) -> None:
        """Boost confidence of all overrides derived from corrections in this project.

        Args:
            project_id: The project whose corrections should be approved.
        """
        await self._db.boost_override_confidence(project_id, boost=0.1)
        logger.info("Approved corrections for project {}, boosted override confidence", project_id)
