"""Triggers for TimeCheck."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Callable

from .duration import (
    add_durations,
    apply_duration_delta,
    day_of_week,
    format_date,
    parse_date,
    parse_duration,
    format_duration_seconds,
    subtract_durations,
)
from .registry import TABLES, timesheet_columns

if TYPE_CHECKING:
    from .timecheck import TimeCheck


class Triggers:
    """Handle table mutation callbacks for each trigger event."""

    def __init__(self) -> None:
        self._triggers: dict[str, dict[str, list[Callable[..., None]]]] = {}
        for table_name in TABLES:
            self._triggers[table_name] = {
                "before_add": [],
                "after_add": [],
                "before_update": [],
                "after_update": [],
                "before_delete": [],
                "after_delete": [],
            }

    def add_trigger(self, table_name: str, trigger_type: str, callback: Callable[..., None]) -> None:
        self._triggers[table_name][trigger_type].append(callback)

    def remove_trigger(self, table_name: str, trigger_type: str, callback: Callable[..., None]) -> None:
        self._triggers[table_name][trigger_type].remove(callback)

    def clear_triggers(self, table_name: str) -> None:
        for trigger_type in self._triggers[table_name]:
            self._triggers[table_name][trigger_type].clear()

    def trigger(self, table_name: str, trigger_type: str, *args: Any, **kwargs: Any) -> None:
        for callback in self._triggers[table_name][trigger_type]:
            callback(*args, **kwargs)

    def before_add(self, table_name: str, entry: dict[str, Any]) -> None:
        self.trigger(table_name, "before_add", entry)

    def after_add(self, table_name: str, entry: dict[str, Any]) -> None:
        self.trigger(table_name, "after_add", entry)

    def before_update(
        self,
        table_name: str,
        old_entry: dict[str, Any],
        fields: dict[str, Any],
    ) -> None:
        self.trigger(table_name, "before_update", old_entry, fields)

    def after_update(
        self,
        table_name: str,
        old_entry: dict[str, Any],
        new_entry: dict[str, Any],
    ) -> None:
        self.trigger(table_name, "after_update", old_entry, new_entry)

    def before_delete(self, table_name: str, entry: dict[str, Any]) -> None:
        self.trigger(table_name, "before_delete", entry)

    def after_delete(self, table_name: str, entry: dict[str, Any]) -> None:
        self.trigger(table_name, "after_delete", entry)


def register_default_triggers(tc: TimeCheck) -> Triggers:
    """Register built-in triggers that keep dependent tables in sync."""
    triggers = Triggers()

    triggers.add_trigger("log", "after_add", lambda entry: _on_log_added(tc, entry))
    triggers.add_trigger(
        "log",
        "after_update",
        lambda old_entry, new_entry: _on_log_updated(tc, old_entry, new_entry),
    )
    triggers.add_trigger("log", "after_delete", lambda entry: _on_log_deleted(tc, entry))

    triggers.add_trigger("tasks", "after_add", lambda entry: _on_task_added(tc, entry))
    triggers.add_trigger("tasks", "after_delete", lambda entry: _on_task_deleted(tc, entry))
    triggers.add_trigger(
        "tasks",
        "after_update",
        lambda old_entry, new_entry: _on_task_updated(tc, old_entry, new_entry),
    )

    triggers.add_trigger(
        "projects",
        "after_update",
        lambda old_entry, new_entry: _on_project_updated(tc, old_entry, new_entry),
    )

    triggers.add_trigger("log", "after_add", lambda entry: _run_alerts(tc, entry))
    triggers.add_trigger(
        "log",
        "after_update",
        lambda old_entry, new_entry: _run_alerts(tc, new_entry),
    )
    triggers.add_trigger("log", "after_delete", lambda entry: _run_alerts(tc, entry))

    return triggers


def _run_alerts(tc: TimeCheck, entry: dict[str, Any]) -> None:
    date = str(entry.get("date", "")).strip() or None
    tc.alerts.run_checks(reference=date)


def _task_chain(tc: TimeCheck, task_name: str) -> tuple[str, str]:
    try:
        task = tc.get("tasks", key=task_name)
    except KeyError:
        return "", ""

    project_name = str(task.get("project", "")).strip()
    if not project_name:
        return "", ""

    try:
        project = tc.get("projects", key=project_name)
    except KeyError:
        return project_name, ""

    return project_name, str(project.get("area", "")).strip()


def _propagate_duration(
    tc: TimeCheck,
    task_name: str,
    duration: str,
    *,
    sign: int = 1,
) -> None:
    if not task_name or not duration:
        return

    project_name = ""
    area_name = ""

    try:
        task = tc.get("tasks", key=task_name)
        new_task_time = apply_duration_delta(task.get("time log", "0:00:00"), duration, sign)
        tc._tables["tasks"].update(key=task_name, **{"time log": new_task_time})
        project_name = str(task.get("project", "")).strip()
    except KeyError:
        return

    if project_name:
        try:
            project = tc.get("projects", key=project_name)
            new_project_time = apply_duration_delta(
                project.get("time log", "0:00:00"), duration, sign
            )
            tc._tables["projects"].update(key=project_name, **{"time log": new_project_time})
            area_name = str(project.get("area", "")).strip()
        except KeyError:
            pass

    if area_name:
        try:
            area = tc.get("areas", key=area_name)
            new_area_time = apply_duration_delta(area.get("time log", "0:00:00"), duration, sign)
            tc._tables["areas"].update(key=area_name, **{"time log": new_area_time})
        except KeyError:
            pass


def _timesheet_areas(tc: TimeCheck) -> list[str]:
    return list(tc.config.get("timesheet_areas") or [])


def _timesheet_row_index(tc: TimeCheck, date: str) -> int | None:
    matches = tc.timesheet.df.index[tc.timesheet.df["Date"].astype(str) == str(date)]
    if len(matches) == 0:
        return None
    return int(matches[0])


def _ensure_timesheet_row(tc: TimeCheck, date: str) -> int:
    row_index = _timesheet_row_index(tc, date)
    if row_index is not None:
        return row_index

    entry: dict[str, str] = {column: "" for column in tc.timesheet.columns}
    entry["Date"] = date
    entry["Day"] = day_of_week(date)
    for area in _timesheet_areas(tc):
        entry[f"{area} time"] = "0:00:00"
    entry["Total Work Hours"] = "0:00:00"
    entry["7-Day Total"] = "0:00:00"
    return tc._tables["timesheet"].add(entry)


def _recalculate_timesheet_totals(tc: TimeCheck, date: str) -> None:
    row_index = _timesheet_row_index(tc, date)
    if row_index is None:
        return

    area_columns = [f"{area} time" for area in _timesheet_areas(tc)]
    daily_total = sum(
        parse_duration(tc.timesheet.df.at[row_index, column])
        for column in area_columns
        if column in tc.timesheet.columns
    )
    tc._tables["timesheet"].update(
        index=row_index,
        **{"Total Work Hours": format_duration_seconds(daily_total)},
    )

    current_date = parse_date(date)
    rolling_total = 0
    for offset in range(7):
        window_date = format_date(current_date - timedelta(days=offset))
        window_index = _timesheet_row_index(tc, window_date)
        if window_index is None:
            continue
        rolling_total += parse_duration(
            tc.timesheet.df.at[window_index, "Total Work Hours"]
        )

    tc._tables["timesheet"].update(
        index=row_index,
        **{"7-Day Total": format_duration_seconds(rolling_total)},
    )


def _update_timesheet_for_log(
    tc: TimeCheck,
    date: str,
    area_name: str,
    duration: str,
    *,
    sign: int = 1,
) -> None:
    if area_name not in _timesheet_areas(tc):
        return

    area_column = f"{area_name} time"
    if area_column not in tc.timesheet.columns:
        return

    row_index = _ensure_timesheet_row(tc, date)
    current = tc.timesheet.df.at[row_index, area_column] or "0:00:00"
    updated = apply_duration_delta(current, duration, sign)
    tc._tables["timesheet"].update(index=row_index, **{area_column: updated})
    _recalculate_timesheet_totals(tc, date)


def _on_log_added(tc: TimeCheck, entry: dict[str, Any]) -> None:
    task_name = str(entry.get("task", "")).strip()
    duration = str(entry.get("total", "0:00:00"))
    date = str(entry.get("date", "")).strip()
    _propagate_duration(tc, task_name, duration, sign=1)
    _, area_name = _task_chain(tc, task_name)
    if date and area_name:
        _update_timesheet_for_log(tc, date, area_name, duration, sign=1)


def _on_log_deleted(tc: TimeCheck, entry: dict[str, Any]) -> None:
    task_name = str(entry.get("task", "")).strip()
    duration = str(entry.get("total", "0:00:00"))
    date = str(entry.get("date", "")).strip()
    _propagate_duration(tc, task_name, duration, sign=-1)
    _, area_name = _task_chain(tc, task_name)
    if date and area_name:
        _update_timesheet_for_log(tc, date, area_name, duration, sign=-1)


def _on_log_updated(tc: TimeCheck, old_entry: dict[str, Any], new_entry: dict[str, Any]) -> None:
    old_duration = str(old_entry.get("total", "0:00:00"))
    new_duration = str(new_entry.get("total", "0:00:00"))
    if old_duration == new_duration:
        return

    delta = subtract_durations(new_duration, old_duration)
    if parse_duration(delta) == 0:
        return

    task_name = str(new_entry.get("task", "")).strip()
    date = str(new_entry.get("date", "")).strip()
    _propagate_duration(tc, task_name, delta, sign=1)
    _, area_name = _task_chain(tc, task_name)
    if date and area_name:
        _update_timesheet_for_log(tc, date, area_name, delta, sign=1)


def _adjust_project_task_count(tc: TimeCheck, project_name: str, delta: int) -> None:
    if not project_name:
        return
    try:
        project = tc.get("projects", key=project_name)
    except KeyError:
        return
    current = int(str(project.get("#tasks", "0") or "0"))
    tc._tables["projects"].update(key=project_name, **{"#tasks": str(max(current + delta, 0))})


def _on_task_added(tc: TimeCheck, entry: dict[str, Any]) -> None:
    _adjust_project_task_count(tc, str(entry.get("project", "")).strip(), 1)


def _on_task_deleted(tc: TimeCheck, entry: dict[str, Any]) -> None:
    _adjust_project_task_count(tc, str(entry.get("project", "")).strip(), -1)


def _on_task_updated(
    tc: TimeCheck,
    old_entry: dict[str, Any],
    new_entry: dict[str, Any],
) -> None:
    old_project = str(old_entry.get("project", "")).strip()
    new_project = str(new_entry.get("project", "")).strip()
    if old_project != new_project:
        _adjust_project_task_count(tc, old_project, -1)
        _adjust_project_task_count(tc, new_project, 1)

    old_time = str(old_entry.get("time log", "0:00:00"))
    new_time = str(new_entry.get("time log", "0:00:00"))
    if old_time == new_time:
        return

    delta = subtract_durations(new_time, old_time)
    if parse_duration(delta) == 0:
        return

    project_name = new_project or old_project
    if not project_name:
        return

    try:
        project = tc.get("projects", key=project_name)
        updated = add_durations(project.get("time log", "0:00:00"), delta)
        tc._tables["projects"].update(key=project_name, **{"time log": updated})
        area_name = str(project.get("area", "")).strip()
        if area_name:
            area = tc.get("areas", key=area_name)
            updated_area = add_durations(area.get("time log", "0:00:00"), delta)
            tc._tables["areas"].update(key=area_name, **{"time log": updated_area})
    except KeyError:
        pass


def _on_project_updated(
    tc: TimeCheck,
    old_entry: dict[str, Any],
    new_entry: dict[str, Any],
) -> None:
    old_time = str(old_entry.get("time log", "0:00:00"))
    new_time = str(new_entry.get("time log", "0:00:00"))
    if old_time == new_time:
        return

    delta = subtract_durations(new_time, old_time)
    if parse_duration(delta) == 0:
        return

    area_name = str(new_entry.get("area", "")).strip() or str(old_entry.get("area", "")).strip()
    if not area_name:
        return

    try:
        area = tc.get("areas", key=area_name)
        updated = add_durations(area.get("time log", "0:00:00"), delta)
        tc._tables["areas"].update(key=area_name, **{"time log": updated})
    except KeyError:
        pass
