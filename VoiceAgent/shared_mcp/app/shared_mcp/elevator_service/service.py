from __future__ import annotations

import copy
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable

from .store import CallStore
from .tickets import ZendeskBackend


IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
SAFETY_FIELDS = (
    "entrapment_or_egress",
    "injury_or_medical",
    "fire_heat_or_smoke",
    "flooding_or_electrical_hazard",
    "unsafe_elevator_movement",
)
SAFETY_STATES = {"unknown", "clear", "present", "cannot_confirm"}
SAFETY_PRIORITY = {
    "unknown": 0,
    "clear": 1,
    "cannot_confirm": 2,
    "present": 3,
}
SAFETY_PROMPTS = {
    "entrapment_or_egress": (
        "check_entrapment",
        "First, is anyone trapped or unable to exit safely?",
    ),
    "injury_or_medical": (
        "check_injury",
        "Is anyone injured or in need of medical help?",
    ),
    "fire_heat_or_smoke": (
        "check_fire",
        "Is there any fire, unusual heat, or smoke?",
    ),
    "flooding_or_electrical_hazard": (
        "check_flood_or_electrical",
        "Is there flooding or an electrical hazard?",
    ),
    "unsafe_elevator_movement": (
        "check_unsafe_movement",
        "One last safety check: is the elevator moving unexpectedly or unsafely?",
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _clean(value: str, minimum: int, maximum: int) -> str:
    normalized = " ".join(value.split())
    if not minimum <= len(normalized) <= maximum:
        raise ValueError("invalid_text")
    return normalized


class ElevatorService:
    def __init__(
        self,
        store: CallStore,
        tickets: ZendeskBackend,
        token_secret: str | bytes,
    ) -> None:
        secret = (
            token_secret.encode("utf-8")
            if isinstance(token_secret, str)
            else token_secret
        )
        if len(secret) < 16:
            raise ValueError("elevator call-token secret must be at least 16 bytes")
        self._store = store
        self._tickets = tickets
        self._secret = secret

    def _token(self, call_id: str) -> str:
        return hmac.new(
            self._secret,
            f"elevator-service:{call_id}".encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _fingerprint(name: str, payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            {"name": name, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _validate_identifier(value: str) -> str:
        normalized = value.strip()
        if IDENTIFIER.fullmatch(normalized) is None:
            raise ValueError("invalid_identifier")
        return normalized

    @staticmethod
    def _result(
        state: dict[str, Any] | None,
        ok: bool,
        reason: str,
        **fields: Any,
    ) -> dict[str, Any]:
        return {
            "ok": ok,
            "reason_code": reason,
            "call_id": state.get("call_id", "") if state else "",
            "next_node": state.get("next_node", "") if state else "",
            **fields,
        }

    def start_service_call(
        self,
        call_id: str,
        command_id: str,
        caller_ref: str = "",
    ) -> dict[str, Any]:
        try:
            call_id = self._validate_identifier(call_id)
            command_id = self._validate_identifier(command_id)
        except ValueError:
            return self._result(None, False, "invalid_identifier")
        payload = {"caller_ref": caller_ref}
        fingerprint = self._fingerprint("start_service_call", payload)
        with self._store.locked(call_id) as slot:
            if slot.state is not None:
                cached = slot.state["operations"].get(command_id)
                if cached and cached["fingerprint"] == fingerprint:
                    return {
                        **copy.deepcopy(cached["result"]),
                        "call_token": self._token(call_id),
                    }
                return self._result(
                    slot.state,
                    False,
                    "call_already_started",
                )
            state = {
                "call_id": call_id,
                "call_token_hash": hashlib.sha256(
                    self._token(call_id).encode()
                ).hexdigest(),
                "caller_ref": caller_ref.strip(),
                "lifecycle": "active",
                "next_node": "intent_router",
                "active_issue": None,
                "handoff": None,
                "operations": {},
                "created_at": _now(),
                "updated_at": _now(),
            }
            result = self._result(
                state,
                True,
                "call_started",
                caller_known=bool(caller_ref.strip()),
            )
            state["operations"][command_id] = {
                "fingerprint": fingerprint,
                "result": copy.deepcopy(result),
            }
            slot.state = state
            return {**result, "call_token": self._token(call_id)}

    def _execute(
        self,
        *,
        call_id: str,
        call_token: str,
        command_id: str,
        name: str,
        payload: dict[str, Any],
        handler: Callable[[dict[str, Any]], dict[str, Any]],
        allow_terminal: bool = False,
    ) -> dict[str, Any]:
        try:
            call_id = self._validate_identifier(call_id)
            command_id = self._validate_identifier(command_id)
        except ValueError:
            return self._result(None, False, "invalid_identifier")
        fingerprint = self._fingerprint(name, payload)
        with self._store.locked(call_id) as slot:
            state = slot.state
            if state is None or not hmac.compare_digest(
                hashlib.sha256(call_token.encode()).hexdigest(),
                str(state.get("call_token_hash", "")),
            ):
                return self._result(state, False, "invalid_call_token")
            cached = state["operations"].get(command_id)
            if cached:
                if cached["fingerprint"] == fingerprint:
                    return copy.deepcopy(cached["result"])
                return self._result(
                    state,
                    False,
                    "command_id_payload_conflict",
                )
            if state["lifecycle"] != "active" and not allow_terminal:
                return self._result(state, False, "call_not_active")
            try:
                fields = handler(state)
                ok = bool(fields.pop("ok", True))
                reason = str(fields.pop("reason_code", f"{name}_completed"))
            except ValueError as error:
                ok = False
                reason = str(error)
                fields = {}
            state["updated_at"] = _now()
            result = self._result(state, ok, reason, **fields)
            state["operations"][command_id] = {
                "fingerprint": fingerprint,
                "result": copy.deepcopy(result),
            }
            return result

    def record_issue(
        self,
        call_id: str,
        call_token: str,
        command_id: str,
        issue_summary: str,
        source_turn_id: str = "",
    ) -> dict[str, Any]:
        payload = {
            "issue_summary": issue_summary,
            "source_turn_id": source_turn_id,
        }

        def handler(state: dict[str, Any]) -> dict[str, Any]:
            summary = _clean(issue_summary, 8, 500)
            prior = state.get("active_issue")
            if prior and {
                "present",
                "cannot_confirm",
            } & set(prior["safety"].values()):
                raise ValueError("safety_handoff_required")
            revision = int(prior.get("revision", 0)) + 1 if prior else 1
            handle = str(prior.get("handle")) if prior else "issue-1"
            state["active_issue"] = {
                "handle": handle,
                "revision": revision,
                "summary": summary,
                "safety": {name: "unknown" for name in SAFETY_FIELDS},
                "ticket": None,
            }
            state["next_node"] = "report_issue"
            return {
                "reason_code": "issue_recorded",
                "issue_handle": handle,
                "issue_revision": revision,
            }

        return self._execute(
            call_id=call_id,
            call_token=call_token,
            command_id=command_id,
            name="record_issue",
            payload=payload,
            handler=handler,
        )

    def assess_safety(
        self,
        call_id: str,
        call_token: str,
        command_id: str,
        issue_handle: str,
        issue_revision: int,
        assessments: dict[str, str],
        source_turn_id: str = "",
    ) -> dict[str, Any]:
        payload = {
            "issue_handle": issue_handle,
            "issue_revision": issue_revision,
            "assessments": assessments,
            "source_turn_id": source_turn_id,
        }

        def handler(state: dict[str, Any]) -> dict[str, Any]:
            issue = state.get("active_issue")
            if (
                not issue
                or issue["handle"] != issue_handle
                or issue["revision"] != issue_revision
            ):
                raise ValueError("stale_issue")
            if set(assessments) != set(SAFETY_FIELDS):
                raise ValueError("invalid_safety_schema")
            for field, value in assessments.items():
                if value not in SAFETY_STATES:
                    raise ValueError("invalid_safety_state")
                if (
                    SAFETY_PRIORITY[value]
                    > SAFETY_PRIORITY[issue["safety"][field]]
                ):
                    issue["safety"][field] = value
            statuses = dict(issue["safety"])
            if "present" in statuses.values():
                state["next_node"] = "human_handoff"
                return {
                    "reason_code": "safety_risk_present",
                    "action": "handoff",
                    "handoff_reason": "emergency",
                    "safety_status": "present",
                    "statuses": statuses,
                    "human_handling_required": True,
                }
            if "cannot_confirm" in statuses.values():
                state["next_node"] = "human_handoff"
                return {
                    "reason_code": "safety_unresolved",
                    "action": "handoff",
                    "handoff_reason": "safety_unresolved",
                    "safety_status": "unknown",
                    "statuses": statuses,
                    "human_handling_required": True,
                }
            for field in SAFETY_FIELDS:
                if statuses[field] == "unknown":
                    action, prompt = SAFETY_PROMPTS[field]
                    state["next_node"] = "report_issue"
                    return {
                        "reason_code": "safety_question_required",
                        "action": action,
                        "spoken_prompt": prompt,
                        "safety_status": "unknown",
                        "statuses": statuses,
                    }
            state["next_node"] = "report_issue"
            return {
                "reason_code": "safety_clear",
                "action": "clear",
                "safety_status": "clear",
                "statuses": statuses,
            }

        return self._execute(
            call_id=call_id,
            call_token=call_token,
            command_id=command_id,
            name="assess_safety",
            payload=payload,
            handler=handler,
        )

    def mock_zendesk_create_ticket(
        self,
        call_id: str,
        call_token: str,
        command_id: str,
        issue_handle: str,
        issue_revision: int,
        address: str,
        postal_code: str,
        caller_confirmed: bool,
    ) -> dict[str, Any]:
        payload = {
            "issue_handle": issue_handle,
            "issue_revision": issue_revision,
            "address": address,
            "postal_code": postal_code,
            "caller_confirmed": caller_confirmed,
        }

        def handler(state: dict[str, Any]) -> dict[str, Any]:
            issue = state.get("active_issue")
            if (
                not issue
                or issue["handle"] != issue_handle
                or issue["revision"] != issue_revision
            ):
                raise ValueError("stale_issue")
            if set(issue["safety"].values()) != {"clear"}:
                raise ValueError("safety_clearance_required")
            if caller_confirmed is not True:
                raise ValueError("caller_confirmation_required")
            normalized_address = _clean(address, 3, 300)
            normalized_postal = _clean(postal_code, 3, 20)
            ticket = self._tickets.create(
                f"{call_id}-{issue_handle}-{issue_revision}",
                issue["summary"],
                normalized_address,
                normalized_postal,
            )
            issue["ticket"] = ticket
            state["next_node"] = "next_request"
            return {
                "reason_code": "ticket_created",
                "ticket_id": ticket["ticket_id"],
                "command": "handoff_to_next_request",
            }

        return self._execute(
            call_id=call_id,
            call_token=call_token,
            command_id=command_id,
            name="mock_zendesk_create_ticket",
            payload=payload,
            handler=handler,
        )

    def mock_zendesk_get_ticket_status(
        self,
        call_id: str,
        call_token: str,
        command_id: str,
        issue_id: str,
    ) -> dict[str, Any]:
        payload = {"issue_id": issue_id}

        def handler(state: dict[str, Any]) -> dict[str, Any]:
            normalized = _clean(issue_id, 1, 100)
            ticket = self._tickets.get(normalized)
            if ticket is None:
                state["next_node"] = "human_handoff"
                return {
                    "reason_code": "ticket_not_found",
                    "action": "handoff",
                    "handoff_reason": "status_unresolved",
                    "human_handling_required": True,
                    "spoken_message": (
                        "I could not find that fictional Zendesk ticket. "
                        "I will record a request for human assistance."
                    ),
                }
            state["next_node"] = "next_request"
            return {
                "reason_code": "status_found",
                "action": "status_returned",
                "ticket": {
                    "ticket_id": ticket["ticket_id"],
                    "status": ticket["status"],
                    "estimated_visit": ticket["estimated_visit"],
                },
                "spoken_message": (
                    f"Ticket {ticket['ticket_id']} is {ticket['status']}."
                ),
            }

        return self._execute(
            call_id=call_id,
            call_token=call_token,
            command_id=command_id,
            name="mock_zendesk_get_ticket_status",
            payload=payload,
            handler=handler,
        )

    def request_human_handoff(
        self,
        call_id: str,
        call_token: str,
        command_id: str,
        reason: str,
    ) -> dict[str, Any]:
        payload = {"reason": reason}
        allowed = {
            "emergency",
            "caller_requested",
            "out_of_scope",
            "address_unresolved",
            "status_unresolved",
            "safety_unresolved",
            "technical_failure",
        }

        def handler(state: dict[str, Any]) -> dict[str, Any]:
            if reason not in allowed:
                raise ValueError("invalid_handoff_reason")
            handoff = state.get("handoff")
            if handoff is None:
                handoff = {
                    "handoff_id": hashlib.sha256(
                        call_id.encode()
                    ).hexdigest()[:12].upper(),
                    "status": "requested",
                    "reason": reason,
                }
                state["handoff"] = handoff
            state["next_node"] = "human_finalize"
            return {
                "reason_code": "handoff_requested",
                "action": "handoff_recorded",
                "handoff": handoff,
                "spoken_message": (
                    "A human follow-up has been requested. "
                    "This browser demo does not perform a telephone transfer."
                ),
            }

        return self._execute(
            call_id=call_id,
            call_token=call_token,
            command_id=command_id,
            name="request_human_handoff",
            payload=payload,
            handler=handler,
            allow_terminal=True,
        )

    def end_service_call(
        self,
        call_id: str,
        call_token: str,
        command_id: str,
    ) -> dict[str, Any]:
        def handler(state: dict[str, Any]) -> dict[str, Any]:
            state["lifecycle"] = "ended"
            state["next_node"] = "end"
            return {
                "reason_code": "call_ended",
                "lifecycle": "ended",
            }

        return self._execute(
            call_id=call_id,
            call_token=call_token,
            command_id=command_id,
            name="end_service_call",
            payload={},
            handler=handler,
            allow_terminal=True,
        )

    def get_call_state(
        self,
        call_id: str,
        call_token: str,
    ) -> dict[str, Any]:
        try:
            call_id = self._validate_identifier(call_id)
        except ValueError:
            return self._result(None, False, "invalid_identifier")
        with self._store.locked(call_id) as slot:
            state = slot.state
            if state is None or not hmac.compare_digest(
                hashlib.sha256(call_token.encode()).hexdigest(),
                str(state.get("call_token_hash", "")),
            ):
                return self._result(state, False, "invalid_call_token")
            public = copy.deepcopy(state)
            public.pop("call_token_hash", None)
            public.pop("operations", None)
            return self._result(
                state,
                True,
                "state_returned",
                state=public,
            )
