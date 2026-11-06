from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


@dataclass
class StateSlot:
    state: dict[str, Any] | None


class CallStore:
    def __init__(
        self,
        state_dir: Path | None,
        *,
        lock_stripes: int = 64,
        max_terminal_calls: int = 1000,
        max_state_age_seconds: int = 86400,
    ) -> None:
        if lock_stripes < 1:
            raise ValueError("lock_stripes must be positive")
        if max_terminal_calls < 1:
            raise ValueError("max_terminal_calls must be positive")
        if max_state_age_seconds < 1:
            raise ValueError("max_state_age_seconds must be positive")
        self._state_dir = state_dir
        self._memory: dict[str, dict[str, Any]] = {}
        self._memory_lock = threading.RLock()
        self._locks = tuple(threading.RLock() for _ in range(lock_stripes))
        self._cleanup_lock = threading.Lock()
        self._max_terminal_calls = max_terminal_calls
        self._max_state_age_seconds = max_state_age_seconds
        if state_dir is not None:
            state_dir.mkdir(parents=True, exist_ok=True)

    def _lock(self, call_id: str) -> threading.RLock:
        return self._locks[hash(call_id) % len(self._locks)]

    def _path(self, call_id: str) -> Path:
        if self._state_dir is None:
            raise RuntimeError("in-memory store has no state path")
        return self._state_dir / f"{call_id}.json"

    def _load(self, call_id: str) -> dict[str, Any] | None:
        if self._state_dir is None:
            with self._memory_lock:
                state = self._memory.get(call_id)
                return (
                    json.loads(json.dumps(state))
                    if state is not None
                    else None
                )
        path = self._path(call_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, call_id: str, state: dict[str, Any]) -> None:
        if self._state_dir is None:
            with self._memory_lock:
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

    def _delete(self, call_id: str) -> None:
        if self._state_dir is None:
            with self._memory_lock:
                self._memory.pop(call_id, None)
            return
        self._path(call_id).unlink(missing_ok=True)

    def _is_expired(self, state: dict[str, Any]) -> bool:
        value = state.get("updated_at")
        if not isinstance(value, str) or not value:
            return False
        try:
            updated_at = datetime.fromisoformat(value)
        except ValueError:
            return False
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - updated_at
        return age.total_seconds() > self._max_state_age_seconds

    def _prune_states(self) -> None:
        with self._cleanup_lock:
            if self._state_dir is None:
                with self._memory_lock:
                    for call_id in [
                        call_id
                        for call_id, state in self._memory.items()
                        if self._is_expired(state)
                    ]:
                        self._memory.pop(call_id, None)
                    terminal = sorted(
                        (
                            str(state.get("updated_at", "")),
                            call_id,
                        )
                        for call_id, state in self._memory.items()
                        if state.get("lifecycle") == "ended"
                    )
                    for _, call_id in terminal[: -self._max_terminal_calls]:
                        self._memory.pop(call_id, None)
                return

            terminal_files: list[tuple[str, Path]] = []
            for path in self._state_dir.glob("*.json"):
                try:
                    state = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if self._is_expired(state):
                    path.unlink(missing_ok=True)
                    continue
                if state.get("lifecycle") == "ended":
                    terminal_files.append(
                        (str(state.get("updated_at", "")), path)
                    )
            terminal_files.sort()
            for _, path in terminal_files[: -self._max_terminal_calls]:
                path.unlink(missing_ok=True)

    @contextmanager
    def locked(self, call_id: str) -> Iterator[StateSlot]:
        with self._lock(call_id):
            state = self._load(call_id)
            if state is not None and self._is_expired(state):
                self._delete(call_id)
                state = None
            slot = StateSlot(state)
            yield slot
            if slot.state is not None:
                self._save(call_id, slot.state)
                self._prune_states()
