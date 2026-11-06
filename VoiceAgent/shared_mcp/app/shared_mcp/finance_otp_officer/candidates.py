"""Validated fictional customer profiles bound to UI-issued OTPs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .data import DataError


@dataclass(frozen=True)
class CandidateProfile:
    candidate_id: str
    full_name: str
    date_of_birth: str
    credit_tier: str
    credit_score_band: str
    annual_income_usd: int
    debt_to_income_ratio: float
    indicative_max_loan_usd: int
    customer_since: str
    state: str

    def public(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "full_name": self.full_name,
            "date_of_birth": self.date_of_birth,
            "credit_tier": self.credit_tier,
            "credit_score_band": self.credit_score_band,
            "annual_income_usd": self.annual_income_usd,
            "debt_to_income_ratio": self.debt_to_income_ratio,
            "indicative_max_loan_usd": self.indicative_max_loan_usd,
            "customer_since": self.customer_since,
            "state": self.state,
            "fixture": "fictional",
        }

    def summary(self) -> dict[str, str]:
        return {
            "candidate_id": self.candidate_id,
            "full_name": self.full_name,
            "credit_tier": self.credit_tier,
        }


class CandidateDirectory:
    """Immutable, validated profiles used by both the admin UI and MCP pack."""

    def __init__(
        self,
        candidates: tuple[CandidateProfile, ...],
        default_candidate_id: str,
    ) -> None:
        self._by_id = {candidate.candidate_id: candidate for candidate in candidates}
        if len(self._by_id) != len(candidates):
            raise DataError("candidate_ids_must_be_unique")
        if default_candidate_id not in self._by_id:
            raise DataError(f"unknown_default_candidate: {default_candidate_id}")
        self.default_candidate_id = default_candidate_id

    @classmethod
    def load(cls, path: Path) -> "CandidateDirectory":
        if not path.exists():
            raise DataError(f"fixture_not_found: {path}")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise DataError(f"invalid_json: {path}: {error}") from error
        if not isinstance(document, dict) or document.get("fixture") != "fictional":
            raise DataError("candidate_fixture_must_be_fictional")
        raw_candidates = document.get("candidates")
        if not isinstance(raw_candidates, list) or not raw_candidates:
            raise DataError("candidate_fixture_requires_candidates")

        candidates: list[CandidateProfile] = []
        for item in raw_candidates:
            if not isinstance(item, dict):
                raise DataError("candidate_must_be_object")
            required = (
                "candidate_id",
                "full_name",
                "date_of_birth",
                "credit_tier",
                "credit_score_band",
                "annual_income_usd",
                "debt_to_income_ratio",
                "indicative_max_loan_usd",
                "customer_since",
                "state",
            )
            missing = [key for key in required if item.get(key) in (None, "")]
            if missing:
                raise DataError(f"candidate_missing_fields: {missing}")
            try:
                date.fromisoformat(str(item["date_of_birth"]))
                date.fromisoformat(str(item["customer_since"]))
                annual_income = int(item["annual_income_usd"])
                dti = float(item["debt_to_income_ratio"])
                max_loan = int(item["indicative_max_loan_usd"])
            except (TypeError, ValueError) as error:
                raise DataError(
                    f"candidate_invalid_financial_profile: {item.get('candidate_id', '?')}"
                ) from error
            if annual_income <= 0 or max_loan <= 0 or not 0 <= dti <= 1:
                raise DataError(
                    f"candidate_invalid_financial_profile: {item['candidate_id']}"
                )
            candidates.append(
                CandidateProfile(
                    candidate_id=str(item["candidate_id"]),
                    full_name=str(item["full_name"]),
                    date_of_birth=str(item["date_of_birth"]),
                    credit_tier=str(item["credit_tier"]),
                    credit_score_band=str(item["credit_score_band"]),
                    annual_income_usd=annual_income,
                    debt_to_income_ratio=dti,
                    indicative_max_loan_usd=max_loan,
                    customer_since=str(item["customer_since"]),
                    state=str(item["state"]),
                )
            )
        return cls(
            tuple(candidates),
            str(document.get("default_candidate_id", "")),
        )

    def by_id(self, candidate_id: str) -> CandidateProfile | None:
        return self._by_id.get(candidate_id)

    def summaries(self) -> list[dict[str, str]]:
        return [candidate.summary() for candidate in self._by_id.values()]

    def profiles(self) -> list[dict[str, Any]]:
        return [candidate.public() for candidate in self._by_id.values()]

    def __len__(self) -> int:
        return len(self._by_id)
