from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "debug-local-session"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS))

from analyze_session import classify, event_faults  # noqa: E402


def _handoff(event_type: str) -> dict[str, object]:
    return {
        "t": 5.0 if event_type.endswith("started") else 6.0,
        "dir": "down",
        "type": event_type,
        "frame": {
            "handoff_id": "handoff-test",
            "edge_id": "entrypoint_to_target",
            "from_node_id": "$entrypoint",
            "to_node_id": "target",
        },
        "_line": 2 if event_type.endswith("started") else 3,
    }


class AnalyzeSessionTests(unittest.TestCase):
    def _classify(self, events: list[dict[str, object]]) -> tuple[str, str]:
        protocol_errors, handoffs, tool_failures = event_faults(events, {})
        return classify(
            {"ended_at": "2026-09-22T11:14:20+00:00", "errors": []},
            events,
            protocol_errors,
            handoffs,
            tool_failures,
        )

    def test_closed_session_with_unfinished_handoff_is_incomplete(self) -> None:
        status, conclusion = self._classify(
            [
                {"type": "session.created", "frame": {}, "_line": 1},
                _handoff("session.handoff.started"),
            ]
        )

        self.assertEqual(status, "HANDOFF_INCOMPLETE")
        self.assertIn("entrypoint_to_target", conclusion)

    def test_completed_handoff_is_not_incomplete(self) -> None:
        status, _ = self._classify(
            [
                {"type": "session.created", "frame": {}, "_line": 1},
                _handoff("session.handoff.started"),
                _handoff("session.handoff.completed"),
            ]
        )

        self.assertEqual(status, "NO_RECORDED_FAILURE")


if __name__ == "__main__":
    unittest.main()