# Voice Agent examples

## Start here

This directory is the entry point for the Voice Agent portal, runnable samples,
the Finance reference workflow, and its shared MCP service. Detailed setup and
operation instructions live with the component that owns them; this file routes
users and coding agents to the correct entry point.

> [!IMPORTANT]
> **On Windows, use WSL2 for this repository.** Do not run the repository
> setup or runtime workflow from native PowerShell or Command Prompt, and do
> not use a checkout mounted under `/mnt/c/`. Start WSL2, clone the repository
> into the WSL Linux filesystem (for example, `~/src/Cognitive-Speech-TTS`),
> and run all repository commands from WSL. Use the Windows browser to open
> the resulting `localhost` UI and grant microphone permission.

For an unqualified request such as **"run the UI"** or **"start the portal"**,
use [`portal/`](portal/README.md). It is the general Voice Agent UI and runs on
`http://127.0.0.1:9527` by default. Do not start the Finance MCP stack unless
the request mentions Finance, Templates, or the shared MCP.

## Portal + local MCP quickstart

Use this path when the portal must publish or run the checked-in Templates.
It is the recommended end-to-end Linux/WSL workflow:

```bash
cd /path/to/Cognitive-Speech-TTS/VoiceAgent
az login
./scripts/setup-local-examples.sh \
   --project-endpoint "https://<account>.services.ai.azure.com/api/projects/<project>"
./scripts/login-devtunnel.sh
./scripts/setup-local-examples.sh --check
./scripts/manage-local-mcp-and-ui.sh restart
```

`login-devtunnel.sh` uses GitHub device-code authentication. Follow the printed
`https://github.com/login/device` prompt. Azure operations continue to use the
separate identity selected by `az login`.

Success requires `local_mcp_and_portal=ready`. Open
**http://localhost:18098**, then verify with:

```bash
./scripts/manage-local-mcp-and-ui.sh status
curl -fsS http://127.0.0.1:18003/healthz
curl -fsS http://127.0.0.1:18098/healthz
```

Port `9527` is only for a portal-only session without the managed local MCP
lifecycle. Do not run a second manual portal after this quickstart.

## Choose an entry point

| Goal | Start here | What it owns |
| --- | --- | --- |
| Run the general Voice Agent UI | [`portal/README.md`](portal/README.md) | Agent editor, YAML version editing, Templates, voice playground, and standalone WebRTC page |
| Run Python or .NET samples | [`samples/README.md`](samples/README.md) | Common Python setup, microphone samples, REST lifecycle, IQ, Toolbox, local functions, downloads, and the C# sample |
| Run the complete Finance workflow | [`docs/README.md`](docs/README.md) | Ordered subscription, MCP, sample, portal, and debugging guides |
| Work on or deploy the Finance MCP | [`shared_mcp/README.md`](shared_mcp/README.md) | Shared MCP image, Finance routes, local Dev Tunnel hosting, and Azure Container Apps deployment |
| Create an IQ + voice + avatar Agent | [`samples/create-agent-with-iq-avatar-voice/README.md`](samples/create-agent-with-iq-avatar-voice/README.md) | Portal-first Andrew Dragon HD, Harry Business, Knowledge IQ, and optional Python creation |
| Inspect SDK package information | [`dist/README.md`](dist/README.md) | Public Python and .NET SDK dependencies and historical preview build records |
| Use the coding-agent workflows | [`skills/`](skills/) | Voice Agent creation, IQ/Toolbox provisioning, and local-session debugging |

## Instructions for coding agents

When the user asks to run or debug something from this directory:

1. Verify that commands will run on Linux. For a Windows user, require a WSL2
   checkout in the WSL filesystem. If the checkout is under `/mnt/c/` or the
   terminal is native Windows, stop and guide the user to clone and reopen the
   repository in WSL2 before continuing.
2. Select the component from the table above and read its `README.md` before
   running commands.
3. Treat **UI** without a qualifier as the general [`portal/`](portal/README.md).
4. Treat **Finance UI**, **portal Templates with Finance**, or
   **shared MCP UI** as the workflow documented in
   [`docs/03_run_samples.md`](docs/03_run_samples.md).
5. Reuse an existing component-local `.env` and virtual environment when they
   are valid. Never copy credentials or endpoints between unrelated `.env`
   files without the user's intent.
6. Start servers as long-running processes, verify their `/healthz` endpoint,
   and report the browser URL and log location. Do not report success merely
   because a process was spawned.
7. Do not silently fall back to mock data or a different Azure Project when
   authentication, endpoint, model, or preview checks fail.

For the default portal route, follow [`portal/README.md`](portal/README.md) to
prepare `portal/.env` and its `.venv`, start `portal/demo_server.py`, then
verify:

```text
GET http://127.0.0.1:9527/healthz
```

For the complete Finance route, follow the ordered
[`docs/README.md`](docs/README.md) workflow. The normal lifecycle commands are:

```bash
./scripts/setup-local-examples.sh --project-endpoint "https://<account>.services.ai.azure.com/api/projects/<project>"
./scripts/manage-local-mcp-and-ui.sh restart
./scripts/manage-local-mcp-and-ui.sh status
./scripts/manage-local-mcp-and-ui.sh stop
```

The setup command installs Node.js 22 and the Dev Tunnel CLI under the ignored
`.local-mcp-and-ui/tools/` directory when they are missing. It also supports
minimal Linux Python installations that provide `venv` but omit `ensurepip`:
each component environment receives its own bootstrapped `pip`. No `sudo` or
system package change is required for those three tools. Azure CLI must already
be installed and authenticated; Dev Tunnel device-code authentication remains
an explicit user action because setup must not authenticate as an identity the
user did not choose.

## Platform support

The supported repository working environment is Linux. On a Windows computer,
use **WSL2 for the entire repository workflow**, including the portal, samples,
MCP, deployment, and validation commands:

1. Start a supported WSL2 Linux distribution.
2. Clone this repository again into the WSL filesystem, for example under
   `~/src/`. Do not run the workflow from a Windows checkout mounted under
   `/mnt/c/`.
3. Install Git, Python 3.10+, and Azure CLI inside WSL, then authenticate Azure
   CLI. The local setup script can install repository-local Node.js 22 and Dev
   Tunnel CLI copies. Azure Developer CLI is needed only for deployment.
   Windows-side CLI login state is not assumed to be shared.
4. The local setup, MCP E2E, and lifecycle scripts use native Python and never
   invoke Docker. Install Docker only when deliberately running the separate
   `shared_mcp/scripts/package.sh` image-packaging command; Azure Container
   Apps deployment uses a remote build.
5. Open the WSL checkout with VS Code Remote - WSL and run all commands from
   its WSL terminal.
6. Open the resulting `localhost` URL in the Windows browser; browser
   microphone permission remains on the Windows side.

Some individual component documents retain native PowerShell commands because
their code can run independently on Windows. They are not the recommended or
supported end-to-end repository workflow. Native Windows execution, WSL1, and
running the checkout from `/mnt/c/` are outside the supported path.

## Directory map

| Path | Purpose |
| --- | --- |
| [`portal/`](portal/) | General local Voice Agent portal and WebRTC UI |
| [`samples/`](samples/) | Python, .NET, and Finance samples |
| [`docs/`](docs/) | Finance architecture, setup, operation, and debugging guides |
| [`shared_mcp/`](shared_mcp/) | Shared Finance MCP source, native runtime, optional container, IaC, and deployment scripts |
| [`scripts/`](scripts/) | Finance local setup and process lifecycle entry points |
| [`dist/`](dist/) | Public SDK package information and historical preview build records |
| [`skills/`](skills/) | Reusable coding-agent workflows |
| [`tests/`](tests/) | Offline contracts for the common Projects SDK samples |

## Security and environment boundaries

- Configure only Azure resources and identities the customer is authorized to
  use.
- Never place access tokens, API keys, connection secrets, or customer data in
  source files.
- Use Foundry Project connections or environment-based credentials.
- The portal and samples use Azure Foundry; running the local portal does not run
  the Azure voice service locally.
- Review each component's persistence and recording behavior before using
  sensitive prompts, audio, transcripts, or tool output.
