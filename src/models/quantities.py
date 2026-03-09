"""
Quantity data models - represents calculated measurements for building elements.

Coach Simple explains:
    "After we count the LEGO pieces (parsing), we need to MEASURE them.
    How much area does this wall cover? How much volume of concrete?
    These models hold those measurements."
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .project import ElementCategory


class CalculatedQuantity(BaseModel):
    """A single calculated quantity for a building element.

    Example: Wall #1 has a GrossArea of 30.0 m2
    """

    element_id: int = Field(description="IFC element ID this quantity belongs to")
    element_type: str = Field(description="IFC type, e.g. 'IfcWall'")
    element_name: Optional[str] = Field(default=None)
    description: str = Field(description="What this quantity represents, e.g. 'Gross wall area'")
    quantity: float = Field(description="The numeric value")
    unit: str = Field(description="Unit of measurement: m2, m3, m, kg, nr")
    category: Optional[ElementCategory] = Field(default=None)
    storey: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)


class ElementQuantitySummary(BaseModel):
    """All calculated quantities for a single building element."""

    element_id: int
    element_type: str
    element_name: Optional[str] = None
    storey: Optional[str] = None
    category: Optional[ElementCategory] = None
    quantities: list[CalculatedQuantity] = Field(default_factory=list)

    @property
    def gross_area(self) -> float:
        """Get gross area if available."""
        for q in self.quantities:
            if "gross" in q.description.lower() and "area" in q.description.lower():
                return q.quantity
        return 0.0

    @property
    def net_area(self) -> float:
        """Get net area (minus openings) if available."""
        for q in self.quantities:
            if "net" in q.description.lower() and "area" in q.description.lower():
                return q.quantity
        return self.gross_area

    @property
    def volume(self) -> float:
        """Get volume if available."""
        for q in self.quantities:
            if "volume" in q.description.lower():
                return q.quantity
        return 0.0
