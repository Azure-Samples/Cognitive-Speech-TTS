"""The authoritative state of one outbound call.

Everything the agent decides lands here and nowhere else. The client holds none
of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


DISPOSITIONS = (
    "qualified_lead",
    "transferred",
    "callback_scheduled",
    "not_interested",
    "wrong_party",
    "voicemail_left",
    "ivr_unreachable",
    "customer_ended",
    "ineligible",
    "no_disclosure_consent",
    "amount_rejected",
    "terms_rejected",
    "charges_rejected",
    "no_bureau_consent",
    "bureau_consent_not_obtained",
    "appointment_not_booked",
)

# Stage 5 is the compliance floor of the call: a bureau pull needs consent that
# would stand up in an audit. These short acknowledgements, fillers, and bare
# polarities do not name the action and therefore are not consent or refusal.
AMBIGUOUS_CONSENT_PHRASES = (
    "hmm",
    "hm",
    "mmm",
    "hen",
    "huh",
    "uh huh",
    "uh",
    "um",
    "ah",
    "oh",
    "yes",
    "yeah",
    "no",
    "ji",
    "haan",
    "han",
    "ok",
    "okay",
    "acha",
    "achha",
    "keep going",
    "please continue",
    "one second",
    "one sec",
    "hold on",
    "wait",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class CallEvent:
    ts: str
    kind: str
    detail: str
    meta: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "kind": self.kind,
            "detail": self.detail,
            "meta": dict(self.meta),
        }


@dataclass
class CallSession:
    call_id: str
    lead_id: str
    campaign_id: str
    ivr_menu_id: str
    agent_persona_ref: str = "outbound_standard@1"

    answered_by: str | None = None
    ivr_position: str | None = None
    dtmf_presses: list[str] = field(default_factory=list)
    voicemail_left: bool = False

    right_party: bool | None = None
    disclosure_ack: bool | None = None

    # The figures a quote is priced from. They are working values, not a form:
    # every one of them can be re-sent, and the last quote is what counts.
    loan_amount_inr: int | None = None
    tenure_months: int | None = None
    monthly_income_inr: int | None = None
    collateral_value_inr: int | None = None

    # Funnel state, in the order the customer reaches it.
    pitched_amount_inr: int | None = None
    offer_accepted: bool | None = None
    offer_note: str = ""
    charges_presented: bool = False
    charges_accepted: bool | None = None
    bureau_consent: bool | None = None
    bureau_consent_phrase: str = ""
    bureau_consent_unclear_attempts: int = 0
    last_officer_match_ids: list[str] = field(default_factory=list)
    selected_officer_id: str = ""
    officer_selection_mode: str = ""

    offer: dict[str, Any] | None = None
    appointment: dict[str, Any] | None = None
    eligibility_checked: bool = False
    transferred: bool = False
    callback_at: str | None = None
    disposition: str | None = None

    state_version: int = 0
    events: list[CallEvent] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    # The figures the offer stage exists to collect, in the order the agent
    # should ask for them.
    QUALIFICATION_SLOTS = (
        "tenure_months",
        "monthly_income_inr",
        "collateral_value_inr",
    )

    def touch(self, kind: str, detail: str, **meta: Any) -> None:
        self.state_version += 1
        self.updated_at = _now()
        self.events.append(CallEvent(ts=self.updated_at, kind=kind, detail=detail, meta=meta))

    @property
    def is_qualified_lead(self) -> bool:
        """The customer's own definition: they accepted a quote that was actually
        given to them. One answer to one offer, not a set of booleans that can
        disagree with each other."""
        return self.offer_accepted is True

    @property
    def closed(self) -> bool:
        return self.disposition is not None

    def public(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "lead_id": self.lead_id,
            "campaign_id": self.campaign_id,
            "answered_by": self.answered_by,
            "ivr_position": self.ivr_position,
            "dtmf_presses": list(self.dtmf_presses),
            "voicemail_left": self.voicemail_left,
            "right_party": self.right_party,
            "disclosure_ack": self.disclosure_ack,
            "loan_amount_inr": self.loan_amount_inr,
            "tenure_months": self.tenure_months,
            "monthly_income_inr": self.monthly_income_inr,
            "collateral_value_inr": self.collateral_value_inr,
            "pitched_amount_inr": self.pitched_amount_inr,
            "offer_accepted": self.offer_accepted,
            "offer_note": self.offer_note,
            "charges_presented": self.charges_presented,
            "charges_accepted": self.charges_accepted,
            "bureau_consent": self.bureau_consent,
            "bureau_consent_phrase": self.bureau_consent_phrase,
            "bureau_consent_unclear_attempts": self.bureau_consent_unclear_attempts,
            "last_officer_match_ids": list(self.last_officer_match_ids),
            "selected_officer_id": self.selected_officer_id,
            "officer_selection_mode": self.officer_selection_mode,
            "qualified_lead": self.is_qualified_lead,
            "offer": self.offer,
            "appointment": self.appointment,
            "transferred": self.transferred,
            "callback_at": self.callback_at,
            "disposition": self.disposition,
            "state_version": self.state_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "events": [event.public() for event in self.events],
        }
