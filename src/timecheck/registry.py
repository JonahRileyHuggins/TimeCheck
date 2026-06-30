"""Data table definitions and default user configuration."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]
DATA_ROOT = PACKAGE_ROOT.parent / "data"

DEFAULT_USER_CONFIG = {
    "name": "",
    "default_log_duration_minutes": 15,
    "timesheet_areas": [],
}

TABLES = {
    "log": {
        "filename": "log.tsv",
        "primary_key": None,
        "columns": [
            "date",
            "task",
            "start",
            "stop",
            "total",
            "notes",
        ],
        "triggers": {
            "before_add": [],
            "after_add": [],
            "before_update": [],
            "after_update": [],
            "before_delete": [],
            "after_delete": [],
        }
    },
    "tasks": {
        "filename": "tasks.tsv",
        "primary_key": "task",
        "columns": [
            "task",
            "project",
            "details",
            "priority",
            "time log",
            "status",
            "Anticipated Time",
            "start date",
            "due date",
            "point of contact",
            "last update",
            "completed on",
        ],
        "triggers": {
            "before_add": [],
            "after_add": [],
            "before_update": [],
            "after_update": [],
            "before_delete": [],
            "after_delete": [],
        }
    },
    "projects": {
        "filename": "projects.tsv",
        "primary_key": "project",
        "columns": [
            "project",
            "time log",
            "max weekly hours",
            "due date",
            "#tasks",
            "area",
            "status",
        ],
        "triggers": {
            "before_add": [],
            "after_add": [],
            "before_update": [],
            "after_update": [],
            "before_delete": [],
            "after_delete": [],
        }
    },
    "areas": {
        "filename": "areas.tsv",
        "primary_key": "area",
        "columns": [
            "area",
            "time log",
            "Max Weekly Hours",
            "Alert",
        ],
        "triggers": {
            "before_add": [],
            "after_add": [],
            "before_update": [],
            "after_update": [],
            "before_delete": [],
            "after_delete": [],
        }
    },
    "timesheet": {
        "filename": "timesheet.tsv",
        "primary_key": "Date",
        "columns": [
            "Date",
            "PhD time",
            "Business time",
            "Total Work Hours",
            "7-Day Total",
            "Day",
        ],
        "triggers": {
            "before_add": [],
            "after_add": [],
            "before_update": [],
            "after_update": [],
            "before_delete": [],
            "after_delete": [],
        }
    },
}


def timesheet_columns(areas: list[str]) -> list[str]:
    columns = ["Date"]
    columns.extend(f"{area} time" for area in areas)
    columns.extend(["Total Work Hours", "7-Day Total", "Day"])
    return columns


def table_path(name: str, data_root: Path | None = None) -> Path:
    if name not in TABLES:
        raise KeyError(f"Unknown table: {name}. Available: {', '.join(TABLES)}")
    root = data_root or DATA_ROOT
    return root / TABLES[name]["filename"]


def default_user_config() -> dict:
    return deepcopy(DEFAULT_USER_CONFIG)
