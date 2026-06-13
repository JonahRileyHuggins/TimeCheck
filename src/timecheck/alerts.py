"""Threshold alerts for weekly hour limits on areas and projects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Callable

from .duration import parse_hours_threshold
from .metrics import TimeMetrics, week_window

if TYPE_CHECKING:
    from .timecheck import TimeCheck

AlertHandler = Callable[["Alert"], None]


@dataclass(frozen=True)
class Alert:
    """A threshold alert for an area or project."""

    level: str
    kind: str
    entity_type: str
    entity: str
    message: str
    current_hours: float
    threshold_hours: float
    percent_of_threshold: float


def _alert_enabled(value: str) -> bool:
    return str(value or "").strip().upper() in {"TRUE", "YES", "1"}


class AlertManager:
    """Evaluate hour thresholds and dispatch alert callbacks."""

    def __init__(self, tc: TimeCheck) -> None:
        self._tc = tc
        self._metrics = TimeMetrics(tc)
        self._handlers: list[AlertHandler] = []
        self._warn_ratio = 0.9

    @property
    def handlers(self) -> list[AlertHandler]:
        return list(self._handlers)

    def add_handler(self, handler: AlertHandler) -> None:
        self._handlers.append(handler)

    def remove_handler(self, handler: AlertHandler) -> None:
        self._handlers.remove(handler)

    def clear_handlers(self) -> None:
        self._handlers.clear()

    def check(
        self,
        *,
        reference: datetime | str | None = None,
        include_projects: bool = True,
        include_areas: bool = True,
    ) -> list[Alert]:
        alerts: list[Alert] = []
        start, end = week_window(reference)
        weekly_areas = {
            metric.name: metric.hours
            for metric in self._metrics.areas(start=start, end=end)
        }
        weekly_projects = {
            metric.name: metric.hours
            for metric in self._metrics.projects(start=start, end=end)
        }

        if include_areas:
            alerts.extend(self._check_areas(weekly_areas))
        if include_projects:
            alerts.extend(self._check_projects(weekly_projects))

        return sorted(alerts, key=lambda alert: (alert.level != "critical", -alert.percent_of_threshold))

    def run_checks(
        self,
        *,
        reference: datetime | str | None = None,
        include_projects: bool = True,
        include_areas: bool = True,
    ) -> list[Alert]:
        alerts = self.check(
            reference=reference,
            include_projects=include_projects,
            include_areas=include_areas,
        )
        for alert in alerts:
            for handler in self._handlers:
                handler(alert)
        return alerts

    def _check_areas(self, weekly_hours: dict[str, float]) -> list[Alert]:
        alerts: list[Alert] = []
        for _, row in self._tc.areas.df.iterrows():
            area_name = str(row["area"]).strip()
            if not area_name or not _alert_enabled(str(row.get("Alert", ""))):
                continue

            threshold = parse_hours_threshold(str(row.get("Max Weekly Hours", "")))
            if threshold <= 0:
                continue

            current = weekly_hours.get(area_name, 0.0)
            alerts.extend(self._threshold_alerts("area", area_name, current, threshold))
        return alerts

    def _check_projects(self, weekly_hours: dict[str, float]) -> list[Alert]:
        alerts: list[Alert] = []
        for _, row in self._tc.projects.df.iterrows():
            project_name = str(row["project"]).strip()
            if not project_name:
                continue

            threshold = parse_hours_threshold(str(row.get("max weekly hours", "")))
            if threshold <= 0:
                continue

            current = weekly_hours.get(project_name, 0.0)
            alerts.extend(self._threshold_alerts("project", project_name, current, threshold))
        return alerts

    def _threshold_alerts(
        self,
        entity_type: str,
        entity_name: str,
        current_hours: float,
        threshold_hours: float,
    ) -> list[Alert]:
        if threshold_hours <= 0:
            return []

        percent = (current_hours / threshold_hours) * 100
        alerts: list[Alert] = []

        if current_hours >= threshold_hours:
            alerts.append(
                Alert(
                    level="critical",
                    kind="max_weekly_hours",
                    entity_type=entity_type,
                    entity=entity_name,
                    message=(
                        f"{entity_name} exceeded the weekly limit: "
                        f"{current_hours:.2f}h / {threshold_hours:.2f}h"
                    ),
                    current_hours=current_hours,
                    threshold_hours=threshold_hours,
                    percent_of_threshold=percent,
                )
            )
        elif current_hours >= threshold_hours * self._warn_ratio:
            alerts.append(
                Alert(
                    level="warning",
                    kind="max_weekly_hours",
                    entity_type=entity_type,
                    entity=entity_name,
                    message=(
                        f"{entity_name} is approaching the weekly limit: "
                        f"{current_hours:.2f}h / {threshold_hours:.2f}h"
                    ),
                    current_hours=current_hours,
                    threshold_hours=threshold_hours,
                    percent_of_threshold=percent,
                )
            )
        return alerts
