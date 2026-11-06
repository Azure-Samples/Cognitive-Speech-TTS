from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .domain import CallEvent, CallSession


def session_to_dict(session: CallSession) -> dict[str, Any]:
    return session.public()


def session_from_dict(document: dict[str, Any]) -> CallSession:
    session = CallSession(
        call_id=str(document["call_id"]),
        lead_id=str(document["lead_id"]),
        campaign_id=str(document["campaign_id"]),
        ivr_menu_id=str(document.get("ivr_menu_id", "corporate_switchboard")),
        agent_persona_ref=str(document.get("agent_persona_ref", "outbound_standard@1")),
    )
    for name in (
        "answered_by",
        "ivr_position",
        "right_party",
        "disclosure_ack",
        "loan_amount_inr",
        "tenure_months",
        "monthly_income_inr",
        "collateral_value_inr",
        "pitched_amount_inr",
        "offer_accepted",
        "offer_note",
        "charges_accepted",
        "bureau_consent",
        "bureau_consent_phrase",
        "selected_officer_id",
        "officer_selection_mode",
        "offer",
        "appointment",
        "callback_at",
        "disposition",
    ):
        setattr(session, name, document.get(name))
    session.dtmf_presses = list(document.get("dtmf_presses", []))
    session.voicemail_left = bool(document.get("voicemail_left", False))
    session.charges_presented = bool(document.get("charges_presented", False))
    session.bureau_consent_unclear_attempts = int(
        document.get("bureau_consent_unclear_attempts", 0)
    )
    session.last_officer_match_ids = list(
        document.get("last_officer_match_ids", [])
    )
    session.transferred = bool(document.get("transferred", False))
    session.state_version = int(document.get("state_version", 0))
    session.created_at = str(document.get("created_at", session.created_at))
    session.updated_at = str(document.get("updated_at", session.updated_at))
    session.events = [
        CallEvent(
            ts=str(item.get("ts", "")),
            kind=str(item.get("kind", "")),
            detail=str(item.get("detail", "")),
            meta=dict(item.get("meta", {}) or {}),
        )
        for item in document.get("events", [])
    ]
    return session


class CallStore:
    """In-memory call store with optional JSON-file persistence.

    `operations` (the idempotency cache) is kept in memory alongside each call so
    replays survive within a process; the persisted file holds business state.
    """

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir
        self._calls: dict[str, CallSession] = {}
        self._operations: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        if state_dir is not None:
            state_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, call_id: str) -> Path | None:
        if self._state_dir is None:
            return None
        return self._state_dir / f"{call_id}.json"

    def create(self, session: CallSession) -> None:
        with self._lock:
            self._calls[session.call_id] = session
            self._operations.setdefault(session.call_id, {})
            self._persist(session)

    def get(self, call_id: str) -> CallSession | None:
        with self._lock:
            if call_id in self._calls:
                return self._calls[call_id]
            path = self._path(call_id)
            if path is not None and path.exists():
                session = session_from_dict(json.loads(path.read_text("utf-8")))
                self._calls[call_id] = session
                self._operations.setdefault(call_id, {})
                return session
            return None

    def save(self, session: CallSession) -> None:
        with self._lock:
            self._calls[session.call_id] = session
            self._persist(session)

    def cached_operation(self, call_id: str, operation_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._operations.get(call_id, {}).get(operation_id)

    def remember_operation(
        self, call_id: str, operation_id: str, result: dict[str, Any]
    ) -> None:
        with self._lock:
            self._operations.setdefault(call_id, {})[operation_id] = result

    def _persist(self, session: CallSession) -> None:
        path = self._path(session.call_id)
        if path is None:
            return
        path.write_text(
            json.dumps(session_to_dict(session), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
