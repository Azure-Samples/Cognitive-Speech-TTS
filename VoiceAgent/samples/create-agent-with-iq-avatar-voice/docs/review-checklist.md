# Creation-only sample review checklist

Use this checklist to review the sample's scope, configuration, validation evidence and reproducibility. It does not imply that every checklist item has been executed or that the pull request has been approved.

## Requirement-to-deliverable map

| Requirement | Material | Acceptance boundary |
| --- | --- | --- |
| Knowledge IQ configuration | [README, step 2](../README.md#2-create-knowledge-iq) | Index, ingestion, source, KB, project MCP connection and RBAC; provisioning is owner-operated |
| Custom avatar configuration | [Photo-avatar preparation](../README.md#3-create-your-photo-avatar), [personal template](../agent.personal.example.json) | Consent-based custom photo avatar; not a built-in or trained video-avatar fallback |
| Personal Voice configuration | [Personal Voice preparation](../README.md#4-create-your-personal-voice), [native field table](../README.md#personal-voice-and-custom-photo-avatar-configuration) | Runtime voice name and synthesis base model are distinct from Speech management/profile IDs |
| Creation-only code | [Creator](../create_agent.py), [standard template](../agent.example.json), [tests](../test_create_agent.py) | Validate/create/exact-version read-back; no microphone client, UI, proxy, container or asset uploader |
| Open the created agent in Foundry Portal | [Portal handoff](../README.md#7-hand-off-to-foundry-portal) | Correct project/name/IDs/version; manual navigation, not a guessed deep link |
| Methods and actual results | [Evaluation](evaluation.md) | Offline contract results separate from owner-confirmed Foundry acceptance and detailed QA/media metrics |

The separate [browser sample](../../voice-live-foundry-iq-avatar/README.md) is preserved historical work. It is not imported or required by the creator and is not part of this creation-only runtime. Its 144 passing tests and Ava/Lisa acceptance do not establish native Personal Voice or custom photo-avatar behavior.

## Recorded verification

The sample owner confirmed completing the Knowledge + Personal Voice + custom photo-avatar workflow in Foundry. The [evaluation record](evaluation.md) attributes this to manual acceptance and distinguishes it from the **49 creator tests passed, zero skipped**, **8 direct CLI smoke outcomes passed**, and successful wheel provenance and `pip check` results. The separate unchanged browser regression reports **144 passed**.

The owner's confirmation is not a claim of an independently reproduced live CLI run or a complete protocol, performance or reliability matrix.

## Review focus

- [ ] Follow the Knowledge setup using only authorized/public content; check corpus coverage and role scope.
- [ ] Check both full templates and the four documented configuration combinations.
- [ ] Verify the Personal Voice runtime name/base-model distinction and native `photo_avatar` spelling.
- [ ] Verify consent, resource compatibility and independent asset preview requirements are explicit.
- [ ] Check creation has no implicit overwrite/version append, retry, fallback, enabling or provisioning.
- [ ] Inspect exact-version read-back and distinct server-issued agent/version identifiers.
- [ ] Inspect SDK provenance, actual offline results, HTTP-transport contract checks and manual evidence attribution.
- [ ] Confirm no private media, questions, credentials, real resource/asset IDs or local reports are in the public deliverable.

## Optional independent reproduction

For a new run, approve the exact project/resource scope, allowed operations, corpus, legitimately consented assets, cost and retention. Reuse a provided agent with the read-only `show` command when only configuration verification is needed; creating another agent is unnecessary. A live interaction test is separate from reading configuration.

1. Match the native agent's configuration and exact version with its Portal identity and local read-back report.
2. Run K1–K5 from the evaluation matrix, inspect actual retrieval and source support, and score unknown-answer behavior.
3. Verify Personal Voice and custom photo-avatar runtime names against their authorized assets.
4. Record the selected configuration and protocol rather than assuming every documented combination was tested.
5. Check audible voice identity, likeness, synchronization and interruption on that native agent. Asset/model playground results cannot replace this check.
6. Add observed per-case results to a sanitized evaluation summary; retain identifiers and raw evidence privately.

No deployment, cross-browser reliability or SLA claim is made.
