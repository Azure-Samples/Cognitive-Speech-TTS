---
name: provision-foundry-iq
description: >-
  Provision or create an Azure AI Foundry IQ knowledge base from local files,
  especially VoiceAgent/samples/sample_foundry_iq_doc. Use when asked to
  upload documents to Foundry IQ, create a knowledge source or knowledge base,
  create its Foundry project MCP connection, or produce
  AZURE_VOICE_AGENTS_FOUNDRY_IQ_URL and
  AZURE_VOICE_AGENTS_FOUNDRY_IQ_CONNECTION_ID.
argument-hint: "[document folder] [optional knowledge-base name]"
---

# Provision Foundry IQ

Create a new Foundry IQ knowledge source, knowledge base, and project
connection from a local document folder. Always derive the Foundry account and
project from `AZURE_VOICE_AGENTS_ENDPOINT`; do not copy account identifiers
from another environment.

Use the bundled [provisioner](./scripts/provision_foundry_iq.py). It discovers
the endpoint account across all subscriptions visible to Azure CLI, selects the
account's Azure AI Search connection, uploads the documents, grants the project
managed identity Search Index Data Reader, and creates the MCP connection.

## Prerequisites

- Run from the `VoiceAgent` directory with its Python environment active.
- Install `samples/requirements.txt`.
- Sign in with `az login` using an identity that can read the endpoint Foundry,
  provision Search data-plane resources, read account keys, create project
  connections, and assign the Search Index Data Reader role.
- Set `AZURE_VOICE_AGENTS_ENDPOINT` in `samples/.env`.
- The endpoint Foundry account must have an Azure AI Search project connection.

## Workflow

1. Resolve the requested document folder. Default to
   `samples/sample_foundry_iq_doc`.
2. Discover all supported files recursively. The provisioner accepts Markdown,
   text, JSON, PDF, HTML, Word, and PowerPoint files and rejects other types.
3. Choose one resource name and use it for both preflight and creation. Derive
   a lowercase hyphenated name from the folder plus a short unique suffix when
   the user does not provide one.
4. Run a read-only preflight:

   ```powershell
   python skills/provision-foundry-iq/scripts/provision_foundry_iq.py --name <name> --dry-run
   ```

5. If preflight reports that `text-embedding-3-small` or `gpt-4.1-mini` is
   missing, explain that adding model capacity can incur cost and obtain the
   user's explicit approval. After approval, add
   `--create-missing-model-deployments`. Never add this flag implicitly.
6. Create the knowledge base with the same name used during preflight:

   ```powershell
   python skills/provision-foundry-iq/scripts/provision_foundry_iq.py --name <name>
   ```

   With approved model deployment creation:

   ```powershell
   python skills/provision-foundry-iq/scripts/provision_foundry_iq.py --name <name> --create-missing-model-deployments
   ```

7. For a different folder, pass `--docs-dir <path>`. If the Foundry has
   multiple Search connections, pass
   `--search-connection-name <name>`.
8. The final two output lines are the values to return to the user:

   ```dotenv
   AZURE_VOICE_AGENTS_FOUNDRY_IQ_URL=https://<search>.search.windows.net/knowledgebases/<name>/mcp?api-version=2026-05-01-preview
   AZURE_VOICE_AGENTS_FOUNDRY_IQ_CONNECTION_ID=/subscriptions/<subscription>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<account>/connections/<connection>
   ```

9. Add `--update-env` only when the user asks to replace those two values in
   `samples/.env`.

## Safety and validation

- A normal invocation creates Azure resources. Run `--dry-run` first.
- Never print or persist account keys. They are sent only to the Search service
  in the knowledge source and knowledge base definitions.
- Do not delete knowledge bases, knowledge sources, model deployments, project
  connections, or indexes. The script only removes stale files when rerunning
  the same explicitly named knowledge source.
- Do not use an existing `AZURE_VOICE_AGENTS_FOUNDRY_IQ_URL` to choose the
  Foundry or Search service. The endpoint and its Search connection control the
  destination.
- On failure, report the failed Azure operation and leave the existing `.env`
  values unchanged.