# Evaluation results

Last updated: September 17, 2026.

## Knowledge evaluation

**The evaluation achieved 219 PASS / 18 FAIL (92.41%) on 237 knowledge-covered questions.**

The benchmark covers Theodore Roosevelt questions answerable from the current KB, using `gpt-4o` with Foundry IQ in Foundry Portal text interactions. The results measure final-answer correctness. A refusal on a question whose answer is available in the KB counts as FAIL.

| Metric | Result |
| --- | --- |
| Knowledge-covered questions | 237 |
| PASS | 219 |
| FAIL | 18 |
| Incomplete evaluations | 0 |
| Pass rate | 92.41% (219 / 237) |

### Failure breakdown

The 18 failed answers fall into these observed categories:

| Category | FAIL count |
| --- | --- |
| Incorrect facts, entities, places, numbers or timing | 5 |
| Answered a different question or misread the intended target | 2 |
| Incomplete, overly general or missing required details | 11 |
| **Total** | **18** |

Incomplete answers account for **11 of 18 failures (61.11%)**. Retrieval and use of relevant details are areas for follow-up; these are possible contributors rather than confirmed causes.

## Foundry Portal functional result

| Scenario | Result |
| --- | --- |
| Knowledge + Personal Voice + custom photo avatar workflow in Foundry Portal | **PASS** |

## Andrew and Harry cloud and Portal checks

Verified on September 17, 2026, using the Python creator with bundled Azure AI Projects 2.7.0b1, followed by manual testing in Foundry Portal.

| Check | Result | Observation |
| --- | --- | --- |
| Native voice agent creation | **PASS** | `creation_status="created"`; the saved definition matched the requested configuration (`definition_verified=true`) |
| Exact-version read-back | **PASS** | A separate `show --version "1"` returned `definition_verified=true`; agent state was `enabled` |
| Portal visibility | **PASS** | The agent was initially absent from the same project's list; adding `flight=voice_agent_bundle` to the Portal URL made it visible |
| Andrew Dragon HD voice playback | **PASS** | `en-US-Andrew:DragonHDLatestNeural` audio worked in Portal |
| Standard Harry Business avatar playback | **PASS** | The Harry / Business avatar worked in Portal |

The [Portal visibility troubleshooting step](../README.md#python-created-agent-missing-from-portal) records the preview URL workaround. These checks confirm creation, saved settings and voice/avatar playback; they do not add a new Knowledge correctness score or establish audio/video synchronization, interruption, latency or stability results.

## Python creator checks

Recorded on September 16, 2026, using bundled Azure AI Projects 2.7.0b1 and OpenAI 3.14.1; see the [SDK build record](../../../dist/README.md).

| Check | Result | Coverage |
| --- | --- | --- |
| Offline test suite | **58 passed; 0 skipped** | Six voice/avatar combinations, default Andrew + Harry Business template, strict asset and MCP URL validation, typed models, lifecycle, CLI and bundled SDK HTTP contracts, including API-version preservation, with synthetic in-memory responses |
| Direct CLI smoke checks | **17 expected outcomes passed** | Help; six valid configurations; three additional API-version formats; two unresolved templates, one invalid personal model and four invalid version/query configurations correctly rejected with exit code 2 |

See [Run Python offline checks](../README.md#run-python-offline-checks) for the unit-test and CLI help commands.

## Data handling

This document contains aggregate results and failure themes. Keep original questions, responses, logs, credentials and personal media in their authorized locations. The Python templates use `store=false`; review applicable storage, access and retention settings for Portal-created agents. Recording requires separate approval.
