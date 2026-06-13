"""Duration parsing and formatting for H:MM:SS time values."""

from __future__ import annotations

from datetime import datetime, timedelta


def parse_duration(value: str) -> int:
    """Parse a duration string (H:MM:SS or H:MM:SS) into total seconds."""
    text = str(value or "0:00:00").strip()
    if not text:
        return 0

    parts = text.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = (int(part or 0) for part in parts)
        return hours * 3600 + minutes * 60 + seconds
    if len(parts) == 2:
        hours, minutes = (int(part or 0) for part in parts)
        return hours * 3600 + minutes * 60
    return int(parts[0] or 0) * 3600


def format_duration_seconds(seconds: int) -> str:
    """Format seconds as H:MM:SS."""
    seconds = max(int(seconds), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def add_durations(*values: str) -> str:
    total = sum(parse_duration(value) for value in values)
    return format_duration_seconds(total)


def subtract_durations(minuend: str, subtrahend: str) -> str:
    return format_duration_seconds(parse_duration(minuend) - parse_duration(subtrahend))


def apply_duration_delta(base: str, delta: str, sign: int = 1) -> str:
    if sign >= 0:
        return add_durations(base, delta)
    return subtract_durations(base, delta)


def parse_date(value: str) -> datetime:
    return datetime.strptime(str(value).strip(), "%m/%d/%Y")


def format_date(value: datetime) -> str:
    return f"{value.month}/{value.day}/{value.year}"


def day_of_week(value: str) -> str:
    return parse_date(value).strftime("%A")


def parse_hours_threshold(value: str) -> float:
    """Parse an hour limit stored as H:MM:SS, a whole number, or decimal hours."""
    text = str(value or "").strip()
    if not text:
        return 0.0
    if ":" in text:
        return parse_duration(text) / 3600.0
    return float(text)


def duration_to_hours(value: str) -> float:
    return parse_duration(value) / 3600.0
