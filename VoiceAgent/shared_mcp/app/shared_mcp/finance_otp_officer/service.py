from __future__ import annotations

import re
import uuid
from typing import Any, Callable, Sequence

from .auth import AUTHENTICATED_STATUSES, OtpService
from .candidates import CandidateDirectory
from .data import DataError, DataStore, OfficerDirectory
from .directory import preload as directory_preload
from .directory import search_candidates as directory_search_candidates
from .domain import CallSession, DomainError, SearchAttempt
from .pricing import (
    ALLOWED_TERMS_MONTHS,
    MAX_LOAN_USD,
    MIN_LOAN_USD,
    price_offer,
    rate_ladder,
)


def _ok(**fields: Any) -> dict[str, Any]:
    result = {"ok": True}
    result.update(fields)
    return result


def _err(code: str, **fields: Any) -> dict[str, Any]:
    result = {"ok": False, "error": code}
    result.update(fields)
    return result


def _is_explicit_interest_decision(outcome: str, spoken_words: str) -> bool:
    words = re.sub(
        r"[^a-z0-9']+",
        " ",
        spoken_words.lower().replace("’", "'"),
    ).strip()
    declined = (
        "i decline",
        "not interested",
        "do not want",
        "don't want",
        "no thank",
        "not right now",
    )
    if outcome == "declined":
        return any(marker in words for marker in declined)
    return not any(marker in words for marker in declined) and bool(
        re.fullmatch(r"i accept(?: the (?:offer|package))?", words)
    )


class RoutingService:
    """Maps MCP tool calls to the call state machine and the officer directory.

    Every business rule — how many code attempts a caller gets, whether a name is
    unambiguous enough to act on, whether a transfer is allowed — lives here and
    in `domain.py`. The MCP server is a thin wrapper and the voice client is not
    in this path at all.
    """

    def __init__(
        self,
        data: DataStore,
        store: "SessionStoreProto",
        max_otp_attempts: int = 3,
        otp_service: OtpService | None = None,
        candidate_directory: CandidateDirectory | None = None,
    ) -> None:
        self._data = data
        self._store = store
        self._max_otp_attempts = max_otp_attempts
        self._create_ops: dict[str, dict[str, Any]] = {}
        self._otp = otp_service or OtpService()
        self._candidates = candidate_directory

    def preload(self, directory_id: str) -> dict[str, Any]:
        """Read the directory and build its phonetic index before the first call.

        Both are cached and immutable, so this is purely about *when* the cost is
        paid: about 0.45s for 20,000 officers, at startup rather than inside the
        first caller's turn, where it would land as a silence on the line.
        """
        try:
            return directory_preload(self._data.load_directory(directory_id))
        except DataError as error:
            return _err("data_error", details=str(error))

    # ---- internal write wrapper ---------------------------------------
    def _write(
        self,
        session_id: str,
        operation_id: str,
        mutate: Callable[[CallSession, OfficerDirectory], dict[str, Any]],
    ) -> dict[str, Any]:
        session = self._store.get(session_id)
        if session is None:
            return _err("unknown_session", session_id=session_id)

        cached = self._store.cached_operation(session_id, operation_id)
        if cached is not None:
            replay = dict(cached)
            replay["idempotent_replay"] = True
            return replay

        try:
            directory = self._data.load_directory(session.directory_id)
            result = mutate(session, directory)
        except DomainError as error:
            return _err(
                error.code, state_version=session.state_version, **error.details
            )
        except DataError as error:
            return _err("data_error", details=str(error))

        self._store.save(session)
        self._store.remember_operation(session_id, operation_id, result)
        return result

    # ---- tools --------------------------------------------------------
    def start_call(
        self,
        caller_id: str,
        directory_id: str,
        operation_id: str,
        routing_persona_ref: str = "finance_sample@1",
    ) -> dict[str, Any]:
        if operation_id in self._create_ops:
            replay = dict(self._create_ops[operation_id])
            replay["idempotent_replay"] = True
            return replay
        try:
            self._data.load_caller(caller_id)
            self._data.load_directory(directory_id)
        except DataError as error:
            return _err("data_error", details=str(error))

        session = CallSession(
            session_id=f"finance-{uuid.uuid4().hex[:12]}",
            caller_id=caller_id,
            directory_id=directory_id,
            routing_persona_ref=routing_persona_ref,
            max_otp_attempts=self._max_otp_attempts,
        )
        self._store.create(session)
        result = _ok(
            session_id=session.session_id,
            state_version=session.state_version,
            authenticated=session.authenticated,
            max_otp_attempts=session.max_otp_attempts,
        )
        self._create_ops[operation_id] = result
        return result

    def verify_caller_otp(
        self, session_id: str, operation_id: str, otp: str
    ) -> dict[str, Any]:
        def mutate(session: CallSession, _: OfficerDirectory) -> dict[str, Any]:
            heard = OtpService.normalize(otp)
            collected = session.accumulate_otp_digits(heard)
            # A short code is a mishearing or a pause, not a wrong code: it must
            # not burn an attempt, or a caller whose "seven" was dropped is
            # locked out for it. The digits stay on the session, so the next
            # utterance continues the same code instead of starting a new one.
            if len(collected) < 8:
                raise DomainError(
                    "access_code_incomplete",
                    digits_heard=len(heard),
                    digits_collected=len(collected),
                    digits_required=8,
                    digits_missing=8 - len(collected),
                    otp_attempts=session.otp_attempts,
                    attempts_remaining=max(
                        0, session.max_otp_attempts - session.otp_attempts
                    ),
                )
            customer = None
            candidate_id = None
            if self._candidates is not None:
                status, candidate_id = self._otp.verify_candidate(
                    collected,
                    self._candidates.default_candidate_id,
                )
                candidate = (
                    self._candidates.by_id(candidate_id)
                    if candidate_id is not None
                    else None
                )
                if candidate is not None:
                    customer = candidate.public()
            else:
                # Backward-compatible fallback for direct service construction.
                status = self._otp.verify(session.caller_id, collected)
                if status in AUTHENTICATED_STATUSES:
                    customer = {
                        "candidate_id": session.caller_id,
                        "full_name": session.caller_id,
                        "fixture": "legacy",
                    }
            if status in AUTHENTICATED_STATUSES and customer is None:
                raise DomainError(
                    "authenticated_customer_not_found",
                    candidate_id=candidate_id,
                )
            outcome = session.register_otp_attempt(status, customer)
            if status not in AUTHENTICATED_STATUSES:
                raise DomainError("access_code_invalid", status=status, **outcome)
            return _ok(
                status=status,
                caller_id=session.caller_id,
                customer=customer,
                state_version=session.state_version,
                **outcome,
            )

        result = self._write(session_id, operation_id, mutate)
        result.setdefault("session_id", session_id)
        return result

    def start_and_verify_caller_otp(
        self,
        caller_id: str,
        directory_id: str,
        operation_id: str,
        otp: str,
        routing_persona_ref: str = "finance_sample@1",
    ) -> dict[str, Any]:
        """Create the call state as part of the caller's first OTP check."""
        started = self.start_call(
            caller_id,
            directory_id,
            f"{operation_id}:start",
            routing_persona_ref,
        )
        if not started.get("ok"):
            return started
        return self.verify_caller_otp(
            str(started["session_id"]),
            operation_id,
            otp,
        )

    def record_loan_interest(
        self,
        session_id: str,
        operation_id: str,
        outcome: str,
        product: str,
        requested_amount_usd: Any,
        timeline: str,
        spoken_words: str,
        notes: str = "",
    ) -> dict[str, Any]:
        allowed_outcomes = {"interested", "declined"}
        allowed_products = {
            "home_purchase",
            "refinance",
            "home_equity",
            "investment_property",
            "other",
            "unspecified",
        }
        allowed_timelines = {
            "immediately",
            "within_3_months",
            "within_6_months",
            "more_than_6_months",
            "researching",
            "unspecified",
        }

        def mutate(session: CallSession, _: OfficerDirectory) -> dict[str, Any]:
            session.require_authenticated()
            if outcome not in allowed_outcomes:
                raise DomainError(
                    "unknown_interest_outcome",
                    outcome=outcome,
                    allowed=sorted(allowed_outcomes),
                )
            if product not in allowed_products:
                raise DomainError(
                    "unknown_loan_product",
                    product=product,
                    allowed=sorted(allowed_products),
                )
            if timeline not in allowed_timelines:
                raise DomainError(
                    "unknown_loan_timeline",
                    timeline=timeline,
                    allowed=sorted(allowed_timelines),
                )
            amount: int | None = None
            if requested_amount_usd is not None:
                if isinstance(requested_amount_usd, bool):
                    raise DomainError(
                        "loan_amount_invalid", requested_amount_usd=requested_amount_usd
                    )
                try:
                    amount = int(requested_amount_usd)
                except (TypeError, ValueError) as error:
                    raise DomainError(
                        "loan_amount_invalid",
                        requested_amount_usd=requested_amount_usd,
                    ) from error
                if amount <= 0 or amount > 100_000_000:
                    raise DomainError(
                        "loan_amount_out_of_range",
                        requested_amount_usd=amount,
                    )
            if not spoken_words.strip() or not _is_explicit_interest_decision(
                outcome, spoken_words
            ):
                raise DomainError(
                    (
                        "offer_acceptance_not_explicit"
                        if outcome == "interested"
                        else "interest_decision_not_explicit"
                    ),
                    outcome=outcome,
                )
            if outcome == "interested":
                if session.current_offer is None:
                    raise DomainError("loan_offer_required")
                offer_amount = int(session.current_offer["amount_usd"])
                if amount is not None and amount != offer_amount:
                    raise DomainError(
                        "offer_amount_mismatch",
                        requested_amount_usd=amount,
                        offered_amount_usd=offer_amount,
                    )
                amount = offer_amount
            interest = session.record_interest(
                status=outcome,
                product=product,
                requested_amount_usd=amount,
                timeline=timeline,
                spoken_words=spoken_words.strip(),
                notes=notes.strip(),
            )
            return _ok(
                interest=interest.public(),
                accepted_offer=interest.accepted_offer,
                proceed_to_officer=outcome == "interested",
                state_version=session.state_version,
            )

        return self._write(session_id, operation_id, mutate)

    def calculate_loan_offer(
        self,
        session_id: str,
        operation_id: str,
        amount_usd: Any,
        term_months: Any = 360,
        requested_rate_percent: Any = None,
    ) -> dict[str, Any]:
        def mutate(session: CallSession, _: OfficerDirectory) -> dict[str, Any]:
            session.require_authenticated()
            if isinstance(term_months, bool):
                raise DomainError("loan_term_invalid", term_months=term_months)
            try:
                term = int(term_months)
            except (TypeError, ValueError) as error:
                raise DomainError(
                    "loan_term_invalid", term_months=term_months
                ) from error
            if term not in ALLOWED_TERMS_MONTHS:
                raise DomainError(
                    "loan_term_not_offered",
                    term_months=term,
                    allowed_terms_months=list(ALLOWED_TERMS_MONTHS),
                )

            requested_rate: float | None = None
            if requested_rate_percent is not None:
                if isinstance(requested_rate_percent, bool):
                    raise DomainError(
                        "requested_rate_invalid",
                        requested_rate_percent=requested_rate_percent,
                    )
                try:
                    requested_rate = round(float(requested_rate_percent), 2)
                except (TypeError, ValueError) as error:
                    raise DomainError(
                        "requested_rate_invalid",
                        requested_rate_percent=requested_rate_percent,
                    ) from error
                if not 1.0 <= requested_rate <= 25.0:
                    raise DomainError(
                        "requested_rate_out_of_range",
                        requested_rate_percent=requested_rate,
                    )

            customer = session.authenticated_customer or {}
            credit_tier = str(customer.get("credit_tier", "unknown")).lower()
            try:
                indicative_max = int(customer["indicative_max_loan_usd"])
            except (KeyError, TypeError, ValueError) as error:
                raise DomainError("customer_pricing_profile_missing") from error
            if amount_usd is None:
                amount = min(indicative_max, MAX_LOAN_USD)
            else:
                if isinstance(amount_usd, bool):
                    raise DomainError("loan_amount_invalid", amount_usd=amount_usd)
                try:
                    amount = int(amount_usd)
                except (TypeError, ValueError) as error:
                    raise DomainError(
                        "loan_amount_invalid", amount_usd=amount_usd
                    ) from error
            if not MIN_LOAN_USD <= amount <= MAX_LOAN_USD:
                raise DomainError(
                    "loan_amount_out_of_range",
                    amount_usd=amount,
                    min_amount_usd=MIN_LOAN_USD,
                    max_amount_usd=MAX_LOAN_USD,
                )

            current = session.current_offer or {}
            same_terms = (
                current.get("amount_usd") == amount
                and current.get("term_months") == term
            )
            current_rate = (
                float(current["annual_rate_percent"])
                if same_terms and current.get("annual_rate_percent") is not None
                else None
            )
            offer = price_offer(
                amount_usd=amount,
                term_months=term,
                credit_tier=credit_tier,
                indicative_max_loan_usd=indicative_max,
                requested_rate_percent=requested_rate,
                current_rate_percent=current_rate,
            ).public()
            session.record_offer(offer)

            if requested_rate is None:
                negotiation_status = "starting_offer"
            elif offer["at_best_available"] and requested_rate < float(
                offer["annual_rate_percent"]
            ):
                negotiation_status = "best_available"
            else:
                negotiation_status = "counter_applied"
            return _ok(
                offer=offer,
                rate_ladder=rate_ladder(credit_tier, term),
                negotiation={
                    "status": negotiation_status,
                    "can_reduce_further": offer["can_reduce_further"],
                    "at_best_available": offer["at_best_available"],
                    "customer_explanation": (
                        "The indicative rate uses the verified credit tier, one "
                        "of three loan-amount bands, and the repayment-term band."
                    ),
                    "floor_is_internal": True,
                },
                allowed_terms_months=list(ALLOWED_TERMS_MONTHS),
                indicative_max_loan_usd=indicative_max,
                offer_rounds=session.offer_rounds,
                state_version=session.state_version,
            )

        return self._write(session_id, operation_id, mutate)

    def auto_assign_loan_officer(
        self, session_id: str, operation_id: str
    ) -> dict[str, Any]:
        def mutate(
            session: CallSession, directory: OfficerDirectory
        ) -> dict[str, Any]:
            session.require_positive_interest()
            available = sorted(
                (
                    officer
                    for officer in directory.officers
                    if officer.status == "available"
                ),
                key=lambda officer: officer.officer_id,
            )
            if not available:
                raise DomainError("no_available_officer")
            index = sum(ord(char) for char in session.session_id) % len(available)
            officer = available[index]
            session.record_search(
                SearchAttempt(
                    spoken_name="[auto-assigned]",
                    status="one_match",
                    match_ids=[officer.officer_id],
                )
            )
            return _ok(
                assignment="automatic",
                officer=officer.public(),
                state_version=session.state_version,
            )

        return self._write(session_id, operation_id, mutate)

    def search_loan_officer(
        self,
        session_id: str,
        operation_id: str,
        spoken_name: str,
        also_heard: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        def mutate(
            session: CallSession, directory: OfficerDirectory
        ) -> dict[str, Any]:
            session.require_authenticated()
            outcome = directory_search_candidates(
                directory, [spoken_name, *(also_heard or ())]
            )
            attempt = SearchAttempt(
                spoken_name=spoken_name,
                status=outcome["status"],
                match_ids=[match["officer_id"] for match in outcome["matches"]],
            )
            session.record_search(attempt)
            return _ok(
                status=outcome["status"],
                query=outcome["query"],
                queries=outcome.get("queries", []),
                normalized_query=outcome["normalized_query"],
                matches=outcome["matches"],
                match_count=len(outcome["matches"]),
                reason=outcome.get("reason"),
                search_attempts=len(session.searches),
                state_version=session.state_version,
            )

        return self._write(session_id, operation_id, mutate)

    def confirm_loan_officer(
        self, session_id: str, operation_id: str, officer_id: str
    ) -> dict[str, Any]:
        def mutate(
            session: CallSession, directory: OfficerDirectory
        ) -> dict[str, Any]:
            officer = session.confirm_officer(directory, officer_id)
            return _ok(
                confirmed=True,
                officer=officer.public(),
                state_version=session.state_version,
            )

        return self._write(session_id, operation_id, mutate)

    def end_call(
        self, session_id: str, operation_id: str, reason: str
    ) -> dict[str, Any]:
        allowed = {
            "caller_hung_up",
            "authentication_failed",
            "officer_not_found",
            "caller_declined",
            "officer_callback_requested",
            "other",
        }
        if reason not in allowed:
            return _err("unknown_reason", reason=reason, allowed=sorted(allowed))

        def mutate(
            session: CallSession, directory: OfficerDirectory
        ) -> dict[str, Any]:
            callback: dict[str, Any] | None = None
            if (
                reason == "officer_callback_requested"
                and session.confirmed_officer_id is None
            ):
                raise DomainError("officer_not_confirmed")
            if reason == "officer_callback_requested":
                if (
                    session.loan_interest is None
                    or session.loan_interest.accepted_offer is None
                ):
                    raise DomainError("accepted_offer_required")
                officer = directory.by_id(str(session.confirmed_officer_id))
                if officer is None:
                    raise DomainError(
                        "unknown_officer",
                        officer_id=session.confirmed_officer_id,
                    )
                callback = {
                    "officer": officer.public(),
                    "accepted_offer": dict(
                        session.loan_interest.accepted_offer
                    ),
                }
            outcome = session.end(reason)
            return _ok(
                state_version=session.state_version,
                callback=callback,
                **outcome,
            )

        result = self._write(session_id, operation_id, mutate)
        result.setdefault("session_id", session_id)
        return result

    def start_and_end_call(
        self,
        caller_id: str,
        directory_id: str,
        operation_id: str,
        reason: str,
        routing_persona_ref: str = "finance_sample@1",
    ) -> dict[str, Any]:
        """Persist a pre-authentication ending without a separate start tool."""
        started = self.start_call(
            caller_id,
            directory_id,
            f"{operation_id}:start",
            routing_persona_ref,
        )
        if not started.get("ok"):
            return started
        return self.end_call(
            str(started["session_id"]),
            operation_id,
            reason,
        )

    def get_call_state(self, session_id: str) -> dict[str, Any]:
        session = self._store.get(session_id)
        if session is None:
            return _err("unknown_session", session_id=session_id)
        return _ok(state=session.snapshot())

    # ---- admin (not exposed to the voice agent) ------------------------
    def issue_caller_otp(self, caller_id: str) -> dict[str, Any]:
        try:
            self._data.load_caller(caller_id)
        except DataError:
            return _err("unknown_caller", caller_id=caller_id)
        return _ok(caller_id=caller_id, **self._otp.issue(caller_id))

    def append_turn(
        self,
        session_id: str,
        role: str,
        kind: str,
        text: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = self._store.get(session_id)
        if session is None:
            return _err("unknown_session", session_id=session_id)
        turn = session.record_turn(role, kind, text, meta or {})
        self._store.save(session)
        return _ok(turn_count=len(session.turns), ts=turn.ts)


# Minimal structural protocol so service.py needs no store import cycle.
class SessionStoreProto:  # pragma: no cover - typing helper
    def get(self, session_id: str) -> CallSession | None: ...
    def create(self, session: CallSession) -> None: ...
    def save(self, session: CallSession) -> None: ...
    def cached_operation(
        self, session_id: str, operation_id: str
    ) -> dict[str, Any] | None: ...
    def remember_operation(
        self, session_id: str, operation_id: str, result: dict[str, Any]
    ) -> None: ...
