# Integrating a real Zendesk backend

## Conclusion

Example 3 intentionally uses a replica-local filesystem-backed mock Zendesk
backend. It creates and queries fictional tickets without requiring a Zendesk
tenant, Azure Logic App, OAuth consent, API token, or customer cloud resources.

The mock is a portability boundary, not a production Zendesk integration.
Customers who need real tickets must replace the backend behind the existing
MCP business policy rather than adding Zendesk credentials to the Agent.

## Current example behavior

The portable flow is:

```text
Example 3 Voice Agent
  -> shared_mcp /mcp/elevator-service
  -> mock_zendesk_create_ticket
     or mock_zendesk_get_ticket_status
  -> replica-local fictional ticket store
```

The mock implementation is
[`MockZendeskBackend`](../shared_mcp/app/shared_mcp/elevator_service/tickets.py).
Its state uses `ELEVATOR_MCP_STATE_DIR` and survives a native MCP process
restart while that directory remains. The Azure deployment currently places
it under `/tmp`, so Container Apps replica or revision replacement can reset
created tickets. The committed fixture includes a fictional ticket that can be
queried without creating customer data.

Tool results contain:

```json
{
  "ticket_id": "1001",
  "subject": "Elevator service request: ...",
  "status": "new",
  "priority": "normal",
  "updated_at": "",
  "estimated_visit": "Within 4 demo hours",
  "backend": "mock_zendesk"
}
```

No code in the default example calls a real Zendesk endpoint.

## Replacement contract

A real implementation should implement the `ZendeskBackend` protocol in
[`tickets.py`](../shared_mcp/app/shared_mcp/elevator_service/tickets.py):

```python
class ZendeskBackend(Protocol):
    def create(
        self,
        business_key: str,
        summary: str,
        address: str,
        postal_code: str,
    ) -> dict[str, str]: ...

    def get(self, ticket_id: str) -> dict[str, str] | None: ...
```

Inject the replacement in
[`build_service`](../shared_mcp/app/shared_mcp/elevator_service/server.py).
Do not change the Agent's safety, confirmation, handoff, or idempotency flow
merely to connect another ticket provider.

After a real adapter is implemented, rename the two `mock_zendesk_*` MCP tools
only when the Agent definition, tests, documentation, and published Agent are
updated together. The explicit mock names prevent a customer from mistaking
the default example for a live integration.

## Supported architecture choices

Two common production designs are:

```text
shared_mcp -> customer-owned adapter -> Zendesk REST API
```

or:

```text
shared_mcp
  -> customer-owned Logic App workflow
  -> Microsoft.Web/connections/zendesk
  -> Zendesk
```

The direct adapter is operationally smaller but makes the customer responsible
for OAuth storage, refresh, rotation, revocation, and tenant binding. The Logic
App design keeps Zendesk OAuth in the managed Zendesk connection but requires
the customer to provision and operate the workflow and complete Zendesk OAuth
consent.

Do not copy URLs, connection IDs, identities, tokens, tenants, or resource
names from a Microsoft test environment.

## Security requirements

A production adapter must:

1. keep credentials out of `agent.json`, prompts, tool schemas, logs, and
   source code;
2. use a dedicated least-privilege Zendesk integration identity;
3. preserve explicit caller confirmation before ticket creation;
4. preserve the business idempotency key and avoid automatic write retries
   after an unknown outcome;
5. authorize the caller against the requested customer, site, and ticket;
6. return only caller-safe fields;
7. enforce bounded timeouts and reject redirects to unapproved hosts;
8. fail startup when production configuration is incomplete instead of
   silently falling back to the mock.

Service authentication proves only that the adapter may call Zendesk. It does
not prove that a telephone caller may read or modify a ticket.

## Caller-safe response

The Agent may receive only the fields it needs to speak:

- ticket ID;
- subject;
- status;
- priority;
- updated time;
- an approved estimated visit value.

Do not expose requester, submitter, assignee, email, phone, comments,
attachments, organizations, private descriptions, unrestricted custom fields,
or internal URLs without an explicit business requirement and authorization
review.

## Validation checklist

Before describing a replacement as connected to Zendesk, verify:

1. unit tests for request mapping, response filtering, timeout, authentication,
   and error handling;
2. a read-only request against a marked test ticket;
3. one explicitly approved write with a recognizable test subject;
4. the ticket remains readable after MCP restart;
5. duplicate create requests do not create duplicate tickets;
6. unknown write outcomes require reconciliation instead of retry;
7. the MCP tool inventory matches the updated Agent definition;
8. browser and telephony journeys preserve safety and confirmation gates;
9. Zendesk audit identifies the approved customer integration identity.

Until caller authorization and the complete live journey are proven, describe
the result as a Zendesk transport integration rather than production-ready
customer authorization.
