"""
Export Service - generates Excel and CSV reports from BOQ data.

Coach Simple explains:
    "This takes our organized BOQ data and turns it into a real Excel
    spreadsheet that the client can open, print, and use. It has
    professional formatting with headers, colors, borders, and totals."
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.utils.logger import get_logger

logger = get_logger("export_service")


# Styling constants
HEADER_FILL = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
SECTION_FILL = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
SECTION_FONT = Font(name="Calibri", size=11, bold=True, color="2F5496")
ITEM_FONT = Font(name="Calibri", size=10)
TITLE_FONT = Font(name="Calibri", size=16, bold=True, color="2F5496")
SUBTITLE_FONT = Font(name="Calibri", size=12, color="666666")
THIN_BORDER = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)


class ExportService:
    """Generates reports from BOQ data."""

    def export_excel(
        self, boq_data: dict[str, Any], output_path: str | Path
    ) -> Path:
        """Export BOQ data to a professional Excel spreadsheet.

        Args:
            boq_data: The BOQ data dict from BOQGeneratorAgent.
            output_path: Where to save the .xlsx file.

        Returns:
            Path to the generated file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()

        # --- Sheet 1: BOQ (main report) ---
        ws = wb.active
        ws.title = "Bill of Quantities"
        self._write_boq_sheet(ws, boq_data)

        # --- Sheet 2: Material Summary ---
        ws2 = wb.create_sheet("Material Summary")
        self._write_summary_sheet(ws2, boq_data)

        wb.save(str(output_path))
        logger.info(f"Excel report saved: {output_path}")
        return output_path

    def _write_boq_sheet(self, ws, boq_data: dict[str, Any]) -> None:
        """Write the main BOQ sheet."""
        # Column widths
        ws.column_dimensions["A"].width = 10
        ws.column_dimensions["B"].width = 50
        ws.column_dimensions["C"].width = 8
        ws.column_dimensions["D"].width = 15
        ws.column_dimensions["E"].width = 15
        ws.column_dimensions["F"].width = 18

        row = 1

        # Title
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        cell = ws.cell(row=row, column=1, value="BILL OF QUANTITIES")
        cell.font = TITLE_FONT
        cell.alignment = Alignment(horizontal="center")
        row += 1

        # Project info
        project_name = boq_data.get("project_name", "Untitled")
        building_name = boq_data.get("building_name", "")
        date_str = datetime.now().strftime("%Y-%m-%d")

        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        cell = ws.cell(row=row, column=1, value=f"Project: {project_name}")
        cell.font = SUBTITLE_FONT
        cell.alignment = Alignment(horizontal="center")
        row += 1

        if building_name:
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
            cell = ws.cell(row=row, column=1, value=f"Building: {building_name}")
            cell.font = SUBTITLE_FONT
            cell.alignment = Alignment(horizontal="center")
            row += 1

        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        cell = ws.cell(
            row=row, column=1,
            value=f"Date: {date_str}  |  Prepared by: {boq_data.get('prepared_by', 'Metraj AI')}",
        )
        cell.font = Font(name="Calibri", size=9, color="999999")
        cell.alignment = Alignment(horizontal="center")
        row += 2

        # Column headers
        headers = ["Item No.", "Description", "Unit", "Quantity", "Rate", "Amount"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal="center", vertical="center")
        row += 1

        # Sections and items
        for section in boq_data.get("sections", []):
            # Section header row
            ws.merge_cells(
                start_row=row, start_column=1, end_row=row, end_column=6
            )
            cell = ws.cell(
                row=row, column=1,
                value=f"{section['section_no']}. {section['title']}",
            )
            cell.font = SECTION_FONT
            cell.fill = SECTION_FILL
            cell.border = THIN_BORDER
            for col in range(2, 7):
                ws.cell(row=row, column=col).fill = SECTION_FILL
                ws.cell(row=row, column=col).border = THIN_BORDER
            row += 1

            # Items
            for item in section.get("items", []):
                ws.cell(row=row, column=1, value=item["item_no"]).font = ITEM_FONT
                ws.cell(row=row, column=2, value=item["description"]).font = ITEM_FONT
                ws.cell(row=row, column=3, value=item["unit"]).font = ITEM_FONT

                qty_cell = ws.cell(row=row, column=4, value=item["quantity"])
                qty_cell.font = ITEM_FONT
                qty_cell.number_format = "#,##0.00"

                rate_cell = ws.cell(row=row, column=5, value=item.get("rate"))
                rate_cell.font = ITEM_FONT
                rate_cell.number_format = "#,##0.00"

                amount_cell = ws.cell(row=row, column=6, value=item.get("amount"))
                amount_cell.font = ITEM_FONT
                amount_cell.number_format = "#,##0.00"

                # Borders
                for col in range(1, 7):
                    ws.cell(row=row, column=col).border = THIN_BORDER
                    ws.cell(row=row, column=col).alignment = Alignment(
                        horizontal="left" if col == 2 else "center",
                        vertical="center",
                    )

                row += 1

            # Empty row between sections
            row += 1

        # Footer
        row += 1
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        cell = ws.cell(
            row=row, column=1,
            value="Generated by Metraj AI - Construction Material Estimation System",
        )
        cell.font = Font(name="Calibri", size=8, italic=True, color="999999")
        cell.alignment = Alignment(horizontal="center")

    def _write_summary_sheet(self, ws, boq_data: dict[str, Any]) -> None:
        """Write a material summary sheet (aggregated by material type)."""
        ws.column_dimensions["A"].width = 8
        ws.column_dimensions["B"].width = 45
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 15
        ws.column_dimensions["E"].width = 20

        row = 1

        # Title
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        cell = ws.cell(row=row, column=1, value="MATERIAL SUMMARY")
        cell.font = TITLE_FONT
        cell.alignment = Alignment(horizontal="center")
        row += 2

        # Headers
        headers = ["No.", "Material", "Unit", "Total Qty", "Category"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal="center")
        row += 1

        # Collect all unique materials across sections
        item_no = 0
        for section in boq_data.get("sections", []):
            for item in section.get("items", []):
                item_no += 1
                ws.cell(row=row, column=1, value=item_no).border = THIN_BORDER
                ws.cell(row=row, column=2, value=item["description"]).border = THIN_BORDER

                unit_cell = ws.cell(row=row, column=3, value=item["unit"])
                unit_cell.border = THIN_BORDER
                unit_cell.alignment = Alignment(horizontal="center")

                qty_cell = ws.cell(row=row, column=4, value=item["quantity"])
                qty_cell.border = THIN_BORDER
                qty_cell.number_format = "#,##0.00"
                qty_cell.alignment = Alignment(horizontal="right")

                cat_cell = ws.cell(
                    row=row, column=5, value=section["title"]
                )
                cat_cell.border = THIN_BORDER
                cat_cell.font = Font(name="Calibri", size=9, color="666666")

                row += 1

    def export_csv(
        self, boq_data: dict[str, Any], output_path: str | Path
    ) -> Path:
        """Export BOQ data to a CSV file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Item No.", "Description", "Unit", "Quantity", "Rate", "Amount", "Section"])

            for section in boq_data.get("sections", []):
                for item in section.get("items", []):
                    writer.writerow([
                        item["item_no"],
                        item["description"],
                        item["unit"],
                        item["quantity"],
                        item.get("rate", ""),
                        item.get("amount", ""),
                        section["title"],
                    ])

        logger.info(f"CSV report saved: {output_path}")
        return output_path

    def export_json(
        self, boq_data: dict[str, Any], output_path: str | Path
    ) -> Path:
        """Export BOQ data to a JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(boq_data, f, indent=2, ensure_ascii=False)

        logger.info(f"JSON report saved: {output_path}")
        return output_path
