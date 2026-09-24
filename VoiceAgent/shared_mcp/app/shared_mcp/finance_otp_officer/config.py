from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_DATA_DIR = ROOT / "data" / "finance_otp_officer"
DEFAULT_AUTH_DIR = ROOT / "state" / "auth"


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    data_dir: Path
    state_dir: Path | None
    auth_dir: Path
    token: str | None
    max_otp_attempts: int
    otp_redis_url: str | None
    otp_redis_password: str | None
    otp_ttl_seconds: int
    default_access_code: str | None
    otp_candidates_file: Path
    directory_id: str = "loan_officers"
    caller_id: str = "caller-demo"
    routing_persona_ref: str = "finance_sample@1"

    @classmethod
    def from_environment(
        cls,
        environment: dict[str, str] | None = None,
    ) -> "ServerConfig":
        values = os.environ if environment is None else environment
        data_dir = Path(
            values.get(
                "FINANCE_OTP_MCP_DATA_DIR",
                str(DEFAULT_DATA_DIR),
            )
        )
        state_raw = values.get(
            "FINANCE_OTP_MCP_STATE_DIR",
            "",
        ).strip()
        auth_dir = Path(
            values.get(
                "FINANCE_OTP_MCP_AUTH_DIR",
                str(DEFAULT_AUTH_DIR),
            )
        )
        token = values.get(
            "SHARED_MCP_TOKEN",
            "",
        ).strip() or None
        try:
            max_otp_attempts = int(
                values.get("FINANCE_OTP_MAX_OTP_ATTEMPTS", "3")
            )
        except ValueError:
            max_otp_attempts = 3
        try:
            otp_ttl_seconds = int(
                values.get("FINANCE_OTP_TTL_SECONDS", "172800")
            )
        except ValueError:
            otp_ttl_seconds = 172800
        default_access_code = values.get(
            "FINANCE_OTP_DEMO_ACCESS_CODE", "12345007"
        ).strip()
        if default_access_code and (
            len(default_access_code) != 8
            or not default_access_code.isascii()
            or not default_access_code.isdigit()
        ):
            raise ValueError("VA_MCP_DEFAULT_ACCESS_CODE must be exactly 8 ASCII digits")
        return cls(
            host=values.get("SHARED_MCP_HOST", "0.0.0.0").strip() or "0.0.0.0",
            port=int(values.get("PORT", values.get("SHARED_MCP_PORT", "8000"))),
            data_dir=data_dir,
            state_dir=Path(state_raw) if state_raw else None,
            auth_dir=auth_dir,
            token=token,
            max_otp_attempts=max(1, max_otp_attempts),
            otp_redis_url=values.get("FINANCE_OTP_REDIS_URL", "").strip() or None,
            otp_redis_password=values.get(
                "FINANCE_OTP_REDIS_PASSWORD", ""
            ).strip() or None,
            otp_ttl_seconds=max(30, otp_ttl_seconds),
            default_access_code=default_access_code or None,
            otp_candidates_file=Path(
                values.get(
                    "FINANCE_OTP_CANDIDATES_FILE",
                    str(data_dir / "otp_candidates.json"),
                )
            ),
            directory_id=values.get(
                "FINANCE_OTP_OFFICER_DIRECTORY_ID", "loan_officers"
            ).strip(),
            caller_id=values.get("FINANCE_OTP_CALLER_ID", "caller-demo").strip(),
            routing_persona_ref=values.get(
                "FINANCE_OTP_PERSONA_REF", "finance_sample@1"
            ).strip(),
        )
