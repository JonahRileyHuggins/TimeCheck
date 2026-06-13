"""CRUD wrapper for a single TSV-backed data table."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .file_loader import FileLoader


class DataTable:
    """Load, save, and mutate one tabular sheet. Each table has its own set of trigger properties
    that will be called when any table is modified."""

    def __init__(
        self,
        name: str,
        path: str,
        columns: list[str],
        primary_key: str | None = None,
    ) -> None:
        self.name = name
        self.path = path
        self.columns = list(columns)
        self.primary_key = primary_key
        self._loader = FileLoader(path)
        self._df = self._empty_frame()

    @property
    def df(self) -> pd.DataFrame:
        return self._df

    def _empty_frame(self) -> pd.DataFrame:
        return pd.DataFrame(columns=self.columns)

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return self._empty_frame()

        missing = [column for column in self.columns if column not in df.columns]
        if missing:
            raise ValueError(
                f"{self.name}: file is missing expected columns: {', '.join(missing)}"
            )

        normalized = df[self.columns].copy()
        normalized = normalized.fillna("")
        return normalized.reset_index(drop=True)

    def load(self) -> pd.DataFrame:
        loaded = self._loader.load()
        self._df = self._normalize(loaded)
        return self._df

    def save(self) -> None:
        self._loader.save(self._df)

    def add(self, entry: dict[str, Any]) -> int:
        row = self._coerce_entry(entry)
        self._df = pd.concat([self._df, pd.DataFrame([row])], ignore_index=True)
        return len(self._df) - 1

    def update(
        self,
        index: int | None = None,
        key: str | None = None,
        **fields: Any,
    ) -> int:
        row_index = self._resolve_index(index=index, key=key)
        unknown = set(fields) - set(self.columns)
        if unknown:
            raise ValueError(
                f"{self.name}: unknown columns: {', '.join(sorted(unknown))}"
            )
        for column, value in fields.items():
            self._df.at[row_index, column] = "" if value is None else str(value)
        return row_index

    def delete(self, index: int | None = None, key: str | None = None) -> None:
        row_index = self._resolve_index(index=index, key=key)
        self._df = self._df.drop(row_index).reset_index(drop=True)

    def get(self, index: int | None = None, key: str | None = None) -> dict[str, str]:
        row_index = self._resolve_index(index=index, key=key)
        return self._df.iloc[row_index].to_dict()

    def find(self, **filters: Any) -> pd.DataFrame:
        result = self._df
        for column, value in filters.items():
            if column not in self.columns:
                raise ValueError(f"{self.name}: unknown filter column {column!r}")
            result = result[result[column].astype(str) == str(value)]
        return result.reset_index(drop=True)

    def ensure_file(self) -> None:
        if self._loader.file_path.exists():
            return
        self._df = self._empty_frame()
        self.save()

    def _coerce_entry(self, entry: dict[str, Any]) -> dict[str, str]:
        unknown = set(entry) - set(self.columns)
        if unknown:
            raise ValueError(
                f"{self.name}: unknown columns: {', '.join(sorted(unknown))}"
            )
        return {
            column: "" if entry.get(column) in (None, "") else str(entry[column])
            for column in self.columns
        }

    def _resolve_index(self, index: int | None = None, key: str | None = None) -> int:
        if index is not None:
            if index < 0 or index >= len(self._df):
                raise IndexError(f"{self.name}: index {index} out of range")
            return index

        if key is None:
            raise ValueError(f"{self.name}: provide index or key")

        if not self.primary_key:
            raise ValueError(f"{self.name}: table has no primary key for lookup")

        matches = self._df.index[self._df[self.primary_key].astype(str) == str(key)]
        if len(matches) == 0:
            raise KeyError(f"{self.name}: no row with {self.primary_key}={key!r}")
        if len(matches) > 1:
            raise ValueError(f"{self.name}: multiple rows with {self.primary_key}={key!r}")
        return int(matches[0])
