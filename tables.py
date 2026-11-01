"""
tables.py

Markdown-table parsing and styled Excel export, split out of main.py (a Streamlit
script that runs its UI on import) so both can be tested.
"""

import io
import re

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows

# Lower-cased spellings the models use for "no data"; all normalised to "N/A".
_NA_VARIANTS = {
    "data not available", "not available", "not listed", "unknown", "none",
    "null", "nan", "", "-", "n/a", "n/a.",
}


def parse_markdown_table_to_df(md_text):
    """First Markdown table in `md_text` -> DataFrame, or None if there isn't one."""
    if not md_text:
        return None
    try:
        lines = [line.strip() for line in md_text.split("\n") if line.strip()]
        separator_idx = -1
        for i, line in enumerate(lines):
            if re.match(r"^\|[\s=:|-]+\|$", line):
                separator_idx = i
                break
        if separator_idx <= 0:
            return None

        headers = [c.strip() for c in lines[separator_idx - 1].split("|")[1:-1] if c.strip()]
        if not headers:
            return None

        data_rows = []
        for row in lines[separator_idx + 1:]:
            if not row.startswith("|"):
                continue
            cells = [c.strip() for c in row.split("|")[1:-1]]
            if len(cells) < len(headers):
                cells += ["N/A"] * (len(headers) - len(cells))
            else:
                cells = cells[: len(headers)]
            data_rows.append(cells)

        if not data_rows:
            return None

        df = pd.DataFrame(data_rows, columns=headers)
        return df.map(lambda v: "N/A" if str(v).strip().lower() in _NA_VARIANTS else v)
    except Exception:
        return None


def generate_styled_excel(df: pd.DataFrame) -> bytes:
    """DataFrame -> styled .xlsx bytes. N/A cells are highlighted."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Market Leads")
        worksheet = writer.sheets["Market Leads"]

        na_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
        na_font = Font(name="Calibri", size=11, italic=True, color="C00000")
        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font

        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=False), start=2):
            for c_idx, value in enumerate(row, start=1):
                cell = worksheet.cell(row=r_idx, column=c_idx)
                # Scraped text must never run as a formula. openpyxl treats any
                # string starting with "=" as one (e.g. =HYPERLINK(...)), so force
                # those cells to plain strings.
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    cell.data_type = "s"
                if str(value).strip() == "N/A":
                    cell.fill = na_fill
                    cell.font = na_font

        for col in worksheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            worksheet.column_dimensions[col[0].column_letter].width = max(max_len + 3, 12)

    return buffer.getvalue()
