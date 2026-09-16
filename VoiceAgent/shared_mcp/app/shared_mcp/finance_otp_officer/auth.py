"""Per-caller 8-digit access code (OTP) service.

Adapted from the interview identity gate. Codes are 8 digits, single-use,
short-lived, and only SHA-256 digests are ever stored. Caller-issued codes are keyed by
caller_id; issuing again replaces that caller's active code.

The reserved test codes exist so validator and manual test rounds have
deterministic identities to read out. They are the ONLY codes that survive a
fresh state directory.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import secrets
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import fcntl

OTP_DIGITS = 8
OTP_TTL_SECONDS = 48 * 60 * 60
TEST_ACCESS_CODE = "12345678"
TEST_CALLER_ID = "caller-demo"
HARDCODED_CANDIDATE_ACCESS_CODES = {
    "87654321": "cand-jeremy-downer",
    "24681357": "cand-daniel-okafor",
    "12345007": "cand-yiwen-rong",
}
AUTHENTICATED_STATUSES = frozenset({"verified", "test_verified"})
LEGACY_GLOBAL_CANDIDATE_ID = "__global_ui_otp__"

_ISSUE_REDIS_OTP = """
redis.call('DEL', KEYS[2])
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
return 1
"""

_CONSUME_REDIS_OTP = """
local value = redis.call('GET', KEYS[1])
if not value then
    local consumed = redis.call('GET', KEYS[2])
    if consumed == ARGV[1] then return 2 end
    return 0
end
if value ~= ARGV[1] then return 0 end
local ttl = redis.call('TTL', KEYS[1])
redis.call('DEL', KEYS[1])
if ttl > 0 then redis.call('SET', KEYS[2], ARGV[1], 'EX', ttl) end
return 1
"""

_ISSUE_CANDIDATE_REDIS_OTP = """
if redis.call('EXISTS', KEYS[2]) == 1 then return 0 end
local previous = redis.call('GET', KEYS[1])
if previous then redis.call('DEL', previous) end
redis.call('SET', KEYS[2], ARGV[1], 'EX', ARGV[2])
redis.call('SET', KEYS[1], KEYS[2], 'EX', ARGV[2])
return 1
"""

_CONSUME_CANDIDATE_REDIS_OTP = """
local candidate = redis.call('GET', KEYS[1])
if not candidate then
    local consumed = redis.call('GET', KEYS[2])
    if consumed then return {2, consumed} end
    return {0, ''}
end
local ttl = redis.call('TTL', KEYS[1])
local active = ARGV[1] .. candidate
if redis.call('GET', active) == KEYS[1] then redis.call('DEL', active) end
redis.call('DEL', KEYS[1])
if ttl > 0 then redis.call('SET', KEYS[2], candidate, 'EX', ttl) end
return {1, candidate}
"""


@dataclass
class _OtpRecord:
    digest: str
    created_at: float
    expires_at: float
    consumed: bool = False


@dataclass
class _CandidateOtpRecord:
    candidate_id: str
    created_at: float
    expires_at: float
    consumed: bool = False


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


class OtpService:
    """Issue and verify caller OTPs plus one UI-issued OTP shared by all callers."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.time,
        code_factory: Callable[[], str] | None = None,
        ttl_seconds: int = OTP_TTL_SECONDS,
        state_dir: Path | None = None,
        test_access_code: str | None = TEST_ACCESS_CODE,
        redis_url: str | None = None,
        redis_password: str | None = None,
        redis_client: Any | None = None,
    ) -> None:
        self._clock = clock
        self._ttl = ttl_seconds
        self._state_dir = state_dir
        self._test_access_code = test_access_code
        self._code_factory = code_factory or self._random_code
        self._redis = redis_client
        if self._redis is None and redis_url:
            Redis = importlib.import_module("redis").Redis
            self._redis = Redis.from_url(
                redis_url,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        self._by_caller: dict[str, _OtpRecord] = {}
        self._candidate_by_digest: dict[str, _CandidateOtpRecord] = {}
        self._active_digest_by_candidate: dict[str, str] = {}
        self._lock = threading.RLock()
        if state_dir is not None:
            state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            state_dir.chmod(0o700)

    def _random_code(self) -> str:
        while True:
            code = f"{secrets.randbelow(10 ** OTP_DIGITS):0{OTP_DIGITS}d}"
            if not self._is_reserved_code(code):
                return code

    def _is_reserved_code(self, code: str) -> bool:
        if code in HARDCODED_CANDIDATE_ACCESS_CODES:
            return True
        return self._test_access_code is not None and secrets.compare_digest(
            code, self._test_access_code
        )

    @staticmethod
    def _digest(code: str) -> str:
        return hashlib.sha256(str(code).encode("ascii")).hexdigest()

    @staticmethod
    def normalize(spoken: str) -> str:
        """Keep only digits. A caller reading a code aloud produces spaces and dashes."""
        return "".join(char for char in str(spoken) if char.isdigit())

    def issue(self, caller_id: str) -> dict:
        now = self._clock()
        code = self._new_code()
        record = _OtpRecord(self._digest(code), now, now + self._ttl)
        with self._caller_lock(caller_id):
            self._save(caller_id, record)
        return self._issued(code, now)

    def _new_code(self) -> str:
        code = self._code_factory()
        if len(code) != OTP_DIGITS or not code.isascii() or not code.isdigit():
            raise ValueError(
                f"OTP generator must return exactly {OTP_DIGITS} ASCII digits"
            )
        if self._is_reserved_code(code):
            raise ValueError("OTP generator returned a reserved test access code")
        return code

    def _issued(self, code: str, created_at: float, **fields: Any) -> dict[str, Any]:
        return {
            "otp": code,
            "created_at": _iso(created_at),
            "expires_at": _iso(created_at + self._ttl),
            "expires_in_seconds": self._ttl,
            **fields,
        }

    def issue_global(self) -> dict:
        """Compatibility alias for callers predating candidate-bound issuance."""
        return self.issue_candidate(LEGACY_GLOBAL_CANDIDATE_ID)

    def issue_candidate(self, candidate_id: str) -> dict[str, Any]:
        """Issue one code for a candidate, replacing that candidate's active code."""
        if not candidate_id:
            raise ValueError("candidate_id is required")
        for _ in range(10):
            now = self._clock()
            code = self._new_code()
            digest = self._digest(code)
            if self._redis is not None:
                created = self._redis.eval(
                    _ISSUE_CANDIDATE_REDIS_OTP,
                    2,
                    self._candidate_active_key(candidate_id),
                    self._candidate_code_key(digest),
                    candidate_id,
                    self._ttl,
                )
                if created == 1:
                    return self._issued(code, now, candidate_id=candidate_id)
                continue
            with self._candidate_lock():
                by_digest, active = self._load_candidate_index()
                if digest in by_digest:
                    continue
                previous = active.get(candidate_id)
                if previous:
                    by_digest.pop(previous, None)
                by_digest[digest] = _CandidateOtpRecord(
                    candidate_id=candidate_id,
                    created_at=now,
                    expires_at=now + self._ttl,
                )
                active[candidate_id] = digest
                self._save_candidate_index(by_digest, active)
                return self._issued(code, now, candidate_id=candidate_id)
        raise RuntimeError("could not allocate a unique OTP")

    def verify(self, caller_id: str, code: str) -> str:
        status, _ = self.verify_candidate(code)
        if status != "invalid":
            return status
        code = self.normalize(code)
        return self._verify_record(caller_id, code)

    def verify_candidate(
        self,
        code: str,
        default_candidate_id: str | None = None,
    ) -> tuple[str, str | None]:
        """Consume a candidate OTP and return the identity it authenticated."""
        code = self.normalize(code)
        if self._test_access_code is not None and secrets.compare_digest(
            code, self._test_access_code
        ):
            return "test_verified", default_candidate_id
        for hardcoded_code, candidate_id in HARDCODED_CANDIDATE_ACCESS_CODES.items():
            if secrets.compare_digest(code, hardcoded_code):
                return "test_verified", candidate_id
        if len(code) != OTP_DIGITS or not code.isascii() or not code.isdigit():
            return ("invalid_length" if len(code) != OTP_DIGITS else "invalid"), None
        digest = self._digest(code)
        if self._redis is not None:
            result = self._redis.eval(
                _CONSUME_CANDIDATE_REDIS_OTP,
                2,
                self._candidate_code_key(digest),
                self._candidate_consumed_key(digest),
                self._candidate_active_prefix(),
            )
            outcome = int(result[0])
            candidate_id = result[1]
            if isinstance(candidate_id, bytes):
                candidate_id = candidate_id.decode("utf-8")
            if outcome == 1:
                return "verified", str(candidate_id)
            if outcome == 2:
                return "consumed", None
            return "invalid", None
        with self._candidate_lock():
            by_digest, active = self._load_candidate_index()
            record = by_digest.get(digest)
            if record is None:
                return "invalid", None
            if record.consumed:
                return "consumed", None
            if self._clock() > record.expires_at:
                if active.get(record.candidate_id) == digest:
                    active.pop(record.candidate_id, None)
                by_digest.pop(digest, None)
                self._save_candidate_index(by_digest, active)
                return "expired", None
            record.consumed = True
            if active.get(record.candidate_id) == digest:
                active.pop(record.candidate_id, None)
            self._save_candidate_index(by_digest, active)
            return "verified", record.candidate_id

    def _verify_record(self, caller_id: str, code: str) -> str:
        if self._redis is not None:
            result = self._redis.eval(
                _CONSUME_REDIS_OTP,
                2,
                self._redis_key(caller_id),
                self._redis_consumed_key(caller_id),
                self._digest(code),
            )
            if result == 1:
                return "verified"
            if result == 2:
                return "consumed"
            return "invalid"
        with self._caller_lock(caller_id):
            record = self._load(caller_id)
            if record is None or not secrets.compare_digest(
                record.digest, self._digest(code)
            ):
                return "invalid"
            if record.consumed:
                return "consumed"
            if self._clock() > record.expires_at:
                return "expired"
            record.consumed = True
            self._save(caller_id, record)
            return "verified"

    def _path(self, caller_id: str) -> Path | None:
        if self._state_dir is None:
            return None
        key = hashlib.sha256(caller_id.encode("utf-8")).hexdigest()
        return self._state_dir / f"{key}.json"

    def _candidate_index_path(self) -> Path | None:
        if self._state_dir is None:
            return None
        return self._state_dir / "candidate-otps.json"

    @contextmanager
    def _candidate_lock(self):
        with self._lock:
            path = self._candidate_index_path()
            if path is None:
                yield
                return
            with path.with_suffix(".lock").open("a", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    @contextmanager
    def _caller_lock(self, caller_id: str):
        with self._lock:
            if self._redis is not None:
                yield
                return
            path = self._path(caller_id)
            if path is None:
                yield
                return
            lock_path = path.with_suffix(".lock")
            with lock_path.open("a", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _load(self, caller_id: str) -> _OtpRecord | None:
        if self._redis is not None:
            return None
        path = self._path(caller_id)
        if path is None:
            return self._by_caller.get(caller_id)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            return _OtpRecord(
                digest=str(document["digest"]),
                created_at=float(document["created_at"]),
                expires_at=float(document["expires_at"]),
                consumed=bool(document.get("consumed", False)),
            )
        except (
            FileNotFoundError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return None

    def _save(self, caller_id: str, record: _OtpRecord) -> None:
        if self._redis is not None:
            key = self._redis_key(caller_id)
            if record.consumed:
                self._redis.delete(key)
                return
            ttl = max(1, int(record.expires_at - self._clock()))
            self._redis.eval(
                _ISSUE_REDIS_OTP,
                2,
                key,
                self._redis_consumed_key(caller_id),
                record.digest,
                ttl,
            )
            return
        path = self._path(caller_id)
        if path is None:
            self._by_caller[caller_id] = record
            return
        document = {
            "digest": record.digest,
            "created_at": record.created_at,
            "expires_at": record.expires_at,
            "consumed": record.consumed,
        }
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(document, output, separators=(",", ":"))
        os.replace(temporary, path)

    def _load_candidate_index(
        self,
    ) -> tuple[dict[str, _CandidateOtpRecord], dict[str, str]]:
        path = self._candidate_index_path()
        if path is None:
            return self._candidate_by_digest, self._active_digest_by_candidate
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            by_digest = {
                str(digest): _CandidateOtpRecord(
                    candidate_id=str(item["candidate_id"]),
                    created_at=float(item["created_at"]),
                    expires_at=float(item["expires_at"]),
                    consumed=bool(item.get("consumed", False)),
                )
                for digest, item in document.get("by_digest", {}).items()
            }
            active = {
                str(candidate_id): str(digest)
                for candidate_id, digest in document.get("active", {}).items()
            }
            return by_digest, active
        except (
            FileNotFoundError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return {}, {}

    def _save_candidate_index(
        self,
        by_digest: dict[str, _CandidateOtpRecord],
        active: dict[str, str],
    ) -> None:
        path = self._candidate_index_path()
        if path is None:
            self._candidate_by_digest = by_digest
            self._active_digest_by_candidate = active
            return
        document = {
            "by_digest": {
                digest: {
                    "candidate_id": record.candidate_id,
                    "created_at": record.created_at,
                    "expires_at": record.expires_at,
                    "consumed": record.consumed,
                }
                for digest, record in by_digest.items()
            },
            "active": active,
        }
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(document, output, separators=(",", ":"))
        os.replace(temporary, path)

    @staticmethod
    def _redis_key(caller_id: str) -> str:
        key = hashlib.sha256(caller_id.encode("utf-8")).hexdigest()
        return f"va-mcp:otp:{key}"

    @classmethod
    def _redis_consumed_key(cls, caller_id: str) -> str:
        return f"{cls._redis_key(caller_id)}:consumed"

    @staticmethod
    def _candidate_active_prefix() -> str:
        return "va-mcp:{otp}:candidate:"

    @classmethod
    def _candidate_active_key(cls, candidate_id: str) -> str:
        return f"{cls._candidate_active_prefix()}{candidate_id}"

    @staticmethod
    def _candidate_code_key(digest: str) -> str:
        return f"va-mcp:{{otp}}:code:{digest}"

    @staticmethod
    def _candidate_consumed_key(digest: str) -> str:
        return f"va-mcp:{{otp}}:consumed:{digest}"
