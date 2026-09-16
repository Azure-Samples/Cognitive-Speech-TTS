# Shared MCP Deployment Plan

Status: Ready for Validation

## Goal

Add a customer-owned shared MCP service under `VoiceAgent/shared_mcp` for the two
Finance Voice Agent samples. Package it as a container, provide one-command
local packaging and Azure deployment, and let each Agent select this shared
endpoint through configuration.

## Scope

- Analyze the two sample Agent definitions and their shared SDK configuration.
- Reuse the existing Finance and OTP/officer-search business behavior.
- Replace the complex production name search with a clearly documented fake
  implementation that returns a random fictional officer.
- Expose a bearer-protected Streamable HTTP MCP endpoint.
- Add local container packaging and an `azd` deployment to Azure Container Apps.
- Add sample configuration for selecting the customer-deployed MCP endpoint.
- Add targeted contract, authentication, and configuration tests.

## Requirements and Assumptions

| Item | Decision |
| --- | --- |
| Classification | Customer-facing sample / proof of concept |
| Expected scale | Small; one Container Apps replica |
| Cost profile | Cost-optimized, while keeping one warm replica for predictable Voice Agent tool latency |
| Data | Fictional sample data only; local filesystem state is acceptable for the sample |
| Region | Selected by the customer through the standard `AZURE_LOCATION` azd environment value |
| Compliance | No regulated or real customer data is included; customers must replace sample persistence before production use |
| Azure policy | Subscription-specific policies are unknown and must be checked by the customer before deployment |

## Existing Components

| Component | Technology | Current behavior |
| --- | --- | --- |
| Finance handoff sample | Python, preview `azure-ai-projects` SDK | Publishes a graph Agent whose MCP tools currently target an externally supplied Finance service |
| Finance OTP/officer sample | Python, preview `azure-ai-projects` SDK | Publishes a flat Agent whose MCP tools currently target the internal compatibility route `/mcp/umw-v3` |
| Finance business implementation | Python FastMCP | Contains call, offer, consent, appointment, callback, and disposition behavior |
| OTP/officer implementation | Python FastMCP | Contains OTP, pricing, interest, assignment, name search, confirmation, and end-call behavior |
| Shared sample helper | Python | Loads per-sample `.env` and injects MCP URL and Foundry Project connection ID into `agent.json` |

The two existing MCP implementations contain overlapping tool names with
different state identifiers and schemas. Registering both inventories on one
MCP endpoint would create ambiguous or overwritten tools.

## Architecture

Create one customer-neutral Python container under `VoiceAgent/shared_mcp` with
two isolated Streamable HTTP endpoints:

- `/mcp/finance-handoff` for `example1_finance_with_handoff`
- `/mcp/finance-otp-officer` for
  `example2_finance_with_OTP_and_Officer_Search`
- `/healthz` for unauthenticated liveness/readiness checks

The service will copy the required business logic into customer-facing
packages rather than import from the internal `docs/` tree. It will preserve
the existing tool names and schemas expected by each Agent.

The production phonetic/name-directory matcher and its 20,000-row data set will
not be copied. The OTP/officer package will instead contain a prominently
named and documented fake name-search implementation that chooses a random
fictional officer from a small committed fixture. Tool responses will identify
the implementation as sample-only where doing so does not break the Agent
contract.

The shared SDK helper will support an optional MCP config file selected through
`VOICE_AGENT_MCP_CONFIG`. Each generated config contains only:

- the route-specific HTTPS MCP URL;
- the route-specific Foundry Project connection ID.

Per-sample `.env` files retain the Foundry Project endpoint, Agent name, model,
and credential mode. Direct `VOICE_AGENT_MCP_SERVER_URL` and
`VOICE_AGENT_MCP_CONNECTION_ID` values remain supported for backward
compatibility and explicit overrides.

## Repository Layout

```text
VoiceAgent/
  shared_mcp/
    .azure/deployment-plan.md
    README.md
    azure.yaml
    Dockerfile
    requirements.txt
    app/
      shared_mcp/
        server.py
        auth.py
        finance_handoff/
        finance_otp_officer/
    data/
    infra/
    scripts/
      package.sh
      e2e-local.sh
      deploy.sh
      configure-agent.sh
    config/
      example1.shared.env.example
      example2.shared.env.example
    tests/
```

## Security

- Require `Authorization: Bearer <token>` on every MCP request, including
  Streamable HTTP GET and DELETE requests.
- Keep `/healthz` unauthenticated and return no tool or customer data.
- Generate the bearer token locally during deployment if it does not already
  exist in the azd environment.
- Pass the token to Bicep as a secure parameter and store it as a Container App
  secret; never commit or print it.
- Create route-specific Foundry remote-tool connections with the same bearer
  token, while keeping the token out of Agent JSON and generated Agent config.
- Run the container as a non-root user and expose only the application port.
- Retain HTTPS-only external ingress. Foundry requires a cloud-reachable HTTPS
  endpoint; local `localhost` is only for direct MCP testing.
- Keep sample state single-replica. Production use must replace filesystem
  state and the fake name search with durable customer implementations.

## Deployment

Use AZD with Bicep and Azure Container Apps.

### One-command packaging

```bash
cd shared_mcp
./scripts/package.sh
```

This builds the local OCI image and runs the offline test suite before
reporting success.

### One-command deployment and Agent connection configuration

```bash
cd shared_mcp
AZURE_AI_PROJECT_ENDPOINT="https://.../api/projects/..." ./scripts/deploy.sh
```

The deployment wrapper will:

1. initialize or reuse an azd environment;
2. generate/reuse a secret bearer token;
3. run `azd up`;
4. read the Container App FQDN from azd outputs;
5. verify unauthenticated MCP requests return `401`;
6. run authenticated `initialize` and `tools/list` against both routes and
   verify the corresponding Agent's allowed tools;
7. create or update two route-specific Foundry remote-tool connections;
8. write non-secret generated config files for the two Agents;
9. print the exact `VOICE_AGENT_MCP_CONFIG` value for each sample.

The Bicep deployment will create:

- Azure Container Registry;
- Log Analytics workspace;
- Container Apps managed environment;
- externally reachable Container App with system-assigned identity;
- separate `AcrPull` role assignment;
- startup, liveness, and readiness probes against `/healthz`;
- one fixed replica to avoid state divergence and tool-call cold starts.

No Azure deployment will be executed while implementing this repository
change. The deliverable is deployment-ready source and commands.

## Validation

- Unit-test both business packages and the fake name-search contract.
- Verify each MCP route contains every tool allowed by its corresponding
  committed Agent definition; additional vendored diagnostic/business tools
  remain inaccessible to that Agent through `allowed_tools`.
- Verify missing or incorrect bearer tokens return `401` on POST, GET, and
  DELETE MCP traffic.
- Verify `/healthz` returns `200` without exposing the token or tool data.
- Verify `VOICE_AGENT_MCP_CONFIG` materializes both Agent definitions with the
  correct route and connection ID, while direct environment overrides continue
  to work.
- Run the existing shared SDK tests.
- Build the container locally when Docker is available; otherwise validate the
  Dockerfile and record the environment limitation.
- Validate Bicep and AZD configuration with existing repository/Azure tools
  before marking the plan ready for deployment.

## Out of Scope

- Running an Azure deployment from this preparation task.
- Production-grade fuzzy or phonetic loan-officer name search.
- Migrating unrelated MCP packs or internal Kubernetes deployment machinery.

## Planned Work

1. Build the standalone shared MCP host and copy the two required business
   packages and fictional fixtures.
2. Replace only the complex OTP/officer name-search path with the fake random
   implementation.
3. Add authentication, health checks, tests, container packaging, and local
   compose support.
4. Add AZD/Bicep Container Apps infrastructure and deployment/configuration
   wrappers.
5. Add `VOICE_AGENT_MCP_CONFIG` support and update both sample READMEs and
   `.env.example` files.
6. Run targeted Python, MCP contract, container, and infrastructure validation.

## Generated Artifacts

- `app/shared_mcp/server.py`: dual-route Streamable HTTP host.
- `app/shared_mcp/auth.py`: ASGI bearer-token gate.
- `app/shared_mcp/finance_handoff/`: vendored Finance handoff business logic.
- `app/shared_mcp/finance_otp_officer/`: vendored OTP, pricing, interest, and
  officer workflow with fake random name search.
- `data/`: fictional Finance, caller, candidate, and officer fixtures.
- `Dockerfile` and `scripts/package.sh`: local packaging and container tests.
- `azure.yaml`, `infra/`, and `scripts/deploy.sh`: Azure Container Apps
  deployment.
- `scripts/configure-agent.sh` and `config/`: route-specific Foundry
  connections and non-secret Agent config generation.
- `scripts/e2e-local.sh`: repeatable Docker, Dev Tunnel, authenticated MCP
  route validation, Foundry connection, and generated local config workflow.
- `tests/test_shared_mcp.py`: auth, inventory, fixture, fake-search, and
  business-service tests.
- Updated shared SDK loader and both sample configurations/documentation.

## Verification Evidence

- Shared SDK helper tests: 8 passed.
- Shared MCP unit and business tests: 7 passed inside the Docker test target.
- Docker test and runtime targets: built successfully.
- Live container protocol smoke:
  - `/healthz` returned success;
  - unauthenticated MCP returned HTTP 401;
  - both routes completed MCP initialize and tools/list;
  - Finance handoff inventory contained 18 tools;
  - Finance OTP/officer inventory contained 8 tools;
  - `verify_caller_otp` authenticated the fictional `12345007` test profile.
- Full local-MCP/Foundry E2E:
  - Docker image packaged with 7 tests passing;
  - public Dev Tunnel health returned 200 and unauthenticated MCP returned 401;
  - `finance-example-local-e2e` version 3 passed with 6 handoff events and 2
    MCP events;
  - `finance-otp-officer-local-e2e` version 3 passed with 4 MCP events and
    successful fictional OTP authentication;
  - both active Agents target the persistent local Docker service through
    route-specific Foundry connections.
- Fixed local closure:
  - a persisted named Dev Tunnel and port provide one stable public HTTPS
    address for the local container;
  - the bearer token and connection names are reused transparently;
  - both CLI samples read `example1.local.env` / `example2.local.env`;
  - the local UI reads those same files through `mcp.config_file`;
  - UI publication reused the existing connections without receiving a token;
  - both UI-published Agents completed their MCP smoke flows.
- `az bicep build` completed successfully.
- `azure.yaml` was parsed and its Container Apps/Docker configuration checked.
- All shell scripts passed `bash -n` and are executable.
- `git diff --check` passed in the owning `Cognitive-Speech-TTS` repository.

## All validation checks pass

- [x] AZD installation (`azd 1.33.0`)
- [x] `azure.yaml` offline structure validation
- [x] Azure CLI and AZD authentication checks
- [ ] Customer azd environment setup
- [ ] Customer subscription and location confirmation
- [ ] `azd provision --preview --no-prompt`
- [x] Application and Docker build verification
- [x] Docker build-context validation
- [x] Package validation through `scripts/package.sh`
- [ ] Customer-subscription Azure Policy validation
- [x] Static `AcrPull` role verification

The unchecked items require the customer's selected subscription, region, and
policy context. They are intentionally deferred because this task produces the
deployment command but does not deploy or select Azure resources for the
customer.

## Role Assignment Verification

- Status: Verified statically.
- Identity: Container App system-assigned managed identity.
- Role: `AcrPull`
  (`7f951dda-4ed3-4680-a7ca-43fe172d538d`).
- Scope: The specific Azure Container Registry resource.
- Additional roles: None required; the MCP runtime does not call Azure data
  services.

## Section 7: Validation Proof

| Check | Command or evidence | Result |
| --- | --- | --- |
| AZD installed | `azd version` | Passed, version 1.33.0 |
| AZD authentication | `azd auth login --check-status` | Passed |
| Azure CLI authentication | `az account show --output none` | Passed |
| Bicep compile/lint | `az bicep build --file infra/main.bicep --stdout` | Passed |
| AZD schema shape | Parsed `azure.yaml` and asserted Container Apps host and Docker path | Passed |
| Shell syntax | `bash -n scripts/*.sh` | Passed |
| Python tests | Shared SDK tests plus shared MCP tests | 8 + 7 passed |
| Container package | `scripts/package.sh` | Docker test and runtime targets passed |
| MCP protocol | Live runtime image, both routes | Initialize/tools-list passed; OTP tool passed |
| MCP E2E | `scripts/e2e-local.sh` | Both public routes passed authenticated protocol and tool-contract validation |
| Agent publication | Each scenario's `sample.py publish`, `check`, and `run` | Both Agents published and invoked independently with required MCP evidence |
| RBAC static review | `infra/modules/acr-pull-role.bicep` | Least-privilege `AcrPull` at ACR scope |
| Provision preview | Requires customer azd environment | Deferred |
| Policy validation | Requires customer subscription | Deferred |
