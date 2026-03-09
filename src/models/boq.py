"""
Bill of Quantities (BOQ) data models - the final output structure.

Coach Simple explains:
    "The BOQ is the final shopping list! It's organized into sections
    (like aisles in a store), and each item has a number, description,
    unit, quantity, and price. This is what the client gets."
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field

from .project import ElementCategory


class BOQLineItem(BaseModel):
    """A single line in the Bill of Quantities.

    Example:
        Item 1.01 | Concrete C25/30 for external walls | m3 | 43.20 | $120 | $5,184
    """

    item_no: str = Field(description="Hierarchical item number, e.g. '1.01'")
    description: str = Field(description="What this item is")
    unit: str = Field(description="Unit of measurement")
    quantity: float = Field(description="Total quantity including waste")
    rate: Optional[float] = Field(default=None, description="Unit price")
    category: ElementCategory

    @computed_field
    @property
    def amount(self) -> Optional[float]:
        """Total cost = quantity * rate."""
        if self.rate is not None:
            return round(self.quantity * self.rate, 2)
        return None


class BOQSection(BaseModel):
    """A section of the BOQ grouped by category.

    Example: Section 1 - Substructure, containing all foundation items.
    """

    section_no: int
    title: str = Field(description="Section title, e.g. 'Substructure'")
    category: ElementCategory
    items: list[BOQLineItem] = Field(default_factory=list)

    @computed_field
    @property
    def subtotal(self) -> Optional[float]:
        """Sum of all item amounts in this section."""
        amounts = [item.amount for item in self.items if item.amount is not None]
        if amounts:
            return round(sum(amounts), 2)
        return None

    @property
    def total_items(self) -> int:
        return len(self.items)


class BOQReport(BaseModel):
    """The complete Bill of Quantities report."""

    # Header info
    project_name: str = Field(default="Untitled Project")
    building_name: Optional[str] = None
    prepared_by: str = Field(default="Metraj AI System")
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))

    # BOQ content
    sections: list[BOQSection] = Field(default_factory=list)

    # Summary
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def grand_total(self) -> Optional[float]:
        """Sum of all section subtotals."""
        subtotals = [s.subtotal for s in self.sections if s.subtotal is not None]
        if subtotals:
            return round(sum(subtotals), 2)
        return None

    @property
    def total_line_items(self) -> int:
        return sum(s.total_items for s in self.sections)

    @property
    def total_sections(self) -> int:
        return len(self.sections)
