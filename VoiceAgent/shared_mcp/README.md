# Shared Finance MCP source

This directory contains the single Docker image and the two isolated MCP
business packs used by the Finance examples:

- `/mcp/finance-handoff`
- `/mcp/finance-otp-officer`

For startup, local hosting, Azure deployment, configuration, and modification
instructions, use [02: MCP settings](../docs/02_mcp_settings.md).

For the complete execution order, use
[03: Start and run the samples](../docs/03_run_samples.md).

For any Project connection, MCP authentication, missing tool call, or
post-tool response failure, use the shared
[`debug-local-session` Skill](../skills/debug-local-session/) and start with:

```bash
cd VoiceAgent
./scripts/manage-local-finance-mcp-and-ui.sh status
python skills/debug-local-session/scripts/analyze_session.py --list
```
