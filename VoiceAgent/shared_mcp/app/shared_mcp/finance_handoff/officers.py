"""Fictional officer catalog using the shared sample's fake name search."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Sequence

from ..finance_otp_officer.data import DataStore as OfficerDataStore
from ..finance_otp_officer.data import LoanOfficer
from ..finance_otp_officer.directory import preload, search_candidates


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OFFICER_DATA_DIR = ROOT / "data" / "finance_otp_officer"


def resolve_officer_data_dir(
    environment: dict[str, str],
    module_file: Path | None = None,
) -> Path:
    del module_file
    configured = environment.get("FINANCE_OFFICER_DATA_DIR")
    return Path(configured) if configured else DEFAULT_OFFICER_DATA_DIR


class OfficerCatalog:
    """Small immutable fictional directory for search and assignment."""

    def __init__(self, data_dir: Path, directory_id: str) -> None:
        self._directory = OfficerDataStore(data_dir).load_directory(directory_id)
        preload(self._directory)

    @classmethod
    def from_environment(
        cls,
        environment: dict[str, str] | None = None,
    ) -> "OfficerCatalog":
        values = dict(os.environ if environment is None else environment)
        return cls(
            resolve_officer_data_dir(values),
            values.get(
                "FINANCE_OFFICER_DIRECTORY_ID",
                "loan_officers",
            ).strip(),
        )

    def search(
        self,
        spoken_name: str,
        also_heard: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        return search_candidates(
            self._directory,
            [spoken_name, *(also_heard or ())],
        )

    def by_id(self, officer_id: str) -> LoanOfficer | None:
        return self._directory.by_id(officer_id)

    def auto_assign(self, call_id: str) -> LoanOfficer | None:
        available = [
            officer
            for officer in self._directory.officers
            if officer.status == "available"
        ]
        if not available:
            return None
        digest = hashlib.sha256(call_id.encode("utf-8")).digest()
        return available[int.from_bytes(digest[:8], "big") % len(available)]

