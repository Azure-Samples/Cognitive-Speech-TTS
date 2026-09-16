# Evaluation results

Last updated: September 16, 2026.

## Knowledge evaluation

**The latest 252-question evaluation achieved 219 PASS / 33 FAIL (86.90%).**

The benchmark covers Theodore Roosevelt questions across 30 quiz groups, using `gpt-4o` with Foundry IQ in Foundry Portal text interactions. A declined answer counts as FAIL when the benchmark expects an answer.

The totals below measure final-answer correctness.

| Metric | Result |
| --- | --- |
| Questions evaluated | 252 |
| PASS | 219 |
| FAIL | 33 |
| Incomplete | 0 |
| Pass rate | 86.90% (219 / 252) |

### Failure breakdown

The final 33 failed answers fall into these observed categories:

| Category | FAIL count |
| --- | --- |
| Declined to answer | 15 |
| Incorrect facts, entities, places, numbers or timing | 5 |
| Answered a different question or misread the intended target | 2 |
| Incomplete, overly general or missing required details | 11 |
| **Total** | **33** |

Declined and incomplete answers account for **26 of 33 failures (78.79%)**. Knowledge coverage, retrieval and use of retrieved details are the main areas for follow-up; these are possible contributors rather than confirmed causes.

## Foundry Portal functional result

| Scenario | Result |
| --- | --- |
| Knowledge + Personal Voice + custom photo avatar workflow in Foundry Portal | **PASS** |

## Python creator checks

Recorded on September 16, 2026, using bundled Azure AI Projects 2.7.0b1 and OpenAI 3.14.1; see the [SDK build record](../../../dist/README.md).

| Check | Result | Coverage |
| --- | --- | --- |
| Offline test suite | **49 passed; 0 skipped** | Configuration, typed models, lifecycle, CLI and bundled SDK HTTP contracts with synthetic in-memory responses |
| Direct CLI smoke checks | **8 expected outcomes passed** | Help; four valid configurations; two unresolved templates and one invalid model correctly rejected with exit code 2 |

See [Run Python offline checks](../README.md#run-python-offline-checks) for the unit-test and CLI help commands.

## Data handling

This document contains aggregate results and failure themes. Keep original questions, responses, logs, credentials and personal media in their authorized locations. The Python templates use `store=false`; review applicable storage, access and retention settings for Portal-created agents. Recording requires separate approval.
