"""
Material data models - represents construction materials mapped from quantities.

Coach Simple explains:
    "Now we know the measurements (30 m2 of wall). But what MATERIALS
    do we need to BUILD that wall? Concrete, steel rebar, plaster, paint...
    These models hold that shopping list."
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, computed_field

from .project import ElementCategory


class MaterialItem(BaseModel):
    """A single material needed for construction.

    Example: 'Concrete C25/30', 6.0 m3, with 5% waste = 6.3 m3 total
    """

    description: str = Field(description="Material name, e.g. 'Concrete C25/30'")
    unit: str = Field(description="Unit: m2, m3, m, kg, nr (number)")
    quantity: float = Field(description="Base quantity needed")
    waste_factor: float = Field(
        default=0.0,
        description="Waste percentage as decimal, e.g. 0.05 for 5%",
    )
    category: Optional[ElementCategory] = Field(default=None)
    source_elements: list[int] = Field(
        default_factory=list,
        description="IFC element IDs that need this material",
    )
    notes: Optional[str] = Field(default=None)

    @computed_field
    @property
    def total_quantity(self) -> float:
        """Quantity including waste factor."""
        return round(self.quantity * (1 + self.waste_factor), 3)


class MaterialSummary(BaseModel):
    """Aggregated material summary - same materials combined across all elements."""

    description: str
    unit: str
    total_base_quantity: float = Field(description="Sum of base quantities")
    average_waste_factor: float = Field(description="Average waste factor applied")
    total_with_waste: float = Field(description="Total including waste")
    element_count: int = Field(description="Number of elements needing this material")
    category: Optional[ElementCategory] = None


class WasteFactor(BaseModel):
    """Waste factor for a specific material type."""

    material_type: str = Field(description="e.g. 'concrete', 'steel', 'bricks'")
    standard: float = Field(description="Standard waste percentage as decimal")
    complex_geometry: float = Field(
        default=0.0,
        description="Higher waste for complex shapes",
    )
    notes: Optional[str] = None
