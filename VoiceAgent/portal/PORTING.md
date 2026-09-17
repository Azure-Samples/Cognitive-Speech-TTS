# Upstream tracking and future ports

## First-port source

| Field | Value |
| --- | --- |
| Source identifier | `voice-agent-demo` (resolve the repository through maintainer-only records) |
| Branch | `main` |
| Full repository commit | `e713a37c4cdb3282157cbaf46b6d425bcd984c05` |
| Commit time | `2026-09-15T23:50:17Z` |
| Remote verification / first port | September 16, 2026 |
| Source directory | `tests/voice-agent-tests/voice-agents-tests-dashboard/voice_demo` |
| Destination | `VoiceAgent/portal` |

The initial clean source checkout was fast-forwarded from
`72ce62dc3af4f81fce86fb213855e229901c69e6`. Its resulting `HEAD` was checked
against `git ls-remote origin refs/heads/main`; both were the full commit above.
The requested `voice\_demo` path was resolved to the actual `voice_demo` folder.
Only tracked Git blobs from that commit were imported; working-tree
configuration and credentials were not copied.

## What the manifest records

`UPSTREAM.json` is the source of truth:

- `upstream.source_id`: neutral source alias; private repository URLs and access
  instructions belong in maintainer-only records, not this public repository.
- `upstream.commit`: immutable full repository commit used for the port.
- `upstream.last_path_commit`: last commit touching the demo, which can be
  older than the repository commit.
- `files`: every file in that upstream directory, including intentional
  omissions. Each has an exact **raw Git blob SHA-256** and an action:
  `copied`, `modified`, `generated`, or `omitted`.
- `ported_sha256`: accepted local bytes of each included file.
- `local_files`: hashes of new portal-only files, including docs, tests, and
  test-only Azure service fixtures. The manifest itself is excluded to avoid a
  self-hash.

These hashes are a change-detection baseline, not an independent digital
signature or proof of redistribution rights.
The portal's `.gitattributes` pins text to LF for consistent local hashes across
Windows and POSIX; upstream hashes always describe the original Git bytes.

## Check the current port

No upstream access, packages, or network are required for a local check:

```powershell
python tools\upstream_status.py --check
```

With access to an existing upstream checkout:

```powershell
python tools\upstream_status.py --source "<source-checkout>" --ref origin/main --check
```

The tool verifies the pinned source hashes, compares the chosen committed
source tree (including omitted files), and reports local added/removed/changed
files. It warns if the source worktree is dirty; that worktree is never copied.
It does not need a clone URL in the public manifest: resolve `voice-agent-demo`
using maintainer-only records and supply that checkout with `--source`.
It exits `1` with `--check` for drift or an advanced upstream revision, and `2`
for an invalid manifest/Git operation.

**The tool never fetches, pulls, checks out, overwrites, or merges files.**

## Update safely

1. Inspect both repositories' status. Preserve unrelated changes. Fetching is
   sufficient for comparison and does not require changing the source checkout:

   ```powershell
   git -C "<source-checkout>" status --short --branch
   git -C "<source-checkout>" fetch origin main
   git -C "<source-checkout>" rev-parse origin/main
   python tools\upstream_status.py --source "<source-checkout>" --ref origin/main
   ```

   Only fast-forward the source checkout with `git pull --ff-only origin main`
   when it is clean and already on `main`. Never reset/clean/stash work just to
   update this port.

2. Compare the previous pin and the candidate commit, scoped to the source
   directory. Review every added file before inclusion. **Do not blindly copy
   the directory**: removed backends, internal reports, resource identifiers,
   and credential-handling paths must stay removed.
3. Apply relevant changes to the port, preserving the local policy below.
   Record feature additions/removals, contract changes, and reasons in a dated
   `CHANGELOG.md` entry containing both old and new full commit IDs.
4. Update the manifest's source revision, commit time, last path commit, and
   upstream file list/hashes from the candidate **Git blobs**. Keep explicit
   omission reasons. Do not update the source pin for a local-only edit.
5. Rebuild both frontend bundles, run the Python/JavaScript/browser suites,
   scan source and generated assets for credentials/internal resources, and
   verify dependencies use public registries.
6. After reviewing the change log, explicitly refresh local hashes:

   ```powershell
   python tools\upstream_status.py --record-local
   python tools\upstream_status.py --source "<source-checkout>" --ref origin/main --check
   ```

   `--record-local` never changes the upstream pin or source hashes. It refuses
   to bless a reintroduced omitted file or a missing included file.
7. Review the whole diff, including bundles, `CHANGELOG.md`, and `UPSTREAM.json`.
   Commit those together when ready. Publication still requires the normal
   repository/security/redistribution review.

## Local policy to retain

- Standalone Python backend and locally bundled frontend; no parent dashboard
  imports, private package feed URLs, source checkout, or SDK wheel at runtime.
- Match the adjacent public samples' version-create route and flat
  `voice` / `voice_type` request fields, while retaining legacy read compatibility.
- An Azure Foundry project is mandatory. No runtime mode selector, offline
  backend, or mock-response fallback. Keep test doubles strictly under `tests/`.
- Public project endpoint supplied by the operator; no internal backends,
  pre-provisioned connection IDs, subscription enumeration, or resource seeding.
- Server-held Azure identity, strict local browser boundary, service header
  allowlists, and no authenticated redirects to another endpoint.
- No shutdown resource deletion; Azure storage and local event recording are
  opt-in. Keep ignored local files/logs out of the tracked manifest.
- Preserve explicit session storage choices for generated results without adding
  unsupported generation API fields or silently rewriting stored agent versions.
- Require a captured or explicitly selected conversation ID before loading
  historical transcript, tool, or audio data.
- Keep full third-party notices beside the generated assets. Do not reintroduce
  private clone URLs, implementation source paths, or private PR references.
- No server-side arbitrary MCP probing or retrieval of connection secrets.
- Preserve protocol/authoring regressions and the real local browser smoke test.
