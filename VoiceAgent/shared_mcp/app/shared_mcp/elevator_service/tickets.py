from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


class ZendeskBackend(Protocol):
    def create(
        self,
        business_key: str,
        summary: str,
        address: str,
        postal_code: str,
    ) -> dict[str, str]: ...

    def get(self, ticket_id: str) -> dict[str, str] | None: ...


class MockZendeskBackend:
    """Persistent fictional Zendesk replacement for the portable example."""

    def __init__(self, data_dir: Path, state_dir: Path | None) -> None:
        self._lock = threading.RLock()
        self._state_file = (
            state_dir / "tickets.json" if state_dir is not None else None
        )
        if self._state_file is not None:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
        fixture = json.loads(
            (data_dir / "tickets.json").read_text(encoding="utf-8")
        )
        if not isinstance(fixture, list):
            raise ValueError("elevator-service tickets.json must be an array")
        self._tickets = {
            str(ticket["ticket_id"]): {
                **dict(ticket),
                "backend": "mock_zendesk",
            }
            for ticket in fixture
        }
        if self._state_file is not None and self._state_file.is_file():
            persisted = json.loads(
                self._state_file.read_text(encoding="utf-8")
            )
            self._tickets.update(
                {
                    str(ticket["ticket_id"]): {
                        **dict(ticket),
                        "backend": "mock_zendesk",
                    }
                    for ticket in persisted
                }
            )

    def _persist(self) -> None:
        if self._state_file is None:
            return
        temporary = self._state_file.with_name(
            f".{self._state_file.name}.{os.getpid()}.tmp"
        )
        temporary.write_text(
            json.dumps(
                list(self._tickets.values()),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self._state_file)

    def create(
        self,
        business_key: str,
        summary: str,
        address: str,
        postal_code: str,
    ) -> dict[str, str]:
        with self._lock:
            existing = next(
                (
                    ticket
                    for ticket in self._tickets.values()
                    if ticket.get("business_key") == business_key
                ),
                None,
            )
            if existing is not None:
                return dict(existing)
            numeric_ids = [
                int(ticket_id)
                for ticket_id in self._tickets
                if ticket_id.isdigit()
            ]
            ticket_id = str(max(numeric_ids, default=1000) + 1)
            ticket = {
                "ticket_id": ticket_id,
                "subject": f"Elevator service request: {summary}"[:150],
                "status": "new",
                "priority": "normal",
                "updated_at": datetime.now(timezone.utc).isoformat(
                    timespec="seconds"
                ),
                "estimated_visit": "Within 4 demo hours",
                "address": address,
                "postal_code": postal_code,
                "business_key": business_key,
                "backend": "mock_zendesk",
            }
            self._tickets[ticket_id] = ticket
            self._persist()
            return dict(ticket)

    def get(self, ticket_id: str) -> dict[str, str] | None:
        with self._lock:
            ticket = self._tickets.get(ticket_id.strip())
            return dict(ticket) if ticket is not None else None
