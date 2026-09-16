from __future__ import annotations

import logging
import time
import uuid
from typing import Annotated, Any, Awaitable, Callable

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from .auth import OtpService
from .candidates import CandidateDirectory
from .config import ServerConfig
from .data import DataStore
from .service import RoutingService
from .store import SessionStore


logger = logging.getLogger("finance_otp_officer_mcp")

SessionId = Annotated[
    str, Field(description="The session id returned by verify_caller_otp.")
]
OptionalSessionId = Annotated[
    str | None,
    Field(
        description=(
            "Omit on the first access-code attempt. After that, pass the exact "
            "session_id returned by this tool."
        )
    ),
]
OfficerId = Annotated[
    str,
    Field(
        description=(
            "The officer_id of one of the matches search_loan_officer returned. "
            "Never invent one and never use a name here."
        )
    ),
]


class _TokenASGIMiddleware:
    """Transport-safe bearer-token gate for the streamable-http app."""

    def __init__(self, app: Any, token: str) -> None:
        self._app = app
        self._expected = f"Bearer {token}".encode("utf-8")

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope.get("type") == "http":
            headers = dict(scope.get("headers") or [])
            if headers.get(b"authorization", b"") != self._expected:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send(
                    {"type": "http.response.body", "body": b'{"error":"unauthorized"}'}
                )
                return
        await self._app(scope, receive, send)


def build_service(config: ServerConfig) -> RoutingService:
    data = DataStore(config.data_dir)
    store = SessionStore(config.state_dir)
    service = RoutingService(
        data,
        store,
        max_otp_attempts=config.max_otp_attempts,
        otp_service=OtpService(
            state_dir=config.auth_dir,
            redis_url=config.otp_redis_url,
            redis_password=config.otp_redis_password,
            ttl_seconds=config.otp_ttl_seconds,
            test_access_code=config.default_access_code,
        ),
        candidate_directory=CandidateDirectory.load(config.otp_candidates_file),
    )
    # Both transports build the service here, so warming the directory here is
    # what keeps the cost off the first caller's turn on either of them.
    loaded = service.preload(config.directory_id)
    logger.info(
        "finance_officer_directory_loaded id=%s officers=%s implementation=%s",
        loaded.get("directory_id", config.directory_id),
        loaded.get("officers", "-"),
        loaded.get("implementation", "-"),
    )
    return service


def build_server(config: ServerConfig) -> FastMCP:
    """Single-pack server: the local run and the tests use this entry point."""
    mcp = FastMCP("umw-loan-intake-v3", host=config.host, port=config.port)
    register_tools(mcp, build_service(config), config)
    return mcp


def register_tools(
    mcp: FastMCP, service: RoutingService, config: ServerConfig
) -> None:
    """Attach the Finance OTP and officer tools to an MCP instance.

    Shared by the local server above and by the va-mcp host (see pack.register), so
    the func and mcp transports publish exactly the same tool surface.
    """

    def _operation_id() -> str:
        """Idempotency key. Server-side: a caller should never invent one."""
        return uuid.uuid4().hex

    def _log(name: str, session_id: str, result: dict[str, Any], started: float) -> None:
        logger.info(
            "tool=%s session=%s ok=%s version=%s ms=%.1f",
            name,
            session_id or "-",
            result.get("ok"),
            result.get("state_version", "-"),
            (time.monotonic() - started) * 1000.0,
        )

    @mcp.tool()
    def verify_caller_otp(
        otp: Annotated[
            str,
            Field(
                description=(
                    "Only the digits the caller said in their LAST turn, in the "
                    "order they said them. Do not repeat digits you already "
                    "sent: this tool remembers them. Spaces and dashes are "
                    "fine; nothing else is."
                )
            ),
        ],
        ctx: Context,
        session_id: OptionalSessionId = None,
    ) -> dict[str, Any]:
        """Check the caller's 8-digit access code and resolve their customer identity.

        Omit session_id on the first attempt: this tool opens the call record and
        returns the new session_id in the same result. Reuse that exact session_id
        for every later OTP fragment, retry, and business tool.

        This tool keeps the digits from earlier turns, so a code read out in
        pieces is assembled here and not by you. Send only what you just heard.
        Until eight digits have arrived it returns access_code_incomplete with
        digits_collected and digits_missing, and that costs no attempt. Once
        eight have arrived it returns authenticated true or false plus
        attempts_remaining. A successful result includes the authoritative
        fictional customer profile and indicative lending attributes bound to
        that code; never infer or alter those attributes yourself.
        """
        started = time.monotonic()
        operation_id = _operation_id()
        mcp_session = ctx.session
        bound_session_id = (
            getattr(mcp_session, "_finance_business_session_id", None)
            if mcp_session is not None
            else None
        )
        effective_session_id = session_id or bound_session_id
        if effective_session_id:
            result = service.verify_caller_otp(
                effective_session_id, operation_id, otp
            )
        else:
            result = service.start_and_verify_caller_otp(
                config.caller_id,
                config.directory_id,
                operation_id,
                otp,
                config.routing_persona_ref,
            )
        returned_session_id = str(
            result.get("session_id") or effective_session_id or ""
        )
        if result.get("authenticated"):
            if hasattr(mcp_session, "_finance_business_session_id"):
                delattr(mcp_session, "_finance_business_session_id")
        elif returned_session_id:
            setattr(
                mcp_session,
                "_finance_business_session_id",
                returned_session_id,
            )
        _log(
            "verify_caller_otp",
            returned_session_id,
            result,
            started,
        )
        return result

    @mcp.tool()
    def calculate_loan_offer(
        session_id: SessionId,
        amount_usd: Annotated[
            int | None,
            Field(
                description=(
                    "The caller-confirmed requested loan amount in whole US "
                    "dollars. Omit when they do not know; the authenticated "
                    "profile's indicative maximum becomes the starting amount."
                )
            ),
        ] = None,
        term_months: Annotated[
            int,
            Field(
                description=(
                    "Repayment term in months, from 12 through 360 in 12-month "
                    "increments. One-year through 30-year terms are supported."
                )
            ),
        ] = 360,
        requested_rate_percent: Annotated[
            float | None,
            Field(
                description=(
                    "The exact annual percentage rate the caller is arguing "
                    "for. Omit for the starting offer."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Calculate or renegotiate the current indicative loan offer.

        Pricing uses three amount bands, the OTP-authenticated customer's credit
        tier, and a simple term adjustment. Call again whenever the caller
        changes an amount or term, or counters with a specific rate. The result
        says whether further reduction is possible without revealing the
        internal floor. It records an offer, not acceptance.
        """
        started = time.monotonic()
        result = service.calculate_loan_offer(
            session_id,
            _operation_id(),
            amount_usd,
            term_months,
            requested_rate_percent,
        )
        _log("calculate_loan_offer", session_id, result, started)
        return result

    @mcp.tool()
    def record_loan_interest(
        session_id: SessionId,
        outcome: Annotated[
            str,
            Field(
                description=(
                    "interested only after a settled offer was read back and "
                    "the caller explicitly said 'I accept'; "
                    "declined only after an explicit refusal."
                )
            ),
        ],
        product: Annotated[
            str,
            Field(
                description=(
                    "One of home_purchase, refinance, home_equity, "
                    "investment_property, other, or unspecified."
                )
            ),
        ],
        timeline: Annotated[
            str,
            Field(
                description=(
                    "One of immediately, within_3_months, within_6_months, "
                    "more_than_6_months, researching, or unspecified."
                )
            ),
        ],
        spoken_words: Annotated[
            str,
            Field(
                description=(
                    "The caller's exact final words. Positive acceptance must be "
                    "'I accept'. A bare yes, interest statement, question, or "
                    "objection is not acceptance."
                )
            ),
        ],
        requested_amount_usd: Annotated[
            int | None,
            Field(
                description=(
                    "The requested total loan amount in whole US dollars. Leave "
                    "it out when the caller did not provide a figure."
                )
            ),
        ] = None,
        notes: Annotated[
            str,
            Field(
                description=(
                    "A short factual note about the caller's stated needs or "
                    "objections. Do not infer protected or financial attributes."
                )
            ),
        ] = "",
    ) -> dict[str, Any]:
        """Record the authenticated caller's explicit loan interest decision.

        Use this only after calculate_loan_offer returned the settled offer and
        every concern was resolved. Positive interest requires the exact phrase
        "I accept" and unlocks officer search; a decline does not.
        """
        started = time.monotonic()
        result = service.record_loan_interest(
            session_id,
            _operation_id(),
            outcome,
            product,
            requested_amount_usd,
            timeline,
            spoken_words,
            notes,
        )
        _log("record_loan_interest", session_id, result, started)
        return result

    @mcp.tool()
    def auto_assign_loan_officer(session_id: SessionId) -> dict[str, Any]:
        """Assign one available loan officer when the caller has no preference.

        Requires an authenticated caller and an accepted offer. Returns one
        officer from the directory and makes that officer eligible for the
        normal read-back and confirm_loan_officer gate.
        """
        started = time.monotonic()
        result = service.auto_assign_loan_officer(
            session_id, _operation_id()
        )
        _log("auto_assign_loan_officer", session_id, result, started)
        return result

    @mcp.tool()
    def search_loan_officer(
        session_id: SessionId,
        spoken_name: Annotated[
            str,
            Field(
                description=(
                    "The loan officer's name exactly as the caller said it. Pass "
                    "what you heard, not a corrected or completed version."
                )
            ),
        ],
        also_heard: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Up to two OTHER ways the same name could be written, when "
                    "you are unsure what you heard. They must be genuinely "
                    "different guesses at the sound, like 'Ragavan', 'Raghavan', "
                    "'rug of on' — not the same guess respelled. Leave this out "
                    "when you heard the name clearly; a wrong guess in here "
                    "costs accuracy."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Run the sample's fake random search over fictional loan officers.

        The directory is matched on pronunciation, not spelling, so a name the
        recogniser wrote as ordinary English words ("bon fee glee oh") still
        finds its row. Give the alternates in also_heard only when they are real
        alternatives; the search fuses their rankings and returns the best three.

        status is one_match, multiple_matches or no_match, and it — not your own
        reading of the list — decides what happens next: one_match may be
        confirmed, multiple_matches must be narrowed with the caller first, and
        no_match means there is nobody to name. Requires an authenticated caller.
        """
        started = time.monotonic()
        result = service.search_loan_officer(
            session_id, _operation_id(), spoken_name, also_heard
        )
        _log("search_loan_officer", session_id, result, started)
        return result

    @mcp.tool()
    def confirm_loan_officer(
        session_id: SessionId, officer_id: OfficerId
    ) -> dict[str, Any]:
        """Record that the caller heard this officer's name and title read back and
        agreed it is the right person. Only an officer_id from the most recent
        search is accepted. This unlocks the officer callback disposition."""
        started = time.monotonic()
        result = service.confirm_loan_officer(session_id, _operation_id(), officer_id)
        _log("confirm_loan_officer", session_id, result, started)
        return result

    @mcp.tool()
    def end_call(
        reason: Annotated[
            str,
            Field(
                description=(
                    "Why the call ended, as one of: caller_hung_up, "
                    "authentication_failed, officer_not_found, caller_declined, "
                    "officer_callback_requested, other."
                )
            ),
        ],
        session_id: OptionalSessionId = None,
    ) -> dict[str, Any]:
        """Close a call that is not being transferred, and record why. Every call
        that does not end in a transfer has to end here, or it has no outcome on
        record at all. For officer_callback_requested, the result includes the
        accepted offer and confirmed officer that must be used for the final
        spoken recap. This tool records the business outcome but does not close
        the Voice Agent transport; the caller or client owns connection closure.
        Omit session_id only when the caller ends before the first access-code
        attempt."""
        started = time.monotonic()
        operation_id = _operation_id()
        if session_id:
            result = service.end_call(session_id, operation_id, reason)
        else:
            result = service.start_and_end_call(
                config.caller_id,
                config.directory_id,
                operation_id,
                reason,
                config.routing_persona_ref,
            )
        _log(
            "end_call",
            str(result.get("session_id") or session_id or ""),
            result,
            started,
        )
        return result

    @mcp.tool()
    def get_call_state(session_id: SessionId) -> dict[str, Any]:
        """Return the raw routing state for the session."""
        return service.get_call_state(session_id)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = ServerConfig.from_environment()
    mcp = build_server(config)

    logger.info(
        "finance_otp_officer_mcp_start host=%s port=%s path=/mcp token=%s data_dir=%s state_dir=%s",
        config.host,
        config.port,
        "on" if config.token else "off",
        config.data_dir,
        config.state_dir or "-",
    )

    if config.token:
        import uvicorn

        app = _TokenASGIMiddleware(mcp.streamable_http_app(), config.token)
        uvicorn.run(app, host=config.host, port=config.port, log_level="info")
        return 0

    mcp.run("streamable-http")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
