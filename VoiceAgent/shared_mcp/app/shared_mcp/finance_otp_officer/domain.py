from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .data import LoanOfficer, OfficerDirectory


class DomainError(Exception):
    """Business-rule violation. `code` is a stable machine string."""

    def __init__(self, code: str, **details: Any) -> None:
        super().__init__(code)
        self.code = code
        self.details = details


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SearchAttempt:
    spoken_name: str
    status: str
    match_ids: list[str]
    searched_at: str = field(default_factory=_now)

    def public(self) -> dict[str, Any]:
        return {
            "spoken_name": self.spoken_name,
            "status": self.status,
            "match_ids": list(self.match_ids),
            "searched_at": self.searched_at,
        }


@dataclass
class LoanInterest:
    status: str
    product: str
    requested_amount_usd: int | None
    timeline: str
    spoken_words: str
    accepted_offer: dict[str, Any] | None = None
    notes: str = ""
    recorded_at: str = field(default_factory=_now)

    def public(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "product": self.product,
            "requested_amount_usd": self.requested_amount_usd,
            "timeline": self.timeline,
            "spoken_words": self.spoken_words,
            "accepted_offer": (
                dict(self.accepted_offer) if self.accepted_offer is not None else None
            ),
            "notes": self.notes,
            "recorded_at": self.recorded_at,
        }


@dataclass
class Turn:
    """One entry on the call timeline: a spoken turn, a tool call, or agent trace."""

    ts: str
    role: str  # agent | caller | system
    kind: str  # speech | tool | trace | note
    text: str
    meta: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "role": self.role,
            "kind": self.kind,
            "text": self.text,
            "meta": dict(self.meta),
        }


@dataclass
class CallSession:
    """The authoritative state of one inbound loan-intake call.

    Four gates, in order, and each one is this object's to decide:
      1. `authenticated` — the caller read a valid 8-digit access code.
      2. `loan_interest` — the caller explicitly accepted or declined having
         their borrowing interest recorded.
      3. `confirmed_officer_id` — the caller heard a name plus a title back and
         said yes to it.
      4. `disposition` — the confirmed officer callback request was recorded.

    Nothing may skip a gate: officer search refuses before positive interest,
    and callback disposition refuses before officer confirmation. A prompt
    regression therefore becomes a named tool error instead of a false promise.
    """

    session_id: str
    caller_id: str
    directory_id: str
    routing_persona_ref: str = "finance_sample@1"
    max_otp_attempts: int = 3

    authenticated: bool = False
    authenticated_candidate_id: str | None = None
    authenticated_customer: dict[str, Any] | None = None
    otp_attempts: int = 0
    locked_out: bool = False
    #: Digits heard so far on a code the caller is still reading out. A caller
    #: pausing mid-code produces several utterances, and the model cannot be the
    #: thing that remembers the earlier ones: asked to, it sent only the newest
    #: four every time and looped forever (issues/06). This buffer is the
    #: authoritative partial code, and it is cleared the moment a full eight
    #: digits are checked, however that check turns out.
    otp_digits: str = ""

    current_offer: dict[str, Any] | None = None
    offer_rounds: int = 0
    loan_interest: LoanInterest | None = None
    searches: list[SearchAttempt] = field(default_factory=list)
    last_match_ids: list[str] = field(default_factory=list)
    confirmed_officer_id: str | None = None
    disposition: str | None = None
    ended: bool = False

    turns: list[Turn] = field(default_factory=list)
    state_version: int = 0
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    # ---- internals ----------------------------------------------------
    def _touch(self) -> None:
        self.state_version += 1
        self.updated_at = _now()

    def record_turn(
        self, role: str, kind: str, text: str, meta: dict[str, Any]
    ) -> Turn:
        turn = Turn(ts=_now(), role=role, kind=kind, text=text, meta=meta)
        self.turns.append(turn)
        return turn

    # ---- gate 1: authentication ---------------------------------------
    def accumulate_otp_digits(self, digits: str, required: int = 8) -> str:
        """Add what the caller just said to the code in progress.

        Eight or more digits in one utterance is a whole code re-read, not a
        continuation, so it replaces the buffer rather than extending it.
        """
        if self.authenticated:
            raise DomainError("already_authenticated")
        if self.locked_out:
            raise DomainError("locked_out", otp_attempts=self.otp_attempts)
        self.otp_digits = digits if len(digits) >= required else self.otp_digits + digits
        self._touch()
        return self.otp_digits

    def clear_otp_digits(self) -> None:
        self.otp_digits = ""

    def register_otp_attempt(
        self,
        status: str,
        customer: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.authenticated:
            raise DomainError("already_authenticated")
        if self.locked_out:
            raise DomainError(
                "locked_out", otp_attempts=self.otp_attempts
            )
        authenticated = status in {"verified", "test_verified"}
        if authenticated and customer is None:
            raise DomainError("authenticated_customer_missing")
        self.otp_attempts += 1
        self.clear_otp_digits()
        if authenticated:
            assert customer is not None
            self.authenticated = True
            self.authenticated_candidate_id = str(customer["candidate_id"])
            self.authenticated_customer = dict(customer)
        elif self.otp_attempts >= self.max_otp_attempts:
            self.locked_out = True
        self._touch()
        return {
            "authenticated": self.authenticated,
            "otp_attempts": self.otp_attempts,
            "attempts_remaining": max(
                0, self.max_otp_attempts - self.otp_attempts
            ),
            "locked_out": self.locked_out,
        }

    def require_authenticated(self) -> None:
        if not self.authenticated:
            raise DomainError("authentication_required")

    # ---- gate 2: indicative offer and explicit acceptance ---------------
    def record_offer(self, offer: dict[str, Any]) -> dict[str, Any]:
        self.require_authenticated()
        if self.ended:
            raise DomainError("call_already_ended")
        if self.loan_interest is not None:
            raise DomainError("interest_already_recorded")
        self.current_offer = dict(offer)
        self.offer_rounds += 1
        self._touch()
        return dict(self.current_offer)

    def record_interest(
        self,
        *,
        status: str,
        product: str,
        requested_amount_usd: int | None,
        timeline: str,
        spoken_words: str,
        notes: str,
    ) -> LoanInterest:
        self.require_authenticated()
        if self.ended:
            raise DomainError("call_already_ended")
        if self.loan_interest is not None:
            raise DomainError(
                "interest_already_recorded",
                recorded_interest=self.loan_interest.public(),
            )
        if status == "interested" and self.current_offer is None:
            raise DomainError("loan_offer_required")
        accepted_offer = (
            dict(self.current_offer)
            if status == "interested" and self.current_offer is not None
            else None
        )
        interest = LoanInterest(
            status=status,
            product=product,
            requested_amount_usd=requested_amount_usd,
            timeline=timeline,
            spoken_words=spoken_words,
            accepted_offer=accepted_offer,
            notes=notes,
        )
        self.loan_interest = interest
        self._touch()
        return interest

    def require_positive_interest(self) -> None:
        self.require_authenticated()
        if self.loan_interest is None:
            raise DomainError("loan_interest_required")
        if self.loan_interest.status != "interested":
            raise DomainError("loan_interest_declined")

    # ---- gate 3: the officer the caller asked for ----------------------
    def record_search(self, attempt: SearchAttempt) -> None:
        self.require_positive_interest()
        self.searches.append(attempt)
        self.last_match_ids = list(attempt.match_ids)
        # A new search invalidates whatever was confirmed before it, so a caller
        # who changes their mind cannot be transferred to the earlier officer.
        self.confirmed_officer_id = None
        self._touch()

    def confirm_officer(
        self, directory: OfficerDirectory, officer_id: str
    ) -> LoanOfficer:
        self.require_positive_interest()
        if not self.searches:
            raise DomainError("no_search_yet")
        officer = directory.by_id(officer_id)
        if officer is None:
            raise DomainError("unknown_officer", officer_id=officer_id)
        if officer_id not in self.last_match_ids:
            raise DomainError(
                "officer_not_in_last_search",
                officer_id=officer_id,
                last_match_ids=list(self.last_match_ids),
            )
        self.confirmed_officer_id = officer_id
        self._touch()
        return officer

    def end(self, reason: str) -> dict[str, Any]:
        if self.ended:
            return {
                "ended": True,
                "disposition": self.disposition,
                "idempotent": True,
            }
        self.disposition = reason
        self.ended = True
        self._touch()
        return {"ended": True, "disposition": self.disposition}

    # ---- introspection -------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "caller_id": self.caller_id,
            "directory_id": self.directory_id,
            "authenticated": self.authenticated,
            "authenticated_candidate_id": self.authenticated_candidate_id,
            "customer": (
                dict(self.authenticated_customer)
                if self.authenticated_customer is not None
                else None
            ),
            "otp_attempts": self.otp_attempts,
            "locked_out": self.locked_out,
            "digits_collected": len(self.otp_digits),
            "current_offer": (
                dict(self.current_offer) if self.current_offer is not None else None
            ),
            "offer_rounds": self.offer_rounds,
            "loan_interest": (
                self.loan_interest.public() if self.loan_interest is not None else None
            ),
            "searches": [attempt.public() for attempt in self.searches],
            "last_match_ids": list(self.last_match_ids),
            "confirmed_officer_id": self.confirmed_officer_id,
            "disposition": self.disposition,
            "ended": self.ended,
            "state_version": self.state_version,
        }
