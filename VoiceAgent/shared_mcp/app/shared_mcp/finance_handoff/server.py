from __future__ import annotations

import logging
import time
import uuid
from typing import Annotated, Any, Awaitable, Callable

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .config import ServerConfig
from .data import DataStore
from .domain import DISPOSITIONS
from .officers import OfficerCatalog
from .service import FinanceService
from .store import CallStore


logger = logging.getLogger("finance_mcp")

CallId = Annotated[str, Field(description="The call id returned by start_call.")]


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
                await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
                return
        await self._app(scope, receive, send)


def build_service(config: ServerConfig) -> FinanceService:
    return FinanceService(
        DataStore(config.data_dir),
        CallStore(config.state_dir),
        OfficerCatalog.from_environment(),
    )


def build_server(config: ServerConfig) -> FastMCP:
    """Single-pack server: the local run and the tests use this entry point."""
    mcp = FastMCP("finance-outbound", host=config.host, port=config.port)
    register_tools(mcp, build_service(config), config)
    return mcp


def register_tools(
    mcp: FastMCP, service: FinanceService, config: ServerConfig
) -> None:
    """The only place a finance tool is declared.

    `build_server` uses it for the local func-transport server; `pack.py` uses it
    to mount the same tools on the shared va-mcp host. One registration means the
    two transports can never drift apart.
    """

    def _operation_id() -> str:
        """Idempotency key. Server-side: a caller should never invent one."""
        return uuid.uuid4().hex

    def _log(name: str, call_id: str, result: dict[str, Any], started: float) -> None:
        logger.info(
            "tool=%s call=%s ok=%s error=%s version=%s ms=%.1f",
            name,
            call_id or "-",
            result.get("ok"),
            result.get("error", "-"),
            result.get("state_version", "-"),
            (time.monotonic() - started) * 1000.0,
        )

    # ---------------------------------------------------------------- stage 0

    @mcp.tool()
    def start_call() -> dict[str, Any]:
        """Open the outbound call record. Call once, before anything else.
        Returns the call_id every later tool needs, plus the first name of the
        person being called and what this campaign is offering."""
        started = time.monotonic()
        result = service.start_call(
            config.lead_id,
            config.campaign_id,
            config.ivr_menu_id,
            _operation_id(),
            config.agent_persona_ref,
        )
        _log("start_call", result.get("call_id", ""), result, started)
        return result

    @mcp.tool()
    def send_dtmf(
        call_id: CallId,
        digits: Annotated[
            str,
            Field(description="The keypad option to press, for example 2 or 0."),
        ],
    ) -> dict[str, Any]:
        """Send one keypad option to the automated phone menu. Success confirms
        only that the configured adapter accepted the key; classify the audio
        heard after the press to determine whether another menu, a person, or
        voicemail answered."""
        started = time.monotonic()
        result = service.send_dtmf(call_id, _operation_id(), digits)
        _log("send_dtmf", call_id, result, started)
        return result

    @mcp.tool()
    def leave_voicemail(
        call_id: CallId,
        message_summary: Annotated[
            str,
            Field(description="A short summary of the message you just left."),
        ],
    ) -> dict[str, Any]:
        """Record that a voicemail message has been left. Only valid when a
        recorded greeting was heard after the menu or initial pickup."""
        started = time.monotonic()
        result = service.leave_voicemail(call_id, _operation_id(), message_summary)
        _log("leave_voicemail", call_id, result, started)
        return result

    # -------------------------------------------------------------- stage 1-3

    @mcp.tool()
    def confirm_right_party(
        call_id: CallId,
        date_of_birth: Annotated[
            str,
            Field(
                description=(
                    "The date of birth they just said, in their own words, for "
                    "example '1 January' or '1990-01-01'. A day and a month is "
                    "enough. Pass an empty string only when they say it is not "
                    "them or refuse to give it."
                )
            ),
        ],
    ) -> dict[str, Any]:
        """Check the person on the line against the borrower being called. Returns
        confirmed true or false; never decide identity yourself. Nothing about the
        account may be said until it returns confirmed true."""
        started = time.monotonic()
        result = service.confirm_right_party(call_id, _operation_id(), date_of_birth)
        _log("confirm_right_party", call_id, result, started)
        return result

    @mcp.tool()
    def record_disclosure(
        call_id: CallId,
        spoken_words: Annotated[
            str,
            Field(
                description=(
                    "The customer's exact answer to the disclosure question. A "
                    "standalone bye or goodbye is ambiguous, and bare yes or yeah "
                    "is not confirmation. Natural Hindi equivalents of an explicit "
                    "confirmation or refusal are accepted."
                )
            ),
        ],
    ) -> dict[str, Any]:
        """Record a clear decision after the purpose and recording disclosure.
        The backend, not the Agent, classifies the exact words as explicit yes,
        explicit no, or unclear. Ambiguous farewells are rejected so the Agent
        must confirm end intent."""
        started = time.monotonic()
        result = service.record_disclosure(call_id, _operation_id(), spoken_words)
        _log("record_disclosure", call_id, result, started)
        return result

    # ------------------------------------------------------------- the offer

    @mcp.tool()
    def calculate_indicative_loan_offer(
        call_id: CallId,
        amount_inr: Annotated[
            int | None,
            Field(
                description=(
                    "How much they want, in whole rupees. Five lakh is 500000. "
                    "Leave it out to price the amount they are pre-approved for."
                )
            ),
        ] = None,        tenure_months: Annotated[
            int | None,
            Field(description="How long they want to repay over, in months. Two years is 24."),
        ] = None,
        monthly_income_inr: Annotated[
            int | None,
            Field(description="What they earn in a month, in whole rupees."),
        ] = None,
        collateral_value_inr: Annotated[
            int | None,
            Field(
                description=(
                    "What the security they are putting up is worth, in whole "
                    "rupees. 0 if they have none."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Work out the indicative loan offer from whatever figures you have so
        far, and say what would change the answer. Call it with nothing to get a
        complete starting illustration: the pre-approved amount, default period,
        rate and estimated monthly instalment. The default period is not the
        customer's choice until they confirm it; call the tool again with that
        period or another one they choose. Call it again with any figure they
        argue for. It records no decision, so calling it repeatedly is expected
        and the last figure sent always wins.

        `need` lists what is still required before a firm offer can be worked
        out: ask for exactly those, nothing else. When `need` is empty it returns
        either an indicative offer with the amount, period, rate and monthly
        instalment, or `eligible` false with a reason that can be said out loud.
        Either way it returns how far each single figure could move with the
        others left alone, which is what a complaint about the rate is answered
        with. A figure it cannot use is rejected by name, so a misheard number
        never gets priced."""
        started = time.monotonic()
        result = service.calculate_indicative_loan_offer(
            call_id,
            _operation_id(),
            amount_inr,
            tenure_months,
            monthly_income_inr,
            collateral_value_inr,
        )
        _log("calculate_indicative_loan_offer", call_id, result, started)
        return result

    @mcp.tool()
    def record_customer_offer_decision(
        call_id: CallId,
        spoken_words: Annotated[
            str,
            Field(
                description=(
                    "The customer's exact answer to the final offer question. "
                    "Interest, questions, objections and counter-offers are not "
                    "acceptance or decline. Natural Hindi equivalents of explicit "
                    "acceptance or decline are accepted."
                )
            ),
        ],
        note: Annotated[
            str, Field(description="In their words, why. Empty if they accepted.")
        ] = "",
    ) -> dict[str, Any]:
        """Record what the customer decided about the offer they were read out.
        The backend, not the Agent, classifies the exact words as accepted,
        declined, or unclear. Never call it in the same turn as the figures you
        just read out. Arguing about a figure is not a decision: send that figure
        to calculate_indicative_loan_offer instead. Accepting is refused until an
        offer has actually been worked out."""
        started = time.monotonic()
        result = service.record_customer_offer_decision(
            call_id, _operation_id(), spoken_words, note
        )
        _log("record_customer_offer_decision", call_id, result, started)
        return result

    # ------------------------------------------------------------- stage 3

    @mcp.tool()
    def present_charges(call_id: CallId) -> dict[str, Any]:
        """Record that charges were presented and return the applicable processing
        fee, insurance premium, total taken up front, and customer-safe
        explanation. Use it once before the fixed disclosure and never work a fee
        out yourself."""
        return service.present_charges(call_id)

    @mcp.tool()
    def record_charges_response(
        call_id: CallId,
        spoken_words: Annotated[
            str,
            Field(
                description=(
                    "The customer's exact answer to whether they accept the "
                    "charges. A question or request to reduce a fee is not an "
                    "acceptance or rejection. Natural Hindi equivalents of explicit "
                    "acceptance or rejection are accepted."
                )
            ),
        ],
    ) -> dict[str, Any]:
        """Record a clear acceptance or rejection after the charges were explained.
        The backend derives the decision from the exact words. Questions,
        objections and negotiation requests are rejected as ambiguous."""
        started = time.monotonic()
        result = service.record_charges_response(
            call_id, _operation_id(), spoken_words
        )
        _log("record_charges_response", call_id, result, started)
        return result

    # ---------------------------------------------------------------- stage 4

    @mcp.tool()
    def capture_bureau_consent(
        call_id: CallId,
        spoken_words: Annotated[
            str,
            Field(
                description=(
                    "Exactly what the customer said, word for word. This is the "
                    "audit record of their consent, so never paraphrase it."
                )
            ),
        ],
    ) -> dict[str, Any]:
        """Record the customer's consent to a credit bureau check. A noise, a
        filler or a pause is classified as unclear and rejected here. The backend
        alone derives consent or refusal from an answer that would stand up on a
        recording."""
        started = time.monotonic()
        result = service.capture_bureau_consent(
            call_id, _operation_id(), spoken_words
        )
        _log("capture_bureau_consent", call_id, result, started)
        return result

    # -------------------------------------------------------- officer transfer

    @mcp.tool()
    def search_loan_officer(
        call_id: CallId,
        spoken_name: Annotated[
            str,
            Field(
                description=(
                    "The loan officer's name exactly as the customer said it. "
                    "Pass what you heard, not a corrected or completed version."
                )
            ),
        ],
        also_heard: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Up to two genuinely different readings of the same spoken "
                    "name when you are unsure what you heard. Omit when clear."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Search the same UWM loan-officer directory used by the inbound routing
        agent. Results contain public names, titles, branches, and availability."""
        started = time.monotonic()
        result = service.search_loan_officer(
            call_id, _operation_id(), spoken_name, also_heard
        )
        _log("search_loan_officer", call_id, result, started)
        return result

    @mcp.tool()
    def confirm_loan_officer(
        call_id: CallId,
        officer_id: Annotated[
            str,
            Field(description="The officer_id from the most recent search result."),
        ],
    ) -> dict[str, Any]:
        """Record the customer's choice after you read the officer's name and title
        back. Only an available officer from the latest search can be selected."""
        started = time.monotonic()
        result = service.confirm_loan_officer(
            call_id, _operation_id(), officer_id
        )
        _log("confirm_loan_officer", call_id, result, started)
        return result

    @mcp.tool()
    def auto_assign_loan_officer(call_id: CallId) -> dict[str, Any]:
        """Select an available officer when the customer asks not to choose one.
        Returns the assigned officer's public name, title, and branch."""
        started = time.monotonic()
        result = service.auto_assign_loan_officer(call_id, _operation_id())
        _log("auto_assign_loan_officer", call_id, result, started)
        return result

    @mcp.tool()
    def transfer_to_loan_officer(
        call_id: CallId,
        reason: Annotated[
            str, Field(description="Why this call is being handed over now.")
        ],
    ) -> dict[str, Any]:
        """Hand the call to the selected loan officer and close it as transferred.
        Requires recorded credit-bureau consent and either a confirmed search
        result or an automatic assignment."""
        started = time.monotonic()
        result = service.transfer_to_loan_officer(call_id, _operation_id(), reason)
        _log("transfer_to_loan_officer", call_id, result, started)
        return result

    # ---------------------------------------------------------------- wrap up

    @mcp.tool()
    def schedule_callback(
        call_id: CallId,
        when_text: Annotated[
            str,
            Field(description="The agreed appointment time, in the customer's own words."),
        ],
        meeting_type: Annotated[
            str,
            Field(description="Use phone or onsite, exactly as the customer chose."),
        ] = "phone",
        location: Annotated[
            str,
            Field(
                description=(
                    "The agreed location for an onsite meeting. Leave empty for a "
                    "phone appointment."
                )
            ),
        ] = "",
    ) -> dict[str, Any]:
        """Schedule a phone or onsite meeting with an available loan officer after
        a qualified sale. A qualified result exposes one customer-safe
        spoken_summary rather than the raw offer fields. Before qualification,
        this records a requested phone callback only."""
        started = time.monotonic()
        result = service.schedule_callback(
            call_id,
            _operation_id(),
            when_text,
            meeting_type,
            location,
        )
        _log("schedule_callback", call_id, result, started)
        return result

    @mcp.tool()
    def set_disposition(
        call_id: CallId,
        code: Annotated[
            str,
            Field(
                description="How this call ended. Use exactly one of: "
                + ", ".join(DISPOSITIONS)
                + "."
            ),
        ],
        note: Annotated[str, Field(description="One line of context, in their words.")],
        spoken_words: Annotated[
            str,
            Field(
                description=(
                    "Exact words that explicitly requested ending the call. "
                    "Required for customer_ended; omit for other outcomes."
                )
            ),
        ] = "",
    ) -> dict[str, Any]:
        """Close the call with its outcome. Every call must end with one; a call
        with no outcome recorded cannot be followed up."""
        started = time.monotonic()
        result = service.set_disposition(
            call_id, _operation_id(), code, note, spoken_words
        )
        _log("set_disposition", call_id, result, started)
        return result

    @mcp.tool()
    def get_call_state(call_id: CallId) -> dict[str, Any]:
        """Return the raw recorded state of the call."""
        return service.get_call_state(call_id)

    @mcp.tool()
    def prepare_offer_summary(call_id: CallId) -> dict[str, Any]:
        """Return only the accepted offer and booked officer appointment for the
        final spoken recap. After this succeeds, the next response must speak every
        returned offer and appointment field before handoff; handoff cannot be the
        first output item."""
        started = time.monotonic()
        result = service.prepare_offer_summary(call_id)
        _log("prepare_offer_summary", call_id, result, started)
        return result


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = ServerConfig.from_environment()
    mcp = build_server(config)

    logger.info(
        "finance_mcp_start host=%s port=%s path=/mcp token=%s data_dir=%s state_dir=%s lead=%s campaign=%s",
        config.host,
        config.port,
        "on" if config.token else "off",
        config.data_dir,
        config.state_dir or "-",
        config.lead_id,
        config.campaign_id,
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
