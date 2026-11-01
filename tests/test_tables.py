import io

import openpyxl
import pandas as pd

from tables import generate_styled_excel, parse_markdown_table_to_df

TABLE = """| Name | Phone |
|---|---|
| Acme | +91 1234567890 |
| Beta | N/A |
"""


def test_parses_basic_table():
    df = parse_markdown_table_to_df(TABLE)
    assert list(df.columns) == ["Name", "Phone"]
    assert df.values.tolist() == [["Acme", "+91 1234567890"], ["Beta", "N/A"]]


def test_ignores_text_around_the_table():
    df = parse_markdown_table_to_df("Here you go:\n\n" + TABLE + "\nHope that helps!")
    assert len(df) == 2


def test_no_table_returns_none():
    for text in ["", None, "just prose", "| header only |", "|---|---|"]:
        assert parse_markdown_table_to_df(text) is None


def test_short_rows_are_padded_and_long_rows_truncated():
    df = parse_markdown_table_to_df("| A | B |\n|---|---|\n| 1 |\n| 1 | 2 | 3 |\n")
    assert df.values.tolist() == [["1", "N/A"], ["1", "2"]]


def test_na_variants_are_normalised_case_insensitively():
    md = "| A |\n|---|\n| Not Available |\n| unknown |\n| n/a |\n| NULL |\n| - |\n| real |\n"
    assert parse_markdown_table_to_df(md)["A"].tolist() == ["N/A"] * 5 + ["real"]


def _sheet(df):
    return openpyxl.load_workbook(io.BytesIO(generate_styled_excel(df))).active


def test_excel_roundtrip_header_and_values():
    ws = _sheet(parse_markdown_table_to_df(TABLE))
    assert [c.value for c in ws[1]] == ["Name", "Phone"]
    assert ws["A2"].value == "Acme"
    assert ws["A1"].fill.start_color.rgb.endswith("1F4E78")


def test_excel_highlights_na_cells_only():
    ws = _sheet(parse_markdown_table_to_df(TABLE))
    assert ws["B3"].fill.start_color.rgb.endswith("FCE4D6")
    assert ws["B2"].fill.fill_type is None


def test_excel_never_stores_scraped_text_as_a_formula():
    evil = '=HYPERLINK("http://evil.example","click")'
    ws = _sheet(pd.DataFrame([[evil, "+91 1234567890", "=1+1"]], columns=["a", "b", "c"]))
    assert ws["A2"].data_type == "s" and ws["A2"].value == evil
    assert ws["C2"].data_type == "s"
    assert ws["B2"].value == "+91 1234567890"
