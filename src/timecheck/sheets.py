"""Google Sheet tab mapping and workbook import for TimeCheck."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from .registry import TABLES

if TYPE_CHECKING:
    from .timecheck import TimeCheck

# Maps Google Sheet tab names to TimeCheck table names.
SHEET_TAB_MAP: dict[str, str] = {
    "Daily": "log",
    "TimeSheet": "timesheet",
    "Tasks": "tasks",
    "Projects": "projects",
    "Areas": "areas",
}

# Alternate tab names seen in exports or older versions.
SHEET_TAB_ALIASES: dict[str, str] = {
    "daily": "log",
    "timesheet": "timesheet",
    "tasks": "tasks",
    "projects": "projects",
    "areas": "areas",
    "log": "log",
}


def resolve_table_name(sheet_name: str) -> str | None:
    name = str(sheet_name).strip()
    if name in SHEET_TAB_MAP:
        return SHEET_TAB_MAP[name]
    lowered = name.lower()
    if lowered in SHEET_TAB_ALIASES:
        return SHEET_TAB_ALIASES[lowered]
    return None


def _normalize_columns(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    expected = TABLES[table_name]["columns"]
    rename: dict[str, str] = {}
    for column in df.columns:
        key = str(column).strip()
        for expected_column in expected:
            if key.lower() == expected_column.lower():
                rename[column] = expected_column
                break
    normalized = df.rename(columns=rename)
    missing = [column for column in expected if column not in normalized.columns]
    if missing:
        raise ValueError(
            f"{table_name}: sheet is missing columns: {', '.join(missing)}"
        )
    return normalized[expected].fillna("")


def read_workbook(path: str | Path) -> dict[str, pd.DataFrame]:
    """Read a Google Sheets .xlsx export into table DataFrames."""
    try:
        workbook = pd.ExcelFile(path)
    except ImportError as exc:
        raise ImportError(
            "Reading .xlsx files requires openpyxl. Install with: pip install openpyxl"
        ) from exc

    tables: dict[str, pd.DataFrame] = {}
    for sheet_name in workbook.sheet_names:
        table_name = resolve_table_name(sheet_name)
        if table_name is None:
            continue
        df = pd.read_excel(workbook, sheet_name=sheet_name, dtype=str).fillna("")
        if df.empty:
            continue
        df = df.loc[df.astype(str).apply(lambda row: any(cell.strip() for cell in row), axis=1)]
        if df.empty:
            continue
        tables[table_name] = _normalize_columns(table_name, df)
    return tables


def import_workbook(
    tc: TimeCheck,
    path: str | Path,
    *,
    replace: bool = True,
) -> dict[str, int]:
    """Import sheet tabs from a workbook into a TimeCheck profile."""
    tables = read_workbook(path)
    if not tables:
        raise ValueError("No recognized sheets found (Daily, Tasks, Projects, Areas, TimeSheet).")

    imported: dict[str, int] = {}
    for table_name, df in tables.items():
        table = tc.table(table_name)
        if replace:
            table._df = table._normalize(df)
        else:
            for _, row in df.iterrows():
                if table.primary_key:
                    key = str(row[table.primary_key])
                    try:
                        table.update(key=key, **row.to_dict())
                        continue
                    except KeyError:
                        pass
                table.add(row.to_dict())
        imported[table_name] = len(df)

    if "timesheet" in tables and tc.config.get("timesheet_areas"):
        pass
    elif "timesheet" in tables:
        area_columns = [
            column.removesuffix(" time")
            for column in tables["timesheet"].columns
            if column.endswith(" time") and column != "Total Work Hours"
        ]
        if area_columns:
            tc.set_timesheet_areas(area_columns)

    tc.save()
    return imported
