"""Per-session recording for the demo bridge.

A demo session used to leave nothing behind: the event stream lived only in the browser tab
(gone on refresh), and the one thing that did reach disk -- the bridge's stdout -- interleaved
every concurrent session into a single file. Debugging "what happened in that call" meant
reproducing it.

So every bridged session writes its own directory, addressable by any of the ids the session
is known by:

    <data-dir>/demo-sessions/<UTC-stamp>-<web-id>/
        meta.json       identity + counters, written on close (and best-effort on crash)
        timeline.log    one human-readable line per meaningful event
        events.jsonl    every frame, audio payloads elided

Audio is the reason this needs care rather than a plain tee: `input_audio_buffer.append` and
`response.audio.delta` carry base64 PCM and arrive every few tens of milliseconds. They are
counted and coalesced into a single summary line instead of being written out, which keeps a
ten-minute call in the low hundreds of KB rather than hundreds of MB.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Frames whose payload is audio: counted, never written. Matched on the event type suffix so a
# renamed prefix (response.audio.delta vs response.output_audio.delta) still gets caught.
_AUDIO_TYPES = re.compile(r"(audio\.delta|audio_buffer\.append|audio\.done)$")
# Text arrives one token at a time; the assembled `.done` event carries the same content.
_DELTA_TYPES = re.compile(r"\.delta$")
_UNSAFE_RUN_ID_CHARS = re.compile(r"[^A-Za-z0-9_-]+")

_MAX_FIELD = 400
_SECRET_KEYS = frozenset({
    "authorization", "api_key", "api-key", "apikey", "access_token",
    "refresh_token", "token", "password", "secret", "client_secret",
    "connection_string", "x-ms-oai-authorization-header-value",
    "credential", "credentials", "accesstoken", "refreshtoken", "clientsecret",
})

_INTERESTING = (
    "session.created",
    "session.updated",
    "error",
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_run_component(value: str) -> str:
    component = _UNSAFE_RUN_ID_CHARS.sub("-", value).strip("-_")
    return component[:80] or "session"


def _clip(value: Any) -> Any:
    """Keep a frame readable without letting one field carry a whole prompt."""
    if isinstance(value, str) and len(value) > _MAX_FIELD:
        return value[:_MAX_FIELD] + f"…(+{len(value) - _MAX_FIELD} chars)"
    if isinstance(value, dict):
        return {k: "<redacted>" if k.lower() in _SECRET_KEYS else _clip(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clip(v) for v in value[:20]]
    return value


class SessionRecorder:
    """One bridged browser session. Not thread-safe; the bridge drives it from one event loop."""

    def __init__(self, root: Path, *, web_id: str, agent: str, backend: str, upstream: str,
                 voice_override: str = "", query: dict | None = None) -> None:
        self.run_id = f"{_utc_stamp()}-{_safe_run_component(web_id)}"
        self.dir = root / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self._started = time.monotonic()
        self._events = (self.dir / "events.jsonl").open("a", encoding="utf-8")
        self._timeline = (self.dir / "timeline.log").open("a", encoding="utf-8")
        self._audio = {"up": [0, 0], "down": [0, 0]}  # direction -> [frames, bytes]
        # A tool call is named once, in `response.output_item.added`; every later frame about it
        # carries only `item_id`. Without this map the timeline reads "mcp_call.completed" with no
        # way to tell which tool completed.
        self._item_names: dict[str, str] = {}
        self.meta: dict[str, Any] = {
            "run_id": self.run_id,
            "web_id": web_id,
            "agent": agent,
            "backend": backend,
            "upstream": upstream,
            "voice_override": voice_override or "",
            "query": query or {},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "session_id": "",
            "conversation_id": "",
            "active_node_id": "",
            "tool_calls": [],
            "errors": [],
            "counts": {"up": 0, "down": 0, "audio_frames": 0},
        }
        self._write_meta()
        self._line("bridge", f"open agent={agent} backend={backend} web_id={web_id}")

    # ---- writing ----------------------------------------------------------

    def _line(self, kind: str, text: str) -> None:
        elapsed = time.monotonic() - self._started
        self._timeline.write(f"{elapsed:8.3f}  {kind:<5} {text}\n")
        self._timeline.flush()

    def _write_meta(self) -> None:
        (self.dir / "meta.json").write_text(
            json.dumps(self.meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _flush_audio(self, direction: str) -> None:
        frames, size = self._audio[direction]
        if not frames:
            return
        self._audio[direction] = [0, 0]
        self._line("audio", f"{direction} {frames} frames, {size / 1024:.1f} KB elided")

    # ---- recording --------------------------------------------------------

    def record(self, direction: str, raw: Any) -> None:
        """direction: 'up' (browser->service) or 'down' (service->browser)."""
        try:
            self._record(direction, raw)
        except Exception:  # noqa: BLE001 - recording must never break the call it observes
            pass

    def _record(self, direction: str, raw: Any) -> None:
        self.meta["counts"][direction] += 1
        if isinstance(raw, (bytes, bytearray)):
            self._audio[direction][0] += 1
            self._audio[direction][1] += len(raw)
            self.meta["counts"]["audio_frames"] += 1
            return

        try:
            frame = json.loads(raw)
        except (TypeError, ValueError):
            return
        if not isinstance(frame, dict):
            return
        event_type = str(frame.get("type") or "")

        if _AUDIO_TYPES.search(event_type):
            self._audio[direction][0] += 1
            self._audio[direction][1] += len(raw or "")
            self.meta["counts"]["audio_frames"] += 1
            return

        self._flush_audio(direction)

        # Token-level deltas would be most of the file and carry nothing the `.done` twin lacks.
        is_delta = bool(_DELTA_TYPES.search(event_type))
        if not is_delta:
            elapsed = time.monotonic() - self._started
            self._events.write(json.dumps(
                {"t": round(elapsed, 3), "dir": direction, "type": event_type,
                 "frame": _clip(frame)},
                ensure_ascii=False,
            ) + "\n")
            self._events.flush()

        item = frame.get("item") or {}
        if isinstance(item, dict) and item.get("id") and item.get("name"):
            self._item_names[str(item["id"])] = str(item["name"])

        if is_delta:
            return

        self._note(direction, event_type, _clip(frame))

    def _note(self, direction: str, event_type: str, frame: dict) -> None:
        """Promote the handful of events that answer "what happened" into the timeline."""
        session = frame.get("session") or {}

        if event_type in ("session.created", "session.updated"):
            sid = str(session.get("id") or "")
            if sid and sid != self.meta["session_id"]:
                self.meta["session_id"] = sid
            handoff = session.get("handoff") or {}
            node = str(handoff.get("active_node_id") or "")
            if node and node != self.meta["active_node_id"]:
                self.meta["active_node_id"] = node
                self._line(direction, f"{event_type} active_node={node}")
                self._write_meta()
                return

        conv = frame.get("conversation_id") or (frame.get("conversation") or {}).get("id")
        if conv and conv != self.meta["conversation_id"]:
            self.meta["conversation_id"] = str(conv)
            self._line(direction, f"conversation={conv}")

        # The tool sequence is the thing worth reading first, so it gets named explicitly --
        # this mirrors how the v5 MCP server log is read (`tool=… ok=…`).
        if "mcp_call" in event_type or "function_call" in event_type:
            item = frame.get("item") or {}
            name = (str(frame.get("name") or "")
                    or str(item.get("name") or "")
                    or self._item_names.get(str(frame.get("item_id") or ""), ""))
            suffix = event_type.rsplit(".", 1)[-1]
            if name and suffix in ("done", "completed", "failed"):
                self.meta["tool_calls"].append({"t": round(time.monotonic() - self._started, 3),
                                                "tool": name, "phase": suffix})
                self._line(direction, f"{event_type} tool={name}")
                if suffix in ("completed", "failed"):
                    self._write_meta()
                return
            self._line(direction, f"{event_type}{f' tool={name}' if name else ''}")
            return

        if event_type == "error" or event_type.endswith(".failed"):
            message = ((frame.get("error") or {}).get("message")
                       if isinstance(frame.get("error"), dict) else None)
            detail = str(message or frame.get("error") or "")[:300]
            self.meta["errors"].append({"t": round(time.monotonic() - self._started, 3),
                                        "type": event_type, "message": detail})
            self._line(direction, f"{event_type} {detail}")
            self._write_meta()
            return

        if event_type in _INTERESTING or event_type.startswith("session.handoff"):
            extra = f" session={self.meta['session_id']}" if event_type == "session.created" else ""
            self._line(direction, f"{event_type}{extra}")

    # ---- lifecycle --------------------------------------------------------

    def close(self, error: str = "") -> None:
        for direction in ("up", "down"):
            self._flush_audio(direction)
        if error:
            self.meta["errors"].append({"t": round(time.monotonic() - self._started, 3),
                                        "type": "bridge", "message": error})
        self.meta["ended_at"] = datetime.now(timezone.utc).isoformat()
        self.meta["duration_s"] = round(time.monotonic() - self._started, 3)
        self._line("bridge", f"close after {self.meta['duration_s']}s"
                             + (f" error={error}" if error else ""))
        self._write_meta()
        for handle in (self._events, self._timeline):
            try:
                handle.close()
            except Exception:  # noqa: BLE001 - closing a log must not mask the session's own error
                pass


# ---- reading back ---------------------------------------------------------


def list_sessions(root: Path, *, limit: int = 50, query: str = "") -> list[dict]:
    """Newest first. `query` matches any id the session is known by, so a `sess_`/`conv_`
    copied off the page finds its directory without knowing the run id."""
    if not root.exists():
        return []
    found: list[dict] = []
    for path in sorted(root.iterdir(), reverse=True):
        meta_path = path / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if query:
            haystack = " ".join(str(meta.get(key, "")) for key in
                                ("run_id", "web_id", "session_id", "conversation_id", "agent"))
            if query.lower() not in haystack.lower():
                continue
        found.append(meta)
        if len(found) >= limit:
            break
    return found


def read_session(root: Path, run_id: str) -> dict | None:
    """Full detail for one run: meta plus the timeline, which is what a human reads first."""
    # `run_id` reaches this from a URL; keep it to one path segment so it cannot escape the root.
    if "/" in run_id or "\\" in run_id or run_id.startswith("."):
        return None
    directory = root / run_id
    meta_path = directory / "meta.json"
    if not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    timeline = ""
    timeline_path = directory / "timeline.log"
    if timeline_path.is_file():
        timeline = timeline_path.read_text(encoding="utf-8")
    return {**meta, "timeline": timeline, "directory": str(directory)}


def read_events(root: Path, run_id: str, *, limit: int = 2000) -> list[dict] | None:
    if "/" in run_id or "\\" in run_id or run_id.startswith("."):
        return None
    path = root / run_id / "events.jsonl"
    if not path.is_file():
        return None
    events: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
            if len(events) >= limit:
                break
    return events
