from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .config import ServerConfig
from .service import ElevatorService
from .store import CallStore
from .tickets import MockZendeskBackend


CallId = Annotated[
    str,
    Field(description="Stable platform or demo call identifier."),
]
CallToken = Annotated[
    str,
    Field(
        min_length=32,
        max_length=128,
        description="Capability returned by start_service_call.",
    ),
]
CommandId = Annotated[
    str,
    Field(description="Idempotency key reused only for an exact retry."),
]
IssueHandle = Annotated[
    str,
    Field(description="Current issue_handle returned by record_issue."),
]
IssueRevision = Annotated[
    int,
    Field(ge=1, description="Current issue_revision returned by the backend."),
]
SafetyStatus = Literal["unknown", "clear", "present", "cannot_confirm"]


def build_service(
    config: ServerConfig,
    call_token_secret: str | bytes,
) -> ElevatorService:
    call_state_dir = (
        config.state_dir / "calls"
        if config.state_dir is not None
        else None
    )
    return ElevatorService(
        CallStore(call_state_dir),
        MockZendeskBackend(config.data_dir, config.state_dir),
        call_token_secret,
    )


def register_tools(mcp: FastMCP, service: ElevatorService) -> None:
    @mcp.tool()
    def start_service_call(
        call_id: CallId,
        command_id: CommandId,
        caller_ref: Annotated[
            str,
            Field(default="", description="Optional fictional caller reference."),
        ] = "",
    ) -> dict[str, Any]:
        """Open authoritative call state."""
        return service.start_service_call(call_id, command_id, caller_ref)

    @mcp.tool()
    def record_issue(
        call_id: CallId,
        call_token: CallToken,
        command_id: CommandId,
        issue_summary: Annotated[
            str,
            Field(min_length=8, max_length=500),
        ],
        source_turn_id: Annotated[
            str,
            Field(default="", max_length=128),
        ] = "",
    ) -> dict[str, Any]:
        """Start the report lane for one issue."""
        return service.record_issue(
            call_id,
            call_token,
            command_id,
            issue_summary,
            source_turn_id,
        )

    @mcp.tool()
    def assess_safety(
        call_id: CallId,
        call_token: CallToken,
        command_id: CommandId,
        issue_handle: IssueHandle,
        issue_revision: IssueRevision,
        entrapment_or_egress: SafetyStatus,
        injury_or_medical: SafetyStatus,
        fire_heat_or_smoke: SafetyStatus,
        flooding_or_electrical_hazard: SafetyStatus,
        unsafe_elevator_movement: SafetyStatus,
        source_turn_id: Annotated[
            str,
            Field(default="", max_length=128),
        ] = "",
    ) -> dict[str, Any]:
        """Return the next deterministic safety action."""
        return service.assess_safety(
            call_id,
            call_token,
            command_id,
            issue_handle,
            issue_revision,
            {
                "entrapment_or_egress": entrapment_or_egress,
                "injury_or_medical": injury_or_medical,
                "fire_heat_or_smoke": fire_heat_or_smoke,
                "flooding_or_electrical_hazard": (
                    flooding_or_electrical_hazard
                ),
                "unsafe_elevator_movement": unsafe_elevator_movement,
            },
            source_turn_id,
        )

    # Real Zendesk integration requires customer-owned credentials and policy.
    # Replace this mock by following VoiceAgent/docs/integration_zendesk.md.
    @mcp.tool()
    def mock_zendesk_create_ticket(
        call_id: CallId,
        call_token: CallToken,
        command_id: CommandId,
        issue_handle: IssueHandle,
        issue_revision: IssueRevision,
        address: Annotated[str, Field(min_length=3, max_length=300)],
        postal_code: Annotated[str, Field(min_length=3, max_length=20)],
        caller_confirmed: Annotated[
            Literal[True],
            Field(description="True only after explicit caller approval."),
        ],
    ) -> dict[str, Any]:
        """Create a persistent fictional ticket after safety clearance."""
        return service.mock_zendesk_create_ticket(
            call_id,
            call_token,
            command_id,
            issue_handle,
            issue_revision,
            address,
            postal_code,
            caller_confirmed,
        )

    # Keep the mock boundary explicit in the tool name so no customer mistakes
    # this portable example for a connection to a real Zendesk tenant.
    @mcp.tool()
    def mock_zendesk_get_ticket_status(
        call_id: CallId,
        call_token: CallToken,
        command_id: CommandId,
        issue_id: Annotated[str, Field(min_length=1, max_length=100)],
    ) -> dict[str, Any]:
        """Return caller-safe status for an exact fictional ticket ID."""
        return service.mock_zendesk_get_ticket_status(
            call_id,
            call_token,
            command_id,
            issue_id,
        )

    @mcp.tool()
    def request_human_handoff(
        call_id: CallId,
        call_token: CallToken,
        command_id: CommandId,
        reason: Literal[
            "emergency",
            "caller_requested",
            "out_of_scope",
            "address_unresolved",
            "status_unresolved",
            "safety_unresolved",
            "technical_failure",
        ],
    ) -> dict[str, Any]:
        """Record a terminal human follow-up request."""
        return service.request_human_handoff(
            call_id,
            call_token,
            command_id,
            reason,
        )

    @mcp.tool()
    def end_service_call(
        call_id: CallId,
        call_token: CallToken,
        command_id: CommandId,
    ) -> dict[str, Any]:
        """Close authoritative call state."""
        return service.end_service_call(call_id, call_token, command_id)

    @mcp.tool()
    def get_call_state(
        call_id: CallId,
        call_token: CallToken,
    ) -> dict[str, Any]:
        """Debug-only state read; Voice Agent nodes do not expose this tool."""
        return service.get_call_state(call_id, call_token)
