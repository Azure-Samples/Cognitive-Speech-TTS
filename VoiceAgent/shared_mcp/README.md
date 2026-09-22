# Shared Voice Agent MCP source

This directory contains one native Python MCP server with three isolated
business packs used by the customer-facing examples:

- `/mcp/finance-handoff`
- `/mcp/finance-otp-officer`
- `/mcp/elevator-service`

Every Portal example uses a `managed` connection. A customer may create a new
Foundry Project, run or deploy this server, and let the Portal create the
required RemoteTool connections in that Project. No example depends on a
connection pre-created in a Microsoft test Project.

The elevator-service route exposes explicitly named
`mock_zendesk_create_ticket` and `mock_zendesk_get_ticket_status` tools backed
by replica-local filesystem-backed fictional data. It never contacts a real
Zendesk tenant, and Azure Container Apps restarts or revisions can reset that
data.
Customers who need a real adapter should preserve the `ZendeskBackend`
contract and follow the
[Zendesk integration guide](../docs/integration_zendesk.md).

The local runtime is always native Python plus Dev Tunnel. Local setup, E2E,
and lifecycle scripts do not require or invoke Docker. The separate
`scripts/package.sh` command remains available only for explicitly building
and testing the optional container image; Azure Container Apps deployment uses
the remote build configured in `azure.yaml`.

For the normal portal + local MCP workflow, run from `VoiceAgent/`:

```bash
./scripts/setup-local-examples.sh \
	--project-endpoint "https://<account>.services.ai.azure.com/api/projects/<project>"
./scripts/login-devtunnel.sh
./scripts/setup-local-examples.sh --check
./scripts/manage-local-mcp-and-ui.sh restart
```

The login wrapper uses GitHub device-code authentication. Do not start
`e2e-local.sh` separately when the manager owns the stack.

For startup, local hosting, Azure deployment, configuration, and modification
instructions, use [02: MCP settings](../docs/02_mcp_settings.md).

For the complete execution order, use
[03: Start and run the samples](../docs/03_run_samples.md).

For any Project connection, MCP authentication, missing tool call, or
post-tool response failure, use the shared
[`debug-local-session` Skill](../skills/debug-local-session/) and start with:

```bash
cd VoiceAgent
./scripts/manage-local-mcp-and-ui.sh status
python skills/debug-local-session/scripts/analyze_session.py --list
```
