#!/usr/bin/env python3
"""Locate and summarize one Voice Agent portal session recording."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


IDENTITY_FIELDS = (
    "run_id",
    "web_id",
    "session_id",
    "conversation_id",
    "agent",
)


def default_data_dir() -> Path:
    return Path(
        os.getenv(
            "VOICE_PORTAL_DATA_DIR",
            str(Path.home() / ".voice-agent-portal"),
        )
    ).expanduser()


def sessions_dir(data_dir: Path) -> Path:
    resolved = data_dir.expanduser().resolve()
    if resolved.name in {"sessions", "demo-sessions"}:
        return resolved
    portal_sessions = resolved / "sessions"
    dashboard_sessions = resolved / "demo-sessions"
    if dashboard_sessions.is_dir() and not portal_sessions.is_dir():
        return dashboard_sessions
    return portal_sessions


def load_meta(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def load_sessions(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for directory in sorted(root.iterdir(), reverse=True):
        if not directory.is_dir() or directory.is_symlink():
            continue
        meta = load_meta(directory / "meta.json")
        if meta is None:
            continue
        meta["_directory"] = str(directory)
        records.append(meta)
    return records


def identity_values(meta: dict[str, Any]) -> list[str]:
    return [
        str(meta.get(field) or "")
        for field in IDENTITY_FIELDS
        if meta.get(field)
    ]


def select_session(
    records: list[dict[str, Any]],
    identifier: str,
    *,
    latest: bool,
) -> dict[str, Any]:
    exact = [
        meta
        for meta in records
        if identifier in identity_values(meta)
    ]
    matches = exact or [
        meta
        for meta in records
        if any(identifier.lower() in value.lower() for value in identity_values(meta))
    ]
    if not matches:
        raise LookupError(f"no recording matches {identifier!r}")
    if len(matches) > 1 and not latest:
        choices = "\n".join(
            f"  {meta.get('run_id', '')}  {meta.get('agent', '')}  "
            f"{meta.get('session_id', '')}"
            for meta in matches[:20]
        )
        raise LookupError(
            f"{identifier!r} matches {len(matches)} recordings; use an exact ID "
            f"or --latest:\n{choices}"
        )
    return matches[0]


def load_events(path: Path) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = []
    malformed = 0
    try:
        handle = path.open(encoding="utf-8")
    except OSError:
        return events, malformed
    with handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                value = json.loads(line)
            except ValueError:
                malformed += 1
                continue
            if not isinstance(value, dict):
                malformed += 1
                continue
            value["_line"] = line_number
            events.append(value)
    return events, malformed


def build_item_names(events: list[dict[str, Any]]) -> dict[str, str]:
    names: dict[str, str] = {}
    for event in events:
        frame = event.get("frame")
        if not isinstance(frame, dict):
            continue
        candidates: list[Any] = [frame.get("item")]
        response = frame.get("response")
        if isinstance(response, dict):
            candidates.extend(response.get("output") or [])
        for item in candidates:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id") or "")
            name = str(item.get("name") or "")
            if item_id and name:
                names[item_id] = name
    return names


def error_fields(frame: dict[str, Any]) -> tuple[str, str]:
    error = frame.get("error")
    if not isinstance(error, dict):
        response = frame.get("response")
        if isinstance(response, dict):
            status_details = response.get("status_details")
            if isinstance(status_details, dict):
                error = status_details.get("error")
    if isinstance(error, dict):
        return str(error.get("code") or ""), str(error.get("message") or "")
    return "", str(error or "")


def event_faults(
    events: list[dict[str, Any]],
    item_names: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    protocol_errors: list[dict[str, Any]] = []
    handoffs: list[dict[str, Any]] = []
    tool_failures: list[dict[str, Any]] = []
    for event in events:
        event_type = str(event.get("type") or "")
        frame = event.get("frame")
        frame = frame if isinstance(frame, dict) else {}
        base = {
            "t": event.get("t"),
            "line": event.get("_line"),
            "dir": event.get("dir"),
            "type": event_type,
        }
        is_tool_failure = event_type.endswith(".failed") and (
            "mcp_call" in event_type
            or "function_call" in event_type
            or event_type.startswith("mcp_")
        )
        if event_type == "error" or (
            event_type.endswith(".failed") and not is_tool_failure
        ):
            code, message = error_fields(frame)
            protocol_errors.append({**base, "code": code, "message": message})
        if event_type.startswith("session.handoff."):
            code, message = error_fields(frame)
            handoffs.append(
                {
                    **base,
                    "handoff_id": str(frame.get("handoff_id") or ""),
                    "edge_id": str(frame.get("edge_id") or ""),
                    "from_node_id": str(frame.get("from_node_id") or ""),
                    "to_node_id": str(frame.get("to_node_id") or ""),
                    "reason": str(frame.get("reason") or ""),
                    "code": code,
                    "message": message,
                }
            )
        if is_tool_failure:
            item_id = str(frame.get("item_id") or "")
            item = frame.get("item")
            item = item if isinstance(item, dict) else {}
            code, message = error_fields(frame)
            tool_failures.append(
                {
                    **base,
                    "item_id": item_id,
                    "tool": str(
                        frame.get("name")
                        or item.get("name")
                        or item_names.get(item_id)
                        or ""
                    ),
                    "code": code,
                    "message": message,
                }
            )
    return protocol_errors, handoffs, tool_failures


def incomplete_handoffs(handoffs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terminal_ids = {
        str(event.get("handoff_id") or "")
        for event in handoffs
        if event.get("type") in {
            "session.handoff.completed",
            "session.handoff.aborted",
        }
    }
    return [
        event
        for event in handoffs
        if event.get("type") == "session.handoff.started"
        and str(event.get("handoff_id") or "") not in terminal_ids
    ]


def server_log_matches(
    data_dir: Path,
    meta: dict[str, Any],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    needles = [
        str(meta.get("run_id") or ""),
        str(meta.get("web_id") or ""),
    ]
    needles = [needle for needle in needles if needle]
    matches: list[dict[str, Any]] = []
    if not needles:
        return matches
    for path in sorted(data_dir.glob("server.log*")):
        if not path.is_file():
            continue
        try:
            lines = path.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if any(needle in line for needle in needles):
                matches.append(
                    {
                        "path": str(path),
                        "line": line_number,
                        "text": line[:500],
                    }
                )
                if len(matches) >= limit:
                    return matches
    return matches


def elapsed(value: Any) -> str:
    try:
        return f"+{float(value):.3f}s"
    except (TypeError, ValueError):
        return "+?s"


def classify(
    meta: dict[str, Any],
    events: list[dict[str, Any]],
    protocol_errors: list[dict[str, Any]],
    handoffs: list[dict[str, Any]],
    tool_failures: list[dict[str, Any]],
) -> tuple[str, str]:
    session_created = any(event.get("type") == "session.created" for event in events)
    first = first_fault(meta, protocol_errors, handoffs, tool_failures)
    if not session_created:
        if first is not None and first.get("type") == "bridge":
            return (
                "BRIDGE_FAILURE",
                f"local bridge failed before session creation: "
                f"{first.get('message') or 'unknown bridge error'}",
            )
        if protocol_errors:
            first = protocol_errors[0]
            return (
                "SESSION_SETUP_ERROR",
                "session was not created; first service error is "
                f"{first.get('code') or first.get('type')}",
            )
        return "SESSION_NOT_CREATED", "recording contains no session.created event"

    if first is not None and first.get("type") == "bridge":
        return (
            "BRIDGE_FAILURE",
            f"local bridge failed: {first.get('message') or 'unknown bridge error'}",
        )
    if first is not None and first.get("type") == "session.handoff.aborted":
        edge = first.get("edge_id") or (
            f"{first.get('from_node_id')}->{first.get('to_node_id')}"
        )
        return (
            "HANDOFF_ABORTED",
            f"handoff {edge} aborted at {elapsed(first.get('t'))}: "
            f"{first.get('code') or first.get('reason') or 'unknown error'}",
        )
    if first is not None and first in protocol_errors:
        code = str(first.get("code") or "")
        status = (
            "CONFIGURATION_ERROR"
            if code in {"tool_connection_unresolved", "invalid_request_error"}
            else "SERVICE_ERROR"
        )
        return (
            status,
            f"{len(protocol_errors)} service error event(s); first is "
            f"{first.get('code') or first.get('type')} at {elapsed(first.get('t'))}",
        )
    if first is not None and first in tool_failures:
        return (
            "TOOL_FAILURE",
            f"tool {first.get('tool') or first.get('item_id') or 'unknown'} failed "
            f"at {elapsed(first.get('t'))}",
        )
    if not meta.get("ended_at"):
        return "RECORDING_INCOMPLETE", "recording has no ended_at marker"
    dangling = incomplete_handoffs(handoffs)
    if dangling:
        first = dangling[0]
        edge = first.get("edge_id") or (
            f"{first.get('from_node_id')}->{first.get('to_node_id')}"
        )
        return (
            "HANDOFF_INCOMPLETE",
            f"handoff {edge} started at {elapsed(first.get('t'))} but no "
            "completed or aborted event was recorded before session close",
        )
    return (
        "NO_RECORDED_FAILURE",
        "no bridge, protocol, handoff, or tool failure is present in the recording",
    )


def first_fault(
    meta: dict[str, Any],
    protocol_errors: list[dict[str, Any]],
    handoffs: list[dict[str, Any]],
    tool_failures: list[dict[str, Any]],
) -> dict[str, Any] | None:
    faults = list(protocol_errors) + list(tool_failures)
    faults.extend(
        event
        for event in handoffs
        if event["type"] == "session.handoff.aborted"
    )
    for error in meta.get("errors") or []:
        if isinstance(error, dict) and error.get("type") == "bridge":
            faults.append(
                {
                    "t": error.get("t"),
                    "line": None,
                    "dir": "bridge",
                    "type": "bridge",
                    "code": "",
                    "message": str(error.get("message") or ""),
                }
            )
    def sort_key(item: dict[str, Any]) -> float:
        try:
            return float(item.get("t") or 0)
        except (TypeError, ValueError):
            return float("inf")

    return min(faults, key=sort_key, default=None)


def build_report(data_dir: Path, meta: dict[str, Any]) -> dict[str, Any]:
    directory = Path(str(meta["_directory"]))
    events_path = directory / "events.jsonl"
    events, malformed = load_events(events_path)
    item_names = build_item_names(events)
    protocol_errors, handoffs, tool_failures = event_faults(events, item_names)
    dangling_handoffs = incomplete_handoffs(handoffs)
    status, conclusion = classify(
        meta,
        events,
        protocol_errors,
        handoffs,
        tool_failures,
    )
    public_meta = {
        key: value
        for key, value in meta.items()
        if not key.startswith("_")
    }
    return {
        "status": status,
        "conclusion": conclusion,
        "session": public_meta,
        "counts": {
            "recorded_events": len(events),
            "malformed_event_lines": malformed,
            "protocol_errors": len(protocol_errors),
            "handoff_started": sum(
                event["type"] == "session.handoff.started" for event in handoffs
            ),
            "handoff_completed": sum(
                event["type"] == "session.handoff.completed" for event in handoffs
            ),
            "handoff_aborted": sum(
                event["type"] == "session.handoff.aborted" for event in handoffs
            ),
            "handoff_incomplete": len(dangling_handoffs),
            "tool_failures": len(tool_failures),
        },
        "first_fault": first_fault(
            meta,
            protocol_errors,
            handoffs,
            tool_failures,
        ),
        "protocol_errors": protocol_errors,
        "handoffs": handoffs,
        "incomplete_handoffs": dangling_handoffs,
        "tool_failures": tool_failures,
        "server_log_matches": server_log_matches(data_dir, meta),
        "paths": {
            "directory": str(directory),
            "meta": str(directory / "meta.json"),
            "timeline": str(directory / "timeline.log"),
            "events": str(events_path),
            "server_logs": str(data_dir / "server.log*"),
        },
    }


def print_list(records: list[dict[str, Any]], limit: int) -> None:
    print("run_id\tagent\tsession_id\tconversation_id\tstatus")
    for meta in records[:limit]:
        status = "closed" if meta.get("ended_at") else "open"
        print(
            "\t".join(
                (
                    str(meta.get("run_id") or ""),
                    str(meta.get("agent") or ""),
                    str(meta.get("session_id") or ""),
                    str(meta.get("conversation_id") or ""),
                    status,
                )
            )
        )


def print_fault(fault: dict[str, Any] | None) -> None:
    if fault is None:
        print("First fault: none recorded")
        return
    location = (
        f"events.jsonl:{fault['line']}"
        if fault.get("line")
        else "meta.json"
    )
    detail = (
        fault.get("code")
        or fault.get("tool")
        or fault.get("reason")
        or fault.get("message")
        or ""
    )
    print(
        f"First fault: {elapsed(fault.get('t'))} {fault.get('dir')} "
        f"{fault.get('type')} {detail} ({location})"
    )


def print_report(report: dict[str, Any]) -> None:
    meta = report["session"]
    print(f"Conclusion [{report['status']}]: {report['conclusion']}")
    print()
    print("Session:")
    for key in (
        "run_id",
        "agent",
        "backend",
        "web_id",
        "session_id",
        "conversation_id",
        "started_at",
        "ended_at",
        "duration_s",
        "active_node_id",
        "upstream",
    ):
        print(f"  {key}: {meta.get(key, '')}")
    print()
    counts = report["counts"]
    print(
        "Evidence counts: "
        + ", ".join(f"{key}={value}" for key, value in counts.items())
    )
    print_fault(report["first_fault"])

    aborted = [
        event
        for event in report["handoffs"]
        if event["type"] == "session.handoff.aborted"
    ]
    if aborted:
        print("Aborted handoffs:")
        for event in aborted[:20]:
            print(
                f"  {elapsed(event.get('t'))} "
                f"{event.get('from_node_id')} -> {event.get('to_node_id')} "
                f"edge={event.get('edge_id')} "
                f"code={event.get('code') or event.get('reason')} "
                f"line={event.get('line')}"
            )
            if event.get("message"):
                print(f"    {event['message']}")

    if report["incomplete_handoffs"]:
        print("Incomplete handoffs:")
        for event in report["incomplete_handoffs"][:20]:
            print(
                f"  {elapsed(event.get('t'))} "
                f"{event.get('from_node_id')} -> {event.get('to_node_id')} "
                f"edge={event.get('edge_id')} line={event.get('line')}"
            )

    if report["protocol_errors"]:
        print("Service errors:")
        for event in report["protocol_errors"][:20]:
            print(
                f"  {elapsed(event.get('t'))} code={event.get('code')} "
                f"line={event.get('line')} {event.get('message')}"
            )

    if report["tool_failures"]:
        print("Tool failures:")
        for event in report["tool_failures"][:20]:
            print(
                f"  {elapsed(event.get('t'))} "
                f"tool={event.get('tool') or '?'} item={event.get('item_id')} "
                f"code={event.get('code')} line={event.get('line')}"
            )
            if event.get("message"):
                print(f"    {event['message']}")

    print("Artifacts:")
    for key, value in report["paths"].items():
        print(f"  {key}: {value}")
    if meta.get("conversation_id"):
        print(
            "Next evidence: use the conversation_id with "
            "samples/download_conversation_traces.py when local artifacts do not "
            "identify the internal service owner."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identifier", nargs="?")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--list", action="store_true", dest="list_sessions")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    if not args.list_sessions and not args.identifier:
        parser.error("provide an identifier or use --list")
    return args


def main() -> int:
    args = parse_args()
    root = sessions_dir(args.data_dir)
    data_dir = root.parent
    records = load_sessions(root)
    if args.list_sessions:
        if args.as_json:
            print(
                json.dumps(
                    [
                        {
                            key: value
                            for key, value in meta.items()
                            if not key.startswith("_")
                        }
                        for meta in records[: args.limit]
                    ],
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print_list(records, args.limit)
        return 0
    try:
        meta = select_session(records, args.identifier, latest=args.latest)
    except LookupError as error:
        print(f"error: {error}", file=sys.stderr)
        print(f"searched: {root}", file=sys.stderr)
        return 2
    report = build_report(data_dir, meta)
    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
