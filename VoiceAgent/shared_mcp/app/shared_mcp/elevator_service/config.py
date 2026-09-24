from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_DATA_DIR = ROOT / "data" / "elevator_service"


@dataclass(frozen=True)
class ServerConfig:
    data_dir: Path
    state_dir: Path | None

    @classmethod
    def from_environment(
        cls,
        environment: dict[str, str] | None = None,
    ) -> "ServerConfig":
        values = os.environ if environment is None else environment
        state_raw = values.get("ELEVATOR_MCP_STATE_DIR", "").strip()
        return cls(
            data_dir=Path(
                values.get(
                    "ELEVATOR_MCP_DATA_DIR",
                    str(DEFAULT_DATA_DIR),
                )
            ),
            state_dir=Path(state_raw) if state_raw else None,
        )
