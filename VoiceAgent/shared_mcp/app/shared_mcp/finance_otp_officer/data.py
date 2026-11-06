from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DataError(Exception):
    """Raised when a fixture is missing or malformed."""


@dataclass(frozen=True)
class LoanOfficer:
    officer_id: str
    full_name: str
    title: str
    branch: str
    nmls_id: str
    extension: str
    status: str
    aliases: tuple[str, ...]

    @property
    def first_name(self) -> str:
        return self.full_name.split()[0] if self.full_name.split() else ""

    @property
    def last_name(self) -> str:
        parts = self.full_name.split()
        return parts[-1] if parts else ""

    def public(self) -> dict[str, Any]:
        """What the agent may say out loud: name, title, branch. Never the extension."""
        return {
            "officer_id": self.officer_id,
            "full_name": self.full_name,
            "title": self.title,
            "branch": self.branch,
            "status": self.status,
        }


@dataclass(frozen=True)
class OfficerDirectory:
    directory_id: str
    officers: tuple[LoanOfficer, ...]

    def by_id(self, officer_id: str) -> LoanOfficer | None:
        for officer in self.officers:
            if officer.officer_id == officer_id:
                return officer
        return None


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise DataError(f"fixture_not_found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise DataError(f"invalid_json: {path}: {error}") from error


class DataStore:
    """Loads the immutable loan-officer directory and caller fixtures from disk.

    The directory is cached after the first read. It is immutable and it is read
    on every tool call, so without the cache a 20,000-row file is re-read and
    re-parsed for each one — and the phonetic index keyed on it would be rebuilt
    with it, which is the difference between a 100ms search and a 550ms one.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._directories: dict[str, OfficerDirectory] = {}

    def load_directory(self, directory_id: str) -> OfficerDirectory:
        cached = self._directories.get(directory_id)
        if cached is not None:
            return cached
        document = _read_json(self._data_dir / f"{directory_id}.json")
        if not isinstance(document, dict):
            raise DataError("directory_must_be_object")
        raw = document.get("officers")
        if not isinstance(raw, list) or not raw:
            raise DataError("directory_requires_officers")

        officers: list[LoanOfficer] = []
        for item in raw:
            if not isinstance(item, dict):
                raise DataError("officer_must_be_object")
            missing = [
                key
                for key in ("officer_id", "full_name", "title")
                if not item.get(key)
            ]
            if missing:
                raise DataError(f"officer_missing_fields: {missing}")
            officers.append(
                LoanOfficer(
                    officer_id=str(item["officer_id"]),
                    full_name=str(item["full_name"]),
                    title=str(item["title"]),
                    branch=str(item.get("branch", "")),
                    nmls_id=str(item.get("nmls_id", "")),
                    extension=str(item.get("extension", "")),
                    status=str(item.get("status", "available")),
                    aliases=tuple(str(alias) for alias in item.get("aliases", [])),
                )
            )

        ids = [officer.officer_id for officer in officers]
        if len(ids) != len(set(ids)):
            raise DataError("officer_ids_must_be_unique")

        directory = OfficerDirectory(
            directory_id=str(document.get("directory_id", directory_id)),
            officers=tuple(officers),
        )
        self._directories[directory_id] = directory
        return directory

    def load_caller(self, caller_id: str) -> dict[str, Any]:
        document = _read_json(self._data_dir / "callers.json")
        if not isinstance(document, dict):
            raise DataError("callers_must_be_object")
        for item in document.get("callers", []):
            if isinstance(item, dict) and item.get("caller_id") == caller_id:
                return item
        raise DataError(f"unknown_caller: {caller_id}")
