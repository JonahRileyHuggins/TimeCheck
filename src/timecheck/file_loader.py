"""Load and save JSON, TSV, CSV, and plain-text files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


class DotDict(dict):
    """Dict with attribute access for nested JSON config."""

    def __getattr__(self, attr: str) -> Any:
        val = self.get(attr)
        if isinstance(val, dict):
            return DotDict(val)
        if isinstance(val, list):
            return [DotDict(x) if isinstance(x, dict) else x for x in val]
        return val

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class FileLoader:
    """Dispatch file loading and saving by extension."""

    _HANDLERS = {}

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)
        self._handler = self._get_handler(self.file_path)(self.file_path)

    def load(self, **kwargs: Any) -> Any:
        return self._handler.load(**kwargs)

    def save(self, content: Any, **kwargs: Any) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._handler.save(content, **kwargs)

    @classmethod
    def _get_handler(cls, file_path: Path):
        ext = file_path.suffix.lower()
        handlers = {
            ".json": JsonFile,
            ".csv": CsvFile,
            ".tsv": TsvFile,
            ".txt": TxtFile,
        }
        handler = handlers.get(ext)
        if handler is None:
            raise ValueError(f"Unsupported file type: {ext}")
        return handler


class BaseFile:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def load(self, **kwargs: Any) -> Any:
        raise NotImplementedError

    def save(self, content: Any, **kwargs: Any) -> None:
        raise NotImplementedError


class JsonFile(BaseFile):
    def load(self, **kwargs: Any) -> DotDict:
        with open(self.file_path, encoding="utf-8") as file:
            return DotDict(json.load(file))

    def save(self, content: dict, **kwargs: Any) -> None:
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(content, file, indent=2)
            file.write("\n")


class TsvFile(BaseFile):
    def load(self, **kwargs: Any) -> pd.DataFrame:
        kwargs.setdefault("sep", "\t")
        kwargs.setdefault("dtype", str)
        kwargs.setdefault("keep_default_na", False)
        if not self.file_path.exists():
            return pd.DataFrame()
        return pd.read_csv(self.file_path, **kwargs)

    def save(self, content: pd.DataFrame, **kwargs: Any) -> None:
        kwargs.setdefault("sep", "\t")
        kwargs.setdefault("index", False)
        content.to_csv(self.file_path, **kwargs)


class CsvFile(BaseFile):
    def load(self, **kwargs: Any) -> pd.DataFrame:
        kwargs.setdefault("sep", ",")
        kwargs.setdefault("dtype", str)
        kwargs.setdefault("keep_default_na", False)
        if not self.file_path.exists():
            return pd.DataFrame()
        return pd.read_csv(self.file_path, **kwargs)

    def save(self, content: pd.DataFrame, **kwargs: Any) -> None:
        kwargs.setdefault("sep", ",")
        kwargs.setdefault("index", False)
        content.to_csv(self.file_path, **kwargs)


class TxtFile(BaseFile):
    def load(self, **kwargs: Any) -> str:
        with open(self.file_path, encoding="utf-8") as file:
            return file.read()

    def save(self, content: str, **kwargs: Any) -> None:
        with open(self.file_path, "w", encoding="utf-8") as file:
            file.write(content)
