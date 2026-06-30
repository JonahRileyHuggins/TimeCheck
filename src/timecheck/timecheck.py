"""Main API for the TimeCheck time-management application."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from .file_loader import FileLoader
from .alerts import Alert, AlertManager
from .metrics import TimeMetric, TimeMetrics
from .profiles import (
    list_profiles,
    local_registry_dir,
    registry_path,
    remove_profile,
    resolve_data_root,
    set_profile_path,
    get_profile_path,
)
from .registry import DATA_ROOT, TABLES, default_user_config, table_path, timesheet_columns
from .table import DataTable
from .triggers import register_default_triggers


def _format_datetime(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return f"{value.month}/{value.day}/{value.year} {value.strftime('%I:%M:%S%p')}"
    return str(value)


def _format_date(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return f"{value.month}/{value.day}/{value.year}"
    return str(value)


def _format_duration(start: datetime, stop: datetime) -> str:
    seconds = max(int((stop - start).total_seconds()), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


class TimeCheck:
    """
    Main API for reading and writing TimeCheck data sheets.

    Tables:
      - areas: life areas (PhD, Business, Personal, ...)
      - projects: projects within an area
      - tasks: tasks within a project
      - log: task-by-task timestamps
      - timesheet: daily rollups
    """

    def __init__(
        self,
        data_root: str | Path | None = None,
        name: str | None = None,
        *,
        register: bool = True,
    ) -> None:
        self.data_root = resolve_data_root(name=name, data_root=data_root)
        self.data_root.mkdir(parents=True, exist_ok=True)

        self._config_path = self.data_root / "config.json"
        self._ensure_config()
        self._config_loader = FileLoader(self._config_path)
        self.config = self._config_loader.load()

        if name is not None:
            self.config["name"] = name
            self.save_config()
            if register and data_root is not None:
                set_profile_path(name, self.data_root)

        self._tables: dict[str, DataTable] = {}
        for table_name, table_def in TABLES.items():
            columns = list(table_def["columns"])
            if table_name == "timesheet":
                configured_areas = list(self.config.get("timesheet_areas") or [])
                if configured_areas:
                    columns = timesheet_columns(configured_areas)
            table = DataTable(
                name=table_name,
                path=str(table_path(table_name, self.data_root)),
                columns=columns,
                primary_key=table_def.get("primary_key"),
            )
            table.ensure_file()
            table.load()
            self._tables[table_name] = table

        self._metrics = TimeMetrics(self)
        self._alerts = AlertManager(self)
        self._triggers = register_default_triggers(self)

    @property
    def areas(self) -> DataTable:
        return self._tables["areas"]

    @property
    def projects(self) -> DataTable:
        return self._tables["projects"]

    @property
    def tasks(self) -> DataTable:
        return self._tables["tasks"]

    @property
    def log(self) -> DataTable:
        return self._tables["log"]

    @property
    def timesheet(self) -> DataTable:
        return self._tables["timesheet"]

    @property
    def metrics(self) -> TimeMetrics:
        return self._metrics

    @property
    def alerts(self) -> AlertManager:
        return self._alerts

    def check_alerts(
        self,
        *,
        reference: datetime | str | None = None,
        dispatch: bool = False,
    ) -> list[Alert]:
        """Evaluate weekly hour thresholds. Set dispatch=True to run alert handlers."""
        if dispatch:
            return self._alerts.run_checks(reference=reference)
        return self._alerts.check(reference=reference)

    def table(self, name: str) -> DataTable:
        return self._tables[name]

    def load(self, name: str | None = None) -> pd.DataFrame | dict[str, pd.DataFrame]:
        if name is None:
            return {table_name: table.load() for table_name, table in self._tables.items()}
        return self._tables[name].load()

    def save(self, name: str | None = None) -> None:
        if name is None:
            for table in self._tables.values():
                table.save()
            return
        self._tables[name].save()

    def add(self, name: str, entry: dict[str, Any]) -> int:
        self._triggers.before_add(name, entry)
        index = self._tables[name].add(entry)
        self._triggers.after_add(name, entry)
        return index

    def update(
        self,
        name: str,
        entry: dict[str, Any] | None = None,
        index: int | None = None,
        key: str | None = None,
        **fields: Any,
    ) -> int:
        if entry is not None:
            fields = {**entry, **fields}
        old_entry = self._tables[name].get(index=index, key=key)
        self._triggers.before_update(name, old_entry, fields)
        row_index = self._tables[name].update(index=index, key=key, **fields)
        new_entry = self._tables[name].get(index=row_index)
        self._triggers.after_update(name, old_entry, new_entry)
        return row_index

    def delete(
        self,
        name: str,
        index: int | None = None,
        key: str | None = None,
    ) -> None:
        entry = self._tables[name].get(index=index, key=key)
        self._triggers.before_delete(name, entry)
        self._tables[name].delete(index=index, key=key)
        self._triggers.after_delete(name, entry)

    def get(
        self,
        name: str,
        index: int | None = None,
        key: str | None = None,
    ) -> dict[str, str]:
        return self._tables[name].get(index=index, key=key)

    def find(self, name: str, **filters: Any) -> pd.DataFrame:
        return self._tables[name].find(**filters)

    def log_entry(
        self,
        task: str,
        date: datetime | str | None = None,
        start: datetime | str | None = None,
        stop: datetime | str | None = None,
        notes: str = "",
    ) -> int:
        """Append a timestamped row to the log sheet."""
        now = datetime.now()
        start_dt = start if isinstance(start, datetime) else now
        default_minutes = int(self.config.get("default_log_duration_minutes", 15))
        stop_dt = (
            stop
            if isinstance(stop, datetime)
            else start_dt + timedelta(minutes=default_minutes)
        )
        if stop in ("", None) and not isinstance(stop, datetime):
            stop_dt = start_dt + timedelta(minutes=default_minutes)

        entry_date = date if date is not None else start_dt
        return self.add(
            "log",
            {
                "date": _format_date(entry_date),
                "task": task,
                "start": _format_datetime(start_dt),
                "stop": _format_datetime(stop_dt),
                "total": _format_duration(start_dt, stop_dt),
                "notes": notes,
            },
        )

    def set_timesheet_areas(self, areas: list[str]) -> None:
        """Choose which areas appear on the timesheet and receive daily rollups."""
        selected = [str(area).strip() for area in areas if str(area).strip()]
        self.update_config(timesheet_areas=selected)
        self._rebuild_timesheet(selected)

    def _rebuild_timesheet(self, areas: list[str]) -> None:
        old_df = self.timesheet.df.copy()
        new_columns = timesheet_columns(areas)

        rows: list[dict[str, str]] = []
        for _, row in old_df.iterrows():
            new_row = {column: "" for column in new_columns}
            new_row["Date"] = str(row.get("Date", ""))
            for area in areas:
                column = f"{area} time"
                new_row[column] = str(row.get(column, "0:00:00") or "0:00:00")
            new_row["Total Work Hours"] = str(
                row.get("Total Work Hours", "0:00:00") or "0:00:00"
            )
            new_row["7-Day Total"] = str(row.get("7-Day Total", "") or "")
            new_row["Day"] = str(row.get("Day", "") or "")
            rows.append(new_row)

        path = str(table_path("timesheet", self.data_root))
        table = DataTable(
            name="timesheet",
            path=path,
            columns=new_columns,
            primary_key="Date",
        )
        if rows:
            table._df = table._normalize(pd.DataFrame(rows))
        self._tables["timesheet"] = table

    def save_config(self) -> None:
        self._config_loader.save(dict(self.config))

    def update_config(self, **settings: Any) -> None:
        self.config.update(settings)
        self.save_config()

    @classmethod
    def profile_path(cls, name: str) -> Path | None:
        """Return the locally registered data directory for a user."""
        return get_profile_path(name)

    @classmethod
    def register_profile(cls, name: str, data_root: str | Path) -> Path:
        """Remember where a user's data directory lives on this machine."""
        return set_profile_path(name, data_root)

    @classmethod
    def unregister_profile(cls, name: str) -> None:
        """Remove a user's locally registered data directory mapping."""
        remove_profile(name)

    @classmethod
    def list_profiles(cls) -> dict[str, str]:
        """Return all user-to-data-directory mappings stored on this machine."""
        return list_profiles()

    @classmethod
    def profile_registry_path(cls) -> Path:
        """Return the local file that stores profile path mappings."""
        return registry_path()

    @classmethod
    def profile_registry_dir(cls) -> Path:
        """Return the local directory that stores profile path mappings."""
        return local_registry_dir()

    def _ensure_config(self) -> None:
        if self._config_path.exists():
            return
        FileLoader(self._config_path).save(default_user_config())
