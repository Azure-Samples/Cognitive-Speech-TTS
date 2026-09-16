# Evaluation methods and results

Last updated: September 16, 2026.

Creation, Knowledge QA, audio transport, audible playback, and personal-asset integration are different checks. Never combine their results into one undifferentiated pass rate.

## Recorded evidence

| Scope | Result | What it establishes |
| --- | --- | --- |
| Preserved browser sample, commit `e956461a799842d0adedfb0093542444d1b4369a`, PR #444 | **144 offline tests passed** in the recorded pre-PR run | Browser bridge regression checks, not native-agent correctness |
| Preserved browser sample, live Avatar disabled | **PASS** | Greeting, Knowledge MCP, grounded English answer, PCM bytes, completion |
| Preserved browser sample, live Avatar enabled | **PASS for transport** | Greeting, Knowledge MCP, answer, video bytes, completion; separate PCM intentionally skipped |
| Preserved browser sample, local manual acceptance | **PASS, confirmed by the tester** | Ava standard voice, built-in Lisa, automatic greeting, playback, synchronization and interruption |
| Preserved browser sample, pre-commit regression rerun on September 16 | **144 passed** in 1.73 seconds | Existing runtime and environment remain unchanged |
| Creator, isolated SDK installation/provenance | **PASS** | New WSL Python 3.13.15 environment; bundled Projects 2.7.0b1, OpenAI 3.14.1; wheel hash, actual import, pip provenance and `pip check` passed |
| Creator, expanded offline suite with actual bundled SDK | **49 passed; 0 skipped** | Configuration, typed models, lifecycle, CLI and seven real-client/in-memory-HTTP test methods; fake responses only |
| Creator, direct process CLI smoke | **8 expected outcomes passed** | `--help`; four completed configurations; two unresolved templates and one invalid model rejected with exit 2; no create command or Azure calls |
| Knowledge + Personal Voice + custom photo-avatar workflow in Foundry | **PASS — owner-confirmed manual acceptance** | The sample owner confirmed completing the full workflow in Foundry; this is a manual report, not an automated cloud run |
| Personal Voice/custom photo-avatar configuration semantics | **DOCUMENTED CONTRACT** | Public Voice Live documentation identifies runtime names/base models; bundled SDK defines native fields and enums |
| Creator CLI against the owner's existing agent | **NOT INDEPENDENTLY RERUN** | Offline tests and the owner's Foundry acceptance do not establish a live execution of this exact CLI against that agent |
| Hosted deployment, cross-browser or long-running reliability | **NOT VALIDATED** | No deployment, SLA or reliability claim |

The owner confirmed the Foundry workflow on September 16, 2026. This supersedes the earlier blanket native-binding/Portal “not verified” status. The confirmation did not include an agent/version export, per-case results or timing measurements. Do not infer that every K1–K5/media case, both transport protocols, or this exact creator CLI was exercised. Those details can be recorded during a separately scoped reproduction without invalidating the owner's manual acceptance.

The browser baseline uses a different SDK, transport, corpus and agent family. Its 144 tests do not cover this new creator. Its headless media checks are not proof of synchronized speech. See the [preserved sample](../../voice-live-foundry-iq-avatar/README.md) and [PR #444](https://github.com/Azure-Samples/Cognitive-Speech-TTS/pull/444).

Historical evaluations using private knowledge or questions are excluded from this public result table. A separate sanitized local review draft is not publication approval and is not evidence for this sample. No private question set is included or rerun.

## Offline checks

From the creation sample directory with its dependencies installed:

```bash
python -m unittest -v test_create_agent.py
python create_agent.py --help
python create_agent.py validate --config agent.local.json
```

Both unchanged templates (`agent.example.json` and `agent.personal.example.json`) must fail validation because they contain placeholders. Completed local configurations must pass without credentials or network calls. Cover standard and personal voice, each with and without a custom photo avatar, while retaining Knowledge in every combination.

Tests exercise strict configuration, native model serialization/typed attributes, existing-name refusal, exact-version verification, separate server-issued IDs, failed read-back, disabled retries and local-output overwrite protection. The real `AIProjectClient` contract tests use an in-memory HTTP transport and fake credential to inspect request bodies, preview headers and exact-version routes and deserialize synthetic responses. The bundled SDK adds `Foundry-Features` to the creation POST; the tested GET agent/version routes do not carry that header. Tests capture this client behavior rather than adding an unverified override. These tests do not contact Azure or establish runtime support.

The 49-test run includes nine successful HTTP configuration subcases across the four combinations, both personal base models and both avatar protocols, plus altered/missing/null asset read-back checks. These subcases are not additional top-level tests or live test runs. Socket creation, connection and DNS lookup are blocked in the HTTP contract tests.

If a test is skipped because the exact SDK is missing, report it as **SKIPPED**, not passed. Mock-only lifecycle tests are not a substitute for serialization through the actual pinned SDK.

### Recorded dependency provenance

The September 16 isolated run uses Python 3.13.15, Projects 2.7.0b1, OpenAI 3.14.1, Azure Identity 1.25.3, Azure Core 1.41.0 and Azure Storage Blob 12.30.1. The actual Projects import resolves inside the new native environment. The browser and earlier native environments were not modified.

Bundled wheel SHA-256:

```text
f857a1281e2fa3414f25e02aed95dfe2275495027b0a764f38921a8589f15e75
```

The source revision is recorded in [the build record](../../../dist/README.md). The requirements do not freeze every transitive dependency; record resolved versions on each run. Package availability is no longer the prior blocker.

## Small public Knowledge QA matrix

Ingest all relevant sections of [voice-agent-overview.md](../../sample_foundry_iq_doc/voice-agent-overview.md), not just the one-document upload example. Freeze the ingested content before testing. These are documentation-based expectations, **not measured results**.

| Case | Prompt | Expected source-supported behavior | Source section |
| --- | --- | --- | --- |
| K1 | What can be configured in an immutable voice-agent version? | Model, instructions, audio/tool settings and other documented defaults; cite the source | Key capabilities: Agent lifecycle |
| K2 | Is conversation storage on by default, and what can be retained if enabled? | Optional/off by default; transcripts, tool events and audio when enabled | Key capabilities: Optional conversation history |
| K3 | What is the difference between a managed model and a self-deployed model? | Distinguish service-managed model from a customer project deployment | Key capabilities: Flexible model options |
| K4 | What does Foundry manage so an application does not need its own voice orchestration service? | Explain managed session/configuration/model/tool coordination without inventing features | How it works |
| K5 | What is this agent's guaranteed monthly availability percentage? | The document supplies no numerical SLA; say "I don't know" instead of inventing a percentage | Unsupported numerical claim; Current scope and availability |

For every case, inspect whether `knowledge_base_retrieve` actually ran and whether the retrieved section supports the final answer. A citation badge or source URL alone does not establish correct attribution. Keep spoken answers short; inspect detailed sources in text.

### Separate manual media acceptance

| Case | Check | Evidence required |
| --- | --- | --- |
| P1 | Correct native agent/version is visible in Portal | Match returned name, agent ID, version ID and exact version wherever displayed; retain read-back for identifiers not exposed by the UI |
| V1 | Standard voice answer | Audible answer matches the text; selected voice is actually used |
| V2 | Microphone and interruption | Spoken query works; speaking during playback interrupts as expected |
| V3 | Fresh session/reconnect | No stale answer or audio from the prior session |
| PV1 | Personal Voice independently | Consented asset synthesis succeeds through supported tooling; does not yet prove native binding |
| PA1 | Own-photo asset independently | Consent accepted, asset `Succeeded`, correct likeness in supported preview |
| PV2 | Native Personal Voice without avatar | Exact saved runtime name/base model; audible chosen voice in the native agent |
| PA2 | Native custom photo avatar with standard voice | Correct likeness, chosen protocol, audible answer and synchronized video |
| PV3/PA3 | Combined native Personal Voice and photo avatar | Exact saved names/base model/protocol, chosen voice, correct likeness, synchronization and interruption |

The new baseline does not configure an automatic greeting. The earlier greeting result applies only to the preserved browser sample. Test additional greeting settings separately if added later.

## Scoring and denominators

Prelabel each question against the **actual frozen corpus** as answerable, unanswerable or ambiguous. Do not reuse coverage labels from an older corpus. Keep ambiguous cases visible and explain their scoring policy before the run.

- **Overall expected-behavior correctness:** questions whose answer or abstention meets the predefined rubric / all scheduled questions. Report failures and missing responses; do not silently remove them.
- **Knowledge coverage:** questions answerable from the frozen corpus / all scheduled questions.
- **Covered-question accuracy:** correct answers on answerable questions / all answerable questions. Show this beside, not instead of, overall accuracy.
- **Correct abstention:** appropriate unknown responses on unanswerable questions / all unanswerable questions.
- **Unsupported-claim rate:** completed responses containing at least one unsupported factual claim / all completed responses. Also report missing responses, so request failures do not disappear.
- **Citation presence:** responses displaying a source / completed responses. Assess source support separately; presence is not correctness.

For a zero denominator, report **N/A**, not 0% or 100%. Distinguish semantic reference-answer correctness from grounded behavior: an unknown answer can be appropriate for this corpus while failing a benchmark that expects an external fact.

Keep first-attempt outcomes and eventual outcomes separate. If failed questions are retried, retain every attempt and the selection rule; a latest-answer score is not first-attempt reliability. Do not compute latency percentiles from anecdotal or success-only timing samples.

## Reproducible run record

Keep detailed evidence in an access-controlled location, not in public Git. Record:

- Date/time, operator-approved scope, SDK source/checksum and package versions.
- Search/Speech/agent API versions; exact model and model type.
- Actual agent ID, name and exact version, plus local config revision/hash.
- Corpus inventory/revision, chunking, retrieval settings and connection authentication type.
- Case ID, answerability, original prompt, every attempt, retries, service status and response outcome.
- Retrieval/tool evidence, selected source support, final answer score and abstention decision.
- First-attempt and eventual outcome separately; timing definitions, failures and timeout policy.
- For media, transport bytes separately from manual audible/synchronization/interruption results.

Do not enable conversation recording merely to fill the table. The template defaults `store=false`. If persistent transcripts/audio are needed, obtain approval, set retention/access controls, and record the changed configuration. Publish only a reviewed sanitized summary; omit credentials, personal identifiers, consent media, recordings and restricted knowledge/questions.
