"""Local profile registry mapping user names to data directories."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .registry import DATA_ROOT


def local_registry_dir() -> Path:
    """Return the fixed local directory that stores profile path mappings."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "TimeCheck"
    return Path.home() / ".timecheck"


def registry_path() -> Path:
    return local_registry_dir() / "profiles.json"


def _load_registry() -> dict[str, str]:
    path = registry_path()
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid profile registry format in {path}")
    return {str(name): str(value) for name, value in data.items()}


def _save_registry(registry: dict[str, str]) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(registry, file, indent=2, sort_keys=True)
        file.write("\n")


def _normalize_path(data_root: str | Path) -> Path:
    return Path(data_root).expanduser().resolve()


def get_profile_path(name: str) -> Path | None:
    """Return the registered data directory for a user, if one exists."""
    key = str(name).strip()
    if not key:
        return None
    path = _load_registry().get(key)
    if not path:
        return None
    return Path(path)


def set_profile_path(name: str, data_root: str | Path) -> Path:
    """Register or update the data directory for a user."""
    key = str(name).strip()
    if not key:
        raise ValueError("Profile name cannot be empty")

    resolved = _normalize_path(data_root)
    registry = _load_registry()
    registry[key] = str(resolved)
    _save_registry(registry)
    return resolved


def remove_profile(name: str) -> None:
    """Remove a user's registered data directory mapping."""
    key = str(name).strip()
    if not key:
        raise ValueError("Profile name cannot be empty")
    registry = _load_registry()
    registry.pop(key, None)
    _save_registry(registry)


def list_profiles() -> dict[str, str]:
    """Return all registered user-to-path mappings."""
    return dict(_load_registry())


def resolve_data_root(
    *,
    name: str | None = None,
    data_root: str | Path | None = None,
) -> Path:
    """Resolve which data directory to open for the given inputs."""
    if data_root is not None:
        return _normalize_path(data_root)

    if name:
        registered = get_profile_path(name)
        if registered is not None:
            return registered

    return DATA_ROOT.resolve()
