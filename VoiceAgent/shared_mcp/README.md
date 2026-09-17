# Shared Finance MCP source

This directory contains one native Python MCP server with two isolated business
packs used by the Finance examples:

- `/mcp/finance-handoff`
- `/mcp/finance-otp-officer`

The local runtime is always native Python plus Dev Tunnel. Local setup, E2E,
and lifecycle scripts do not require or invoke Docker. The separate
`scripts/package.sh` command remains available only for explicitly building
and testing the optional container image; Azure Container Apps deployment uses
the remote build configured in `azure.yaml`.

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
