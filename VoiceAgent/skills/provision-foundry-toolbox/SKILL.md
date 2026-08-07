---
name: provision-foundry-toolbox
description: >-
  Create or provision a Microsoft Foundry Toolbox with an Azure AI Search tool
  over local files, especially VoiceAgent/samples/sample_foundry_iq_doc. Use
  when asked to create a Foundry Toolbox, index documents for a Toolbox,
  configure an azure_ai_search Toolbox tool, or output
  AZURE_VOICE_AGENTS_TOOLBOX_NAME and AZURE_VOICE_AGENTS_TOOLBOX_VERSION.
argument-hint: "[document folder] [optional new Toolbox name]"
---

# Provision Foundry Toolbox

Create a new Azure AI Search index from local text documents, then create an
immutable Foundry Toolbox version that exposes the index as
`azure_ai_search`. Always use the Foundry project in
`AZURE_VOICE_AGENTS_ENDPOINT`.

Use the bundled [provisioner](./scripts/provision_foundry_toolbox.py). It uses
the supported `azure-ai-projects` Toolbox client and discovers the project's
Azure AI Search connection. It does not reuse the Foundry IQ URL or connection.

## Prerequisites

- Run from the `VoiceAgent` directory with its Python environment active.
- Install `samples/requirements.txt`.
- Sign in with `az login` using an identity that can read the Foundry project,
  create Search indexes, upload documents, and create Toolbox versions.
- Set `AZURE_VOICE_AGENTS_ENDPOINT` in `samples/.env`.
- The Foundry project must contain an Azure AI Search connection.

## Workflow

1. Resolve the document folder. Default to
   `samples/sample_foundry_iq_doc`.
2. Choose one new lowercase, hyphenated Toolbox name. Add a short unique suffix
   when the user does not provide a name. Reuse the same name in preflight and
   creation.
3. Run the read-only preflight:

   ```powershell
   python skills/provision-foundry-toolbox/scripts/provision_foundry_toolbox.py --name <name> --dry-run
   ```

4. Confirm that the plan points to the endpoint project, intended Search
   connection, correct document count, a new Search index, and a new Toolbox.
5. Create and validate the index and Toolbox version:

   ```powershell
   python skills/provision-foundry-toolbox/scripts/provision_foundry_toolbox.py --name <name>
   ```

6. For another folder, pass `--docs-dir <path>`. If the project has multiple
   Search connections, pass `--search-connection-name <name>`.
7. Return the final two output lines to the user:

   ```dotenv
   AZURE_VOICE_AGENTS_TOOLBOX_NAME=<toolbox-name>
   AZURE_VOICE_AGENTS_TOOLBOX_VERSION=<immutable-version>
   ```

8. Add `--update-env` only when the user asks to replace the Toolbox values in
   `samples/.env`.

## Behavior and safety

- A normal invocation creates a dedicated Azure AI Search index and a Foundry
  Toolbox version. Run `--dry-run` first.
- The provisioner supports UTF-8 Markdown, text, JSON, and HTML files. It
  chunks each file and creates a lexical index queried with `query_type=simple`.
- Require a new Toolbox and index name. Do not overwrite or delete existing
  Toolbox versions, indexes, connections, or documents.
- Never print access tokens or connection credentials.
- On failure, report the failed Search or Toolbox operation. Leave existing
  `.env` values unchanged unless `--update-env` was explicitly supplied and
  creation completed successfully.