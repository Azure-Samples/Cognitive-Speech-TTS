from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_DATA_DIR = ROOT / "data" / "finance_handoff"


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    data_dir: Path
    state_dir: Path | None
    token: str | None
    lead_id: str
    campaign_id: str
    ivr_menu_id: str
    agent_persona_ref: str

    @classmethod
    def from_environment(
        cls,
        environment: dict[str, str] | None = None,
    ) -> "ServerConfig":
        values = os.environ if environment is None else environment
        state_raw = values.get("FINANCE_MCP_STATE_DIR", "").strip()
        return cls(
            host=values.get("FINANCE_MCP_HOST", "0.0.0.0").strip() or "0.0.0.0",
            port=int(values.get("FINANCE_MCP_PORT", "8961")),
            data_dir=Path(
                values.get("FINANCE_MCP_DATA_DIR", str(DEFAULT_DATA_DIR))
            ),
            state_dir=Path(state_raw) if state_raw else None,
            token=values.get("FINANCE_MCP_TOKEN", "").strip() or None,
            lead_id=values.get("FINANCE_LEAD_ID", "lead-mengyou").strip(),
            campaign_id=values.get(
                "FINANCE_CAMPAIGN_ID", "personal_loan_preapproved"
            ).strip(),
            ivr_menu_id=values.get(
                "FINANCE_IVR_MENU_ID", "corporate_switchboard"
            ).strip(),
            agent_persona_ref=values.get(
                "FINANCE_PERSONA_REF", "outbound_standard@1"
            ).strip(),
        )
