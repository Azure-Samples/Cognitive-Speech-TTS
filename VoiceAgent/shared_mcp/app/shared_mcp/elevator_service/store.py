from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


@dataclass
class StateSlot:
    state: dict[str, Any] | None


class CallStore:
    def __init__(self, state_dir: Path | None) -> None:
        self._state_dir = state_dir
        self._memory: dict[str, dict[str, Any]] = {}
        self._locks_guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}
        if state_dir is not None:
            state_dir.mkdir(parents=True, exist_ok=True)

    def _lock(self, call_id: str) -> threading.RLock:
        with self._locks_guard:
            return self._locks.setdefault(call_id, threading.RLock())

    def _path(self, call_id: str) -> Path:
        if self._state_dir is None:
            raise RuntimeError("in-memory store has no state path")
        return self._state_dir / f"{call_id}.json"

    def _load(self, call_id: str) -> dict[str, Any] | None:
        if self._state_dir is None:
            state = self._memory.get(call_id)
            return json.loads(json.dumps(state)) if state is not None else None
        path = self._path(call_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, call_id: str, state: dict[str, Any]) -> None:
        if self._state_dir is None:
            self._memory[call_id] = json.loads(json.dumps(state))
            return
        path = self._path(call_id)
        temporary = path.with_name(
            f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        temporary.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)

    @contextmanager
    def locked(self, call_id: str) -> Iterator[StateSlot]:
        with self._lock(call_id):
            slot = StateSlot(self._load(call_id))
            yield slot
            if slot.state is not None:
                self._save(call_id, slot.state)
