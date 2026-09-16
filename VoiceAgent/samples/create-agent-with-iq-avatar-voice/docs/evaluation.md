# Evaluation methods and results

Last updated: September 16, 2026.

Keep offline validation, manual workflow acceptance, and scored Knowledge results separate.

## Recorded results

The offline suite and CLI smoke checks were rerun after documentation cleanup on September 16, 2026. The Foundry result below remains the owner's previously confirmed manual acceptance.

| Check | Result | Scope |
| --- | --- | --- |
| Creator offline suite | **49 passed; 0 skipped** | Configuration, typed models, lifecycle, CLI, and actual bundled SDK/in-memory HTTP contract tests using synthetic responses; no Azure calls |
| Direct CLI smoke checks | **8 expected outcomes passed** | Help; four valid configurations; two unresolved templates and one invalid model rejected with exit code 2; no create command or Azure calls |
| Foundry Knowledge + Personal Voice + custom photo avatar | **PASS — owner-confirmed manual acceptance** | The owner confirmed completing the full workflow in Foundry; this is a manual result, not an automated cloud run |

The exact creator CLI has not been independently rerun live against the owner's existing agent.

The recorded offline run used bundled Azure AI Projects 2.7.0b1 and OpenAI 3.14.1; see the [SDK build record](../../../dist/README.md).

## Run offline checks

From the sample directory with its dependencies installed:

```bash
python -m unittest -v test_create_agent.py
python create_agent.py --help
python create_agent.py validate --config agent.local.json
```

Both unchanged templates (`agent.example.json` and `agent.personal.example.json`) must fail validation because they contain placeholders. Completed configurations should pass without credentials or network calls. The four combinations cover standard voice and Personal Voice, each with and without a custom photo avatar, all with Knowledge enabled.

The HTTP contract tests use the actual bundled SDK, fake credentials, and an in-memory transport, with sockets and DNS blocked. They check request serialization and response handling, not live service behavior. Report missing-SDK skips as **SKIPPED**, not passed.

## Recommended evaluation

These are suggested checks for future runs, not additional measured results.

- **Knowledge answers:** freeze and version the ingested source documents, such as [voice-agent-overview.md](../../sample_foundry_iq_doc/voice-agent-overview.md). Include questions supported by the documents and questions they cannot answer; expect an appropriate unknown response for the latter.
- **Grounding and citations:** check that retrieval ran and the retrieved passages support the answer. Verify that each citation supports its associated claim; a source link alone is not enough.
- **Media:** manually check the selected Personal Voice, custom photo likeness, audible playback, audio/video synchronization, microphone input, and interruption. Received media bytes alone do not establish successful playback.

## Summarize results

A manual **PASS** is a valid result. An aggregate summary is sufficient; original questions, answers, and logs do not need to be supplied or published.

For a scored run, define the rubric and treatment of ambiguous questions before testing. Report only counts or rates supported by collected data:

- Record total scheduled, passed, failed, and incomplete cases. If there are retries, separate first-attempt outcomes from final outcomes.
- State each criterion and denominator: expected answer or appropriate abstention / all scheduled questions; grounded-answer accuracy / answerable questions; correct unknown responses / unanswerable questions; citation correctness / responses requiring citations.
- Show numerator and denominator for each rate, keep failures and incomplete cases visible, and report **N/A** for a zero denominator. Do not infer percentages from manual acceptance.

For future evaluations, fill in the available fields below; leave unmeasured fields as **not measured**.

| Summary field | What to record |
| --- | --- |
| Date and scope | Run date; offline, manual, or scored evaluation |
| Configuration | Anonymous configuration label/revision, relevant model/SDK versions, and selected voice/avatar options |
| Corpus | Source-document version or snapshot label |
| Scored counts | Scheduled, passed, failed, incomplete; criteria and denominators; first-attempt versus final results if retried |
| Manual result and known limits | PASS/FAIL or not completed for the checks performed; limitations and remaining checks |

## Privacy and consent

Keep `store=false`; do not enable conversation recording just to fill a result summary. Use only consented Personal Voice and photo assets with authorized access. If recording is separately approved, apply retention and access controls. Share only sanitized summaries, never real credentials, personal identifiers, consent media, recordings, or restricted source content.
