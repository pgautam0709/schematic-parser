"""
Excel Exporter — writes CliRows to an .xlsx file using openpyxl.

Output columns:
  1. Page Number
  2. Component Name
  3. DT Name          (full value, no stripping)
  4. Comment          ("needs review" or blank)
  5. Confidence Spatial
  6. Confidence LLM

Formatting:
  - Header row: bold text, light blue fill
  - "needs review" rows: light yellow fill for all cells
  - Confidence columns: displayed as percentage (e.g. 0.90 → "90%")
  - All columns auto-sized (capped at 50 chars wide)
  - Header row is frozen (freeze_panes)
"""
from __future__ import annotations
from pathlib import Path
from pipeline.normalizer import CliRow

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
except ImportError as exc:
    raise ImportError("openpyxl is required. Run: pip install openpyxl") from exc

COLUMNS = [
    "Page Number",
    "Component Name",
    "DT Name",
    "Comment",
    "Confidence Spatial",
    "Confidence LLM",
]

HEADER_FILL = PatternFill("solid", fgColor="CCE5FF")   # light blue
REVIEW_FILL = PatternFill("solid", fgColor="FFFF99")   # light yellow
HEADER_FONT = Font(bold=True)
CENTER = Alignment(horizontal="center")


def write_excel(rows: list[CliRow], output_path: str | Path) -> None:
    """
    Write all CliRows to an Excel file.

    Args:
        rows:        List of CliRow objects from the pipeline
        output_path: Destination .xlsx path (created or overwritten)
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DT Mapping"

    # Header row
    for col_idx, col_name in enumerate(COLUMNS, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER

    # Freeze header
    ws.freeze_panes = "A2"

    # Data rows
    for row_idx, row in enumerate(rows, 2):
        values = [
            row.page_number,
            row.component_name,
            row.dt_full,
            row.comment,
            row.confidence_spatial,
            row.confidence_llm,
        ]
        is_review = row.comment == "needs review"

        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            if is_review:
                cell.fill = REVIEW_FILL
            # Center-align numeric columns
            if col_idx in (1, 5, 6):
                cell.alignment = CENTER

    # Auto-fit column widths
    for col_idx, col_name in enumerate(COLUMNS, 1):
        col_letter = get_column_letter(col_idx)
        # Measure max content width in this column
        max_width = len(col_name)
        for row_idx in range(2, ws.max_row + 1):
            cell_val = ws.cell(row=row_idx, column=col_idx).value
            if cell_val is not None:
                max_width = max(max_width, len(str(cell_val)))
        ws.column_dimensions[col_letter].width = min(max_width + 4, 50)

    wb.save(str(output_path))
