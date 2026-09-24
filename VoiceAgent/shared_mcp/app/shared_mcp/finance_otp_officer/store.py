from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .domain import CallSession, LoanInterest, SearchAttempt, Turn


def session_to_dict(session: CallSession) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "caller_id": session.caller_id,
        "directory_id": session.directory_id,
        "routing_persona_ref": session.routing_persona_ref,
        "max_otp_attempts": session.max_otp_attempts,
        "authenticated": session.authenticated,
        "authenticated_candidate_id": session.authenticated_candidate_id,
        "authenticated_customer": session.authenticated_customer,
        "otp_attempts": session.otp_attempts,
        "locked_out": session.locked_out,
        "otp_digits": session.otp_digits,
        "current_offer": session.current_offer,
        "offer_rounds": session.offer_rounds,
        "loan_interest": (
            session.loan_interest.public() if session.loan_interest is not None else None
        ),
        "searches": [attempt.public() for attempt in session.searches],
        "last_match_ids": list(session.last_match_ids),
        "confirmed_officer_id": session.confirmed_officer_id,
        "disposition": session.disposition,
        "ended": session.ended,
        "turns": [turn.public() for turn in session.turns],
        "state_version": session.state_version,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def session_from_dict(document: dict[str, Any]) -> CallSession:
    session = CallSession(
        session_id=str(document["session_id"]),
        caller_id=str(document["caller_id"]),
        directory_id=str(document["directory_id"]),
        routing_persona_ref=str(
            document.get("routing_persona_ref", "finance_sample@1")
        ),
        max_otp_attempts=max(1, int(document.get("max_otp_attempts", 3))),
        authenticated=bool(document.get("authenticated", False)),
        authenticated_candidate_id=document.get("authenticated_candidate_id"),
        authenticated_customer=(
            dict(document["authenticated_customer"])
            if isinstance(document.get("authenticated_customer"), dict)
            else None
        ),
        otp_attempts=int(document.get("otp_attempts", 0)),
        locked_out=bool(document.get("locked_out", False)),
        otp_digits=str(document.get("otp_digits", "")),
        current_offer=(
            dict(document["current_offer"])
            if isinstance(document.get("current_offer"), dict)
            else None
        ),
        offer_rounds=int(document.get("offer_rounds", 0)),
        loan_interest=(
            LoanInterest(
                status=str(document["loan_interest"].get("status", "")),
                product=str(document["loan_interest"].get("product", "unspecified")),
                requested_amount_usd=document["loan_interest"].get(
                    "requested_amount_usd"
                ),
                timeline=str(
                    document["loan_interest"].get("timeline", "unspecified")
                ),
                spoken_words=str(
                    document["loan_interest"].get("spoken_words", "")
                ),
                accepted_offer=(
                    dict(document["loan_interest"]["accepted_offer"])
                    if isinstance(
                        document["loan_interest"].get("accepted_offer"), dict
                    )
                    else None
                ),
                notes=str(document["loan_interest"].get("notes", "")),
                **(
                    {"recorded_at": str(document["loan_interest"]["recorded_at"])}
                    if document["loan_interest"].get("recorded_at")
                    else {}
                ),
            )
            if isinstance(document.get("loan_interest"), dict)
            else None
        ),
        last_match_ids=list(document.get("last_match_ids", [])),
        confirmed_officer_id=document.get("confirmed_officer_id"),
        disposition=document.get("disposition"),
        ended=bool(document.get("ended", False)),
        state_version=int(document.get("state_version", 0)),
    )
    session.created_at = str(document.get("created_at", session.created_at))
    session.updated_at = str(document.get("updated_at", session.updated_at))
    session.searches = [
        SearchAttempt(
            spoken_name=str(item.get("spoken_name", "")),
            status=str(item.get("status", "")),
            match_ids=list(item.get("match_ids", [])),
            **(
                {"searched_at": str(item["searched_at"])}
                if item.get("searched_at")
                else {}
            ),
        )
        for item in document.get("searches", [])
    ]
    session.turns = [
        Turn(
            ts=str(item.get("ts", "")),
            role=str(item.get("role", "")),
            kind=str(item.get("kind", "")),
            text=str(item.get("text", "")),
            meta=dict(item.get("meta", {}) or {}),
        )
        for item in document.get("turns", [])
    ]
    return session


class SessionStore:
    """In-memory call store with optional JSON-file persistence.

    `operations` (idempotency cache) is kept in memory alongside each session so
    replays survive within a process; the persisted file holds business state.
    """

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir
        self._sessions: dict[str, CallSession] = {}
        self._operations: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        if state_dir is not None:
            state_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path | None:
        if self._state_dir is None:
            return None
        return self._state_dir / f"{session_id}.json"

    def create(self, session: CallSession) -> None:
        with self._lock:
            self._sessions[session.session_id] = session
            self._operations.setdefault(session.session_id, {})
            self._persist(session)

    def get(self, session_id: str) -> CallSession | None:
        with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]
            path = self._path(session_id)
            if path is not None and path.exists():
                session = session_from_dict(json.loads(path.read_text("utf-8")))
                self._sessions[session_id] = session
                self._operations.setdefault(session_id, {})
                return session
            return None

    def save(self, session: CallSession) -> None:
        with self._lock:
            self._sessions[session.session_id] = session
            self._persist(session)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            existed = self._sessions.pop(session_id, None) is not None
            self._operations.pop(session_id, None)
            path = self._path(session_id)
            if path is not None and path.exists():
                path.unlink()
                existed = True
            return existed

    def cached_operation(
        self, session_id: str, operation_id: str
    ) -> dict[str, Any] | None:
        with self._lock:
            return self._operations.get(session_id, {}).get(operation_id)

    def remember_operation(
        self, session_id: str, operation_id: str, result: dict[str, Any]
    ) -> None:
        with self._lock:
            self._operations.setdefault(session_id, {})[operation_id] = result

    def _persist(self, session: CallSession) -> None:
        path = self._path(session.session_id)
        if path is None:
            return
        path.write_text(
            json.dumps(session_to_dict(session), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
