"""Immutable fixtures: the lead being called, the campaign being run, and the
phone menu the agent may have to get through."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DataError(Exception):
    """Raised when a fixture is missing or malformed."""


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    product_name: str
    min_amount_inr: int
    max_amount_inr: int
    allowed_tenures_months: tuple[int, ...]
    default_tenure_months: int
    annual_rate_percent: float
    # Share of monthly income that may go to this instalment.
    max_foir: float
    min_monthly_income_inr: int
    processing_fee_percent: float = 0.0
    insurance_premium_inr: int = 0
    # Stage 3 policy. The agent may never move the rate itself; when a customer
    # will not accept it, the only sanctioned moves are a different tenure or a
    # human. The floor exists so pricing authority can be modelled at all, and is
    # never disclosed to the customer.
    rate_negotiable: bool = False
    internal_floor_rate_percent: float = 0.0
    # Risk-based pricing, largest-first: (up_to_amount_inr, annual_rate_percent).
    # Lending further above the pre-approved figure costs more, so the rate is a
    # function of the amount rather than one constant. Empty falls back to
    # annual_rate_percent.
    rate_tiers: tuple[tuple[int, float], ...] = ()

    def rate_for_amount(self, amount_inr: int) -> float:
        """The rate this campaign prices `amount_inr` at."""
        for ceiling, rate in self.rate_tiers:
            if amount_inr <= ceiling:
                return rate
        if self.rate_tiers:
            return self.rate_tiers[-1][1]
        return self.annual_rate_percent

    def tenure_is_offered(self, months: int) -> bool:
        return months in self.allowed_tenures_months

    def processing_fee_inr(self, amount_inr: int) -> int:
        return round(amount_inr * self.processing_fee_percent / 100.0)


@dataclass(frozen=True)
class Lead:
    lead_id: str
    first_name: str
    full_name: str
    phone: str
    language: str
    relationship: str
    preapproved_limit_inr: int
    date_of_birth: str

    def public(self) -> dict[str, Any]:
        # date_of_birth is deliberately absent: it is the answer to the identity
        # question, so the agent must never be handed it.
        return {
            "lead_id": self.lead_id,
            "first_name": self.first_name,
            "language": self.language,
            "relationship": self.relationship,
        }


@dataclass(frozen=True)
class IvrOption:
    digits: str
    label: str
    goes_to: str


@dataclass(frozen=True)
class IvrNode:
    node_id: str
    prompt: str
    options: tuple[IvrOption, ...]

    def option_for(self, digits: str) -> IvrOption | None:
        for option in self.options:
            if option.digits == digits:
                return option
        return None


@dataclass(frozen=True)
class IvrMenu:
    menu_id: str
    entry_node_id: str
    nodes: dict[str, IvrNode]
    # Node ids that mean the call has left the menu.
    human_node_id: str
    voicemail_node_id: str

    def node(self, node_id: str) -> IvrNode | None:
        return self.nodes.get(node_id)


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise DataError(f"fixture_not_found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise DataError(f"invalid_json: {path}: {error}") from error


class DataStore:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def load_lead(self, lead_id: str) -> Lead:
        document = _read_json(self._data_dir / "leads" / f"{lead_id}.json")
        if not isinstance(document, dict):
            raise DataError("lead_must_be_object")
        missing = [
            key
            for key in (
                "first_name",
                "full_name",
                "phone",
                "preapproved_limit_inr",
                "date_of_birth",
            )
            if key not in document
        ]
        if missing:
            raise DataError(f"lead_missing_fields: {missing}")
        return Lead(
            lead_id=str(document.get("lead_id", lead_id)),
            first_name=str(document["first_name"]),
            full_name=str(document["full_name"]),
            phone=str(document["phone"]),
            language=str(document.get("language", "en-IN")),
            relationship=str(document.get("relationship", "existing customer")),
            preapproved_limit_inr=int(document["preapproved_limit_inr"]),
            date_of_birth=str(document["date_of_birth"]),
        )

    def load_campaign(self, campaign_id: str) -> Campaign:
        document = _read_json(self._data_dir / "campaigns" / f"{campaign_id}.json")
        if not isinstance(document, dict):
            raise DataError("campaign_must_be_object")
        tenures = document.get("allowed_tenures_months")
        if not isinstance(tenures, list) or not tenures:
            raise DataError("campaign_requires_allowed_tenures_months")
        parsed_tenures = tuple(int(value) for value in tenures)
        default_tenure = int(document.get("default_tenure_months", parsed_tenures[0]))
        if default_tenure not in parsed_tenures:
            raise DataError("campaign_default_tenure_must_be_offered")
        return Campaign(
            campaign_id=str(document.get("campaign_id", campaign_id)),
            product_name=str(document.get("product_name", "personal loan")),
            min_amount_inr=int(document["min_amount_inr"]),
            max_amount_inr=int(document["max_amount_inr"]),
            allowed_tenures_months=parsed_tenures,
            default_tenure_months=default_tenure,
            annual_rate_percent=float(document.get("annual_rate_percent", 14.0)),
            max_foir=float(document.get("max_foir", 0.5)),
            min_monthly_income_inr=int(document.get("min_monthly_income_inr", 20000)),
            processing_fee_percent=float(document.get("processing_fee_percent", 0.0)),
            insurance_premium_inr=int(document.get("insurance_premium_inr", 0)),
            rate_negotiable=bool(document.get("rate_negotiable", False)),
            internal_floor_rate_percent=float(
                document.get("internal_floor_rate_percent", 0.0)
            ),
            rate_tiers=tuple(
                (int(tier["up_to_amount_inr"]), float(tier["annual_rate_percent"]))
                for tier in sorted(
                    document.get("rate_tiers") or [],
                    key=lambda tier: int(tier["up_to_amount_inr"]),
                )
            ),
        )

    def load_ivr_menu(self, menu_id: str) -> IvrMenu:
        document = _read_json(self._data_dir / "ivr_menus" / f"{menu_id}.json")
        if not isinstance(document, dict):
            raise DataError("ivr_menu_must_be_object")
        raw_nodes = document.get("nodes")
        if not isinstance(raw_nodes, dict) or not raw_nodes:
            raise DataError("ivr_menu_requires_nodes")
        nodes: dict[str, IvrNode] = {}
        for node_id, raw in raw_nodes.items():
            if not isinstance(raw, dict):
                raise DataError(f"ivr_node_must_be_object: {node_id}")
            options = tuple(
                IvrOption(
                    digits=str(option["digits"]),
                    label=str(option.get("label", "")),
                    goes_to=str(option["goes_to"]),
                )
                for option in raw.get("options", [])
                if isinstance(option, dict)
            )
            nodes[str(node_id)] = IvrNode(
                node_id=str(node_id),
                prompt=str(raw.get("prompt", "")),
                options=options,
            )
        return IvrMenu(
            menu_id=str(document.get("menu_id", menu_id)),
            entry_node_id=str(document["entry_node_id"]),
            nodes=nodes,
            human_node_id=str(document.get("human_node_id", "agent_queue")),
            voicemail_node_id=str(document.get("voicemail_node_id", "voicemail")),
        )
