# Voice Agent sample debug system map

## Read this when

Use this reference for Project, model deployment, Agent publication,
RemoteTool connection, MCP deployment, Local UI, or cross-layer failures.

## Runtime topology

This reference covers only the customer-facing sample Local UI and its
official Foundry path.

```text
browser
  |
  | localhost / forwarded Local UI port
  v
Local UI Python server
  |-- Azure identity: lists Projects and publishes Agent versions
  |-- Voice WebSocket proxy + session recorder
  |
  v
selected Foundry Project
  |-- immutable Voice Agent version
  |     |-- model_type + model deployment
  |     |-- MCP server_url
  |     +-- project_connection_id
  |
  +-- RemoteTool connection
          |-- target: public MCP route
          +-- CustomKeys Authorization bearer credential
                    |
                    v
          local deployment:
            Docker :18003 -> named Dev Tunnel
          or Azure deployment:
            Container App HTTPS ingress
                    |
                    v
          shared MCP image
            |-- /mcp/finance-handoff
            +-- /mcp/finance-otp-officer
```

The browser never receives the MCP token. Foundry invokes MCP using the
credential stored in the Project connection.

## Project and Agent ownership

The repository does not hardcode one customer Project. Resolve the actual
Project from:

1. `meta.json` `backend` and `upstream` for an existing session;
2. the Project selected in the Local UI;
3. `AZURE_AI_PROJECT_ENDPOINT` in each sample and Local UI `.env`.

The two sample `.env` files should normally target the same Project used by the
UI. The Local UI may switch Projects and upsert the fixed connection there
before template publication, so never assume a connection created for one
Project exists in another.

Agent publication is immutable:

- Example 1 source: `samples/example1_finance_with_handoff/agent.json`
- Example 2 source:
  `samples/example2_finance_with_OTP_and_Officer_Search/agent.json`
- CLI publication: each example's `sample.py`
- UI publication: `samples/local_UI/app.py`

`sample.py check` verifies the current active version against materialized
source settings. A matching Agent name does not prove a matching version.

## Model deployment relationship

The Python wire contract uses:

```json
{
  "model_type": "managed",
  "model": "gpt-realtime"
}
```

`managed` means the Voice Agent service owns model resolution. Do not use an
account deployment list as proof for this mode. Publication errors stating
that the managed model is unsupported belong to Project region/subscription
eligibility, not MCP.

## MCP route relationship

One image contains two isolated tool inventories:

| Example | Route | Typical local connection |
| --- | --- | --- |
| Finance with Handoff | `/mcp/finance-handoff` | `finance-handoff-local-e2e` |
| Finance with OTP and Officer Search | `/mcp/finance-otp-officer` | `finance-otp-officer-local-e2e` |

Some tools share names but have different schemas, so route correctness matters
even when `tools/list` succeeds.

Generated configuration:

- Local: `shared_mcp/config/generated/example1.local.env` and
  `example2.local.env`
- Azure: `example1.shared.env` and `example2.shared.env`

Each file contains only route URL and connection name. Local bearer state is
under `shared_mcp/state/local/token`; do not print, commit, or paste it.

## Local process ownership

`scripts/setup-local-examples.sh` prepares dependencies, builds the UI,
and creates local `.env` files.

`scripts/manage-local-mcp-and-ui.sh` manages the runtime:

- MCP Docker container;
- named Dev Tunnel host;
- Local UI process;
- template MCP readiness checks.

State and logs:

```text
.local-mcp-and-ui/
  mcp.pid
  mcp.log
  local-ui.pid
  local-ui.log
```

The lower-level `shared_mcp/scripts/e2e-local.sh` starts only the MCP path and
leaves its tunnel host running.

## Evidence by boundary

| Boundary | Evidence |
| --- | --- |
| Local dependencies/auth | `setup-local-examples.sh --check` |
| MCP/UI processes | `manage-local-mcp-and-ui.sh status`, state logs |
| Local MCP process | `http://127.0.0.1:18003/healthz`, Docker status |
| Public MCP/auth/tools | Local UI template probe JSON; authenticated HTTP 200 |
| Project selection | UI config/cookie, session `meta.json`, sample `.env` |
| Model deployment | account deployment list, `model_type`, exact `model` |
| Agent publication | `sample.py publish/check`, version and fingerprints |
| Connection materialization | published definition and Project connection target |
| Voice session | `meta.json`, `timeline.log`, `events.jsonl` |
| Foundry internal service | `conv_*` with `samples/download_conversation_traces.py` |
| MCP business execution | MCP item/tool ID, MCP log, persisted sample state |

## Read-only control commands

Run from `VoiceAgent/`. These commands do not print the MCP bearer token.

```bash
# Local processes and their configured Local UI URL.
./scripts/manage-local-mcp-and-ui.sh status

# Dependency, environment, and authentication readiness.
./scripts/setup-local-examples.sh --check

# Local MCP health.
curl -fsS http://127.0.0.1:18003/healthz

# Use the Local UI URL printed by the status command.
curl -fsS http://127.0.0.1:18098/healthz
curl -fsS \
  http://127.0.0.1:18098/api/templates/finance-example/mcp/probe
curl -fsS \
  http://127.0.0.1:18098/api/templates/finance-with-otp-and-officer-search/mcp/probe
```

Verify the published Agent version using the same materialized settings:

```bash
cd samples/example1_finance_with_handoff
python sample.py check

cd ../example2_finance_with_OTP_and_Officer_Search
python sample.py check
```

Inspect Project connection metadata without requesting credentials:

```bash
PROJECT_HOST="${AZURE_AI_PROJECT_ENDPOINT#https://}"
PROJECT_HOST="${PROJECT_HOST%%/*}"
ACCOUNT_NAME="${PROJECT_HOST%%.*}"
PROJECT_NAME="${AZURE_AI_PROJECT_ENDPOINT##*/}"
PROJECT_RESOURCE_ID="$(
  az resource list \
    --resource-type Microsoft.CognitiveServices/accounts/projects \
    --query "[?name=='${ACCOUNT_NAME}/${PROJECT_NAME}'].id | [0]" \
    --output tsv
)"
ACCOUNT_RESOURCE_ID="${PROJECT_RESOURCE_ID%/projects/*}"
az rest \
  --method get \
  --url "https://management.azure.com${ACCOUNT_RESOURCE_ID}/connections?api-version=2025-04-01-preview" \
  --query "value[].{name:name,category:properties.category,target:properties.target}" \
  --output table
```

## Fault-domain rule

Find the first boundary without expected evidence. Do not:

- change prompts when MCP authentication fails;
- redeploy MCP when model validation rejects publication;
- blame MCP when no tool call left Foundry;
- blame Foundry when MCP received the call and returned a business error;
- restart before preserving run/session/conversation/tool IDs.

When an MCP call appears in Foundry trace but not in MCP logs, first prove the
MCP endpoint was alive in the same time window. When `execute_tool` is followed
by no second `chat`, distinguish a missing tool result from a completed tool
whose response continuation failed.
