"""Fake loan-officer name search for the customer sample.

The production implementation uses a large phonetic index and recognizer-aware
ranking. That dependency is intentionally omitted from this portable sample
because of its size and complexity. Every non-empty query returns one random
available fictional officer so customers can exercise the complete Agent flow.
"""

from __future__ import annotations

import random
from typing import Any, Sequence

from .data import OfficerDirectory


def preload(directory: OfficerDirectory) -> dict[str, Any]:
    return {
        "directory_id": directory.directory_id,
        "officers": len(directory.officers),
        "implementation": "fake_random_sample",
    }


def search_candidates(
    directory: OfficerDirectory,
    spoken_names: Sequence[str],
    limit: int = 3,
) -> dict[str, Any]:
    del limit
    queries = [text.strip() for text in spoken_names if text and text.strip()]
    if not queries:
        return {
            "status": "no_match",
            "query": "",
            "queries": [],
            "normalized_query": "",
            "matches": [],
            "reason": "empty_query",
            "implementation": "fake_random_sample",
        }

    available = [
        officer for officer in directory.officers if officer.status == "available"
    ]
    if not available:
        return {
            "status": "no_match",
            "query": queries[0],
            "queries": queries,
            "normalized_query": queries[0].casefold(),
            "matches": [],
            "reason": "no_available_officer",
            "implementation": "fake_random_sample",
        }

    officer = random.SystemRandom().choice(available)
    return {
        "status": "one_match",
        "query": queries[0],
        "queries": queries,
        "normalized_query": queries[0].casefold(),
        "matches": [dict(officer.public(), confidence=1.0)],
        "reason": "fake_random_name_search",
        "implementation": "fake_random_sample",
    }


def search(
    directory: OfficerDirectory,
    spoken_name: str,
    limit: int = 3,
) -> dict[str, Any]:
    return search_candidates(directory, [spoken_name], limit)

