"""Time-spent metrics for tasks, projects, and areas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import pandas as pd

from .duration import format_duration_seconds, parse_date, parse_duration

if TYPE_CHECKING:
    from .timecheck import TimeCheck


@dataclass(frozen=True)
class TimeMetric:
    """Time spent for one task, project, or area."""

    name: str
    seconds: int
    time_log: str
    hours: float
    project: str = ""
    area: str = ""
    status: str = ""
    extra: dict[str, Any] | None = None


def _normalize_range(
    start: datetime | str | None,
    end: datetime | str | None,
) -> tuple[datetime | None, datetime | None]:
    start_dt = parse_date(start) if isinstance(start, str) else start
    end_dt = parse_date(end) if isinstance(end, str) else end
    return start_dt, end_dt


def week_window(reference: datetime | str | None = None) -> tuple[datetime, datetime]:
    """Rolling 7-day window ending on reference date (default: today)."""
    if reference is None:
        end = datetime.now()
    elif isinstance(reference, str):
        end = parse_date(reference)
    else:
        end = reference
    start = end - timedelta(days=6)
    return start, end


def _log_with_hierarchy(tc: TimeCheck) -> pd.DataFrame:
    log_df = tc.log.df.copy()
    if log_df.empty:
        return log_df

    tasks = tc.tasks.df.copy()
    projects = tc.projects.df.copy()
    if tasks.empty:
        log_df["project"] = ""
        log_df["area"] = ""
        log_df["seconds"] = log_df["total"].map(parse_duration)
        return log_df

    task_lookup = tasks.set_index("task", drop=False)
    project_lookup = (
        projects.set_index("project", drop=False) if not projects.empty else pd.DataFrame()
    )

    def resolve_project(task_name: str) -> str:
        if task_name not in task_lookup.index:
            return ""
        return str(task_lookup.at[task_name, "project"]).strip()

    def resolve_area(project_name: str) -> str:
        if not project_name or project_lookup.empty or project_name not in project_lookup.index:
            return ""
        return str(project_lookup.at[project_name, "area"]).strip()

    log_df["project"] = log_df["task"].map(resolve_project)
    log_df["area"] = log_df["project"].map(resolve_area)
    log_df["seconds"] = log_df["total"].map(parse_duration)
    log_df["log_date"] = log_df["date"].map(parse_date)
    return log_df


def _filter_log_range(
    log_df: pd.DataFrame,
    start: datetime | None,
    end: datetime | None,
) -> pd.DataFrame:
    if log_df.empty:
        return log_df
    result = log_df
    if start is not None:
        result = result[result["log_date"] >= start]
    if end is not None:
        result = result[result["log_date"] <= end]
    return result


def _metric_from_seconds(
    name: str,
    seconds: int,
    *,
    project: str = "",
    area: str = "",
    status: str = "",
    extra: dict[str, Any] | None = None,
) -> TimeMetric:
    return TimeMetric(
        name=name,
        seconds=seconds,
        time_log=format_duration_seconds(seconds),
        hours=round(seconds / 3600, 4),
        project=project,
        area=area,
        status=status,
        extra=extra,
    )


class TimeMetrics:
    """Retrieve time-spent metrics from stored totals or log entries."""

    def __init__(self, tc: TimeCheck) -> None:
        self._tc = tc

    def tasks(
        self,
        *,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        project: str | None = None,
        area: str | None = None,
    ) -> list[TimeMetric]:
        start_dt, end_dt = _normalize_range(start, end)
        if start_dt is not None or end_dt is not None:
            return self._tasks_from_log(start_dt, end_dt, project=project, area=area)

        metrics: list[TimeMetric] = []
        for _, row in self._tc.tasks.df.iterrows():
            if project and str(row["project"]).strip() != project:
                continue
            row_area = self._area_for_project(str(row["project"]).strip())
            if area and row_area != area:
                continue
            seconds = parse_duration(str(row.get("time log", "0:00:00")))
            metrics.append(
                _metric_from_seconds(
                    str(row["task"]),
                    seconds,
                    project=str(row["project"]),
                    area=row_area,
                    status=str(row.get("status", "")),
                )
            )
        return sorted(metrics, key=lambda item: item.seconds, reverse=True)

    def projects(
        self,
        *,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        area: str | None = None,
    ) -> list[TimeMetric]:
        start_dt, end_dt = _normalize_range(start, end)
        if start_dt is not None or end_dt is not None:
            return self._projects_from_log(start_dt, end_dt, area=area)

        metrics: list[TimeMetric] = []
        for _, row in self._tc.projects.df.iterrows():
            row_area = str(row.get("area", "")).strip()
            if area and row_area != area:
                continue
            seconds = parse_duration(str(row.get("time log", "0:00:00")))
            metrics.append(
                _metric_from_seconds(
                    str(row["project"]),
                    seconds,
                    area=row_area,
                    status=str(row.get("status", "")),
                    extra={"max weekly hours": str(row.get("max weekly hours", ""))},
                )
            )
        return sorted(metrics, key=lambda item: item.seconds, reverse=True)

    def areas(
        self,
        *,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> list[TimeMetric]:
        start_dt, end_dt = _normalize_range(start, end)
        if start_dt is not None or end_dt is not None:
            return self._areas_from_log(start_dt, end_dt)

        metrics: list[TimeMetric] = []
        for _, row in self._tc.areas.df.iterrows():
            seconds = parse_duration(str(row.get("time log", "0:00:00")))
            metrics.append(
                _metric_from_seconds(
                    str(row["area"]),
                    seconds,
                    extra={
                        "Max Weekly Hours": str(row.get("Max Weekly Hours", "")),
                        "Alert": str(row.get("Alert", "")),
                    },
                )
            )
        return sorted(metrics, key=lambda item: item.seconds, reverse=True)

    def task(
        self,
        name: str,
        *,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> TimeMetric | None:
        matches = [metric for metric in self.tasks(start=start, end=end) if metric.name == name]
        return matches[0] if matches else None

    def project(
        self,
        name: str,
        *,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> TimeMetric | None:
        matches = [
            metric for metric in self.projects(start=start, end=end) if metric.name == name
        ]
        return matches[0] if matches else None

    def area(
        self,
        name: str,
        *,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> TimeMetric | None:
        matches = [metric for metric in self.areas(start=start, end=end) if metric.name == name]
        return matches[0] if matches else None

    def weekly(
        self,
        reference: datetime | str | None = None,
    ) -> dict[str, list[TimeMetric]]:
        """Rolling 7-day totals for tasks, projects, and areas."""
        start, end = week_window(reference)
        return {
            "tasks": self.tasks(start=start, end=end),
            "projects": self.projects(start=start, end=end),
            "areas": self.areas(start=start, end=end),
        }

    def summary(
        self,
        *,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> dict[str, list[TimeMetric]]:
        return {
            "tasks": self.tasks(start=start, end=end),
            "projects": self.projects(start=start, end=end),
            "areas": self.areas(start=start, end=end),
        }

    def _area_for_project(self, project_name: str) -> str:
        if not project_name:
            return ""
        try:
            project = self._tc.get("projects", key=project_name)
        except KeyError:
            return ""
        return str(project.get("area", "")).strip()

    def _tasks_from_log(
        self,
        start: datetime | None,
        end: datetime | None,
        *,
        project: str | None = None,
        area: str | None = None,
    ) -> list[TimeMetric]:
        log_df = _filter_log_range(_log_with_hierarchy(self._tc), start, end)
        if project:
            log_df = log_df[log_df["project"].astype(str) == project]
        if area:
            log_df = log_df[log_df["area"].astype(str) == area]
        if log_df.empty:
            return []

        grouped = log_df.groupby("task", dropna=False)["seconds"].sum()
        status_lookup = {
            str(row["task"]): str(row.get("status", ""))
            for _, row in self._tc.tasks.df.iterrows()
        }
        metrics: list[TimeMetric] = []
        for task_name, seconds in grouped.items():
            task_name = str(task_name)
            project_name = ""
            area_name = ""
            if task_name in self._tc.tasks.df["task"].astype(str).values:
                task = self._tc.get("tasks", key=task_name)
                project_name = str(task.get("project", "")).strip()
                area_name = self._area_for_project(project_name)
            metrics.append(
                _metric_from_seconds(
                    task_name,
                    int(seconds),
                    project=project_name,
                    area=area_name,
                    status=status_lookup.get(task_name, ""),
                )
            )
        return sorted(metrics, key=lambda item: item.seconds, reverse=True)

    def _projects_from_log(
        self,
        start: datetime | None,
        end: datetime | None,
        *,
        area: str | None = None,
    ) -> list[TimeMetric]:
        log_df = _filter_log_range(_log_with_hierarchy(self._tc), start, end)
        if area:
            log_df = log_df[log_df["area"].astype(str) == area]
        if log_df.empty:
            return []

        grouped = log_df.groupby("project", dropna=False)["seconds"].sum()
        metrics: list[TimeMetric] = []
        for project_name, seconds in grouped.items():
            project_name = str(project_name).strip()
            if not project_name:
                continue
            row_area = ""
            status = ""
            max_weekly = ""
            try:
                project = self._tc.get("projects", key=project_name)
                row_area = str(project.get("area", "")).strip()
                status = str(project.get("status", ""))
                max_weekly = str(project.get("max weekly hours", ""))
            except KeyError:
                pass
            metrics.append(
                _metric_from_seconds(
                    project_name,
                    int(seconds),
                    area=row_area,
                    status=status,
                    extra={"max weekly hours": max_weekly},
                )
            )
        return sorted(metrics, key=lambda item: item.seconds, reverse=True)

    def _areas_from_log(
        self,
        start: datetime | None,
        end: datetime | None,
    ) -> list[TimeMetric]:
        log_df = _filter_log_range(_log_with_hierarchy(self._tc), start, end)
        if log_df.empty:
            return []

        grouped = log_df.groupby("area", dropna=False)["seconds"].sum()
        metrics: list[TimeMetric] = []
        for area_name, seconds in grouped.items():
            area_name = str(area_name).strip()
            if not area_name:
                continue
            extra: dict[str, str] = {}
            try:
                area = self._tc.get("areas", key=area_name)
                extra = {
                    "Max Weekly Hours": str(area.get("Max Weekly Hours", "")),
                    "Alert": str(area.get("Alert", "")),
                }
            except KeyError:
                pass
            metrics.append(_metric_from_seconds(area_name, int(seconds), extra=extra))
        return sorted(metrics, key=lambda item: item.seconds, reverse=True)
