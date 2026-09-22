# Turn your knowledge into a personalized voice experience with Microsoft Foundry

A customer asks how a product works, then follows up: “Can you give me an example?” A speaking avatar can make that exchange more approachable—but a familiar voice cannot compensate for an unsupported answer. The opportunity is to bring both together: a personalized conversation and information people can check.

For organizations building customer support, training or learning experiences, Microsoft Foundry provides a way to combine these capabilities. **Foundry IQ** retrieves information from a prepared knowledge base—a collection of sources the agent can consult. **Personal Voice** supplies speech based on consented voice data, while a **custom photo avatar** provides the visual presentation. Grounding means using retrieved source material to support the answer, rather than relying only on the model's general knowledge.

This article shares a three-question demo, the configuration decisions behind it and lessons from an evaluation of 237 knowledge-covered questions. The [companion sample][sample] provides the full walkthrough. Native voice agents in this sample are in preview; check availability, region support, access requirements and usage costs before starting.

## Where personalized voice agents can help

These are potential applications, not customer deployments validated by the sample.

### Customer support and product guidance

Connect approved product documentation so customers can ask about a feature, request an explanation and inspect the supporting information. An authorized voice and avatar can personalize the interaction; current, well-organized sources determine whether the answers remain useful.

### Employee onboarding and training

Let employees explore unfamiliar terminology and processes through questions and follow-ups. An approved presenter's voice and avatar could provide a familiar identity, while the application team designs the document permissions, identity controls and content maintenance required for an internal deployment.

### Interactive learning

A learner can begin with a broad topic and ask for a specific example. Our demonstration uses a Theodore Roosevelt knowledge base to explore that pattern. Teams can substitute their own authorized learning materials; neither a historical subject nor a particular appearance is required.

## Watch a three-question conversation

The approximately three-minute recording combines Knowledge, Personal Voice and a custom photo avatar in the Microsoft Foundry portal. It presents three interactions that teams can use when trying a similar experience:

| Question | What to inspect |
| --- | --- |
| What were Theodore Roosevelt's main contributions to conservation? | Whether the answer addresses the requested topic and can be checked against the source material |
| Could you give one specific example and explain why it mattered? | Whether the follow-up provides the requested detail rather than repeating a general summary |
| What was Microsoft's closing stock price yesterday? | How the agent handles a request outside the knowledge base's subject |

Watch the demo below. These questions illustrate an evaluation pattern; the recording is not an additional accuracy benchmark.

<!-- Publication step: embed the approved hosted demo video here. Confirm asset eligibility and permissions before publishing. Do not link to a local file path. -->

*The voice and avatar presentation is AI-generated, not an archival recording or evidence of statements made by Roosevelt. Asset eligibility and permissions require a separate review before publication.*

## Keep knowledge, voice and appearance separate

Each resource has a distinct role. Changing the voice does not add knowledge, and updating the documents does not require recreating the personal assets.

| Resource | Configuration decision | Check before combining |
| --- | --- | --- |
| Foundry IQ knowledge base | Connect the prepared source collection through the agent's Knowledge integration | A covered question returns relevant supporting passages |
| Personal Voice | Select the prepared voice in the portal, or use its runtime name in Python | Required consent is complete and standalone speech synthesis works |
| Custom photo avatar | Select the prepared avatar, or use its runtime name in the avatar configuration | Image, consent-video and eligibility requirements are met, and the avatar preview works |

The [Knowledge guide][knowledge-guide], [Personal Voice guide][voice-guide] and [photo-avatar guide][asset-guide] cover resource preparation. Afterward, use either the [portal creation path][portal-guide] or the [Python workflow][python-guide]; both reuse the prepared resources. The sample uses the Microsoft Foundry portal for interaction rather than supplying a separate customer-facing application.

### Make the personal-asset binding explicit

For teams using Python, this excerpt from the [Personal Voice and photo-avatar template][personal-template] shows the binding inside the agent's `definition`. It is **not a complete configuration**; the full template also includes the model, instructions, audio input and knowledge connection.

```json
{
  "audio": {
    "output": {
      "format": {"type": "audio/pcm", "rate": 24000},
      "voice_type": "azure-personal",
      "voice": "<personal-voice-name>",
      "personal_voice_model": "DragonLatestNeural"
    }
  },
  "avatar": {
    "type": "photo_avatar",
    "character": "<custom-photo-avatar-name>",
    "customized": true,
    "model": "vasa-1",
    "output_protocol": "webrtc"
  },
  "output_modalities": ["text", "audio", "avatar"]
}
```

Replace the two name placeholders with the prepared assets' **runtime names**, not consent-record IDs or uploaded filenames. In the complete template, the knowledge connection pairs the knowledge base's MCP URL with the matching project connection name. MCP, or Model Context Protocol, lets the agent call the retrieval tool. Copy the URL and connection name from the same existing connection rather than constructing them independently.

The creator's `validate` → `create` → exact-version `show` workflow checks the configuration, creates the agent and compares the saved settings with the request. This verifies configuration persistence—not answer quality or media playback—and does not provision the knowledge base or personal assets.

## Prepare knowledge before polishing the presentation

Start from the questions people need answered. Check that the documents contain the necessary details, keep titles and source references intact, and remove duplicates or unreadable material. Through the portal upload workflow, the service manages document processing; teams still need to inspect what retrieval returns.

The sample starts with **Minimal** retrieval reasoning effort and **Extractive data** output, which returns source content for the agent to use. Treat these as settings to evaluate against your collection, not universal recommendations. Keep source-document versions stable during comparisons and do not upload benchmark answers into the knowledge base.

Use an explicit grounding instruction. For example, the sample asks the agent to:

> Call `knowledge_base_retrieve` for factual questions, answer from the retrieved content, include source references in text, and acknowledge when the knowledge base does not contain the answer.

An instruction is a behavior to test, not a guarantee. Begin with a covered question, a follow-up asking for detail and an out-of-scope question. Inspect the retrieved passages alongside the answer: a citation is useful only if its source supports the claim.

## What 237 questions revealed

To measure answer quality separately from presentation, we evaluated **237 questions answerable from the current Theodore Roosevelt knowledge base**, using `gpt-4o` with Foundry IQ in Microsoft Foundry portal text interactions.

| Final-answer result | Count |
| --- | --- |
| PASS | 219 |
| FAIL | 18 |
| Incomplete evaluations | 0 |
| **Pass rate** | **92.41% (219/237)** |

The score measures final-answer correctness on this knowledge-covered set. It is not retrieval accuracy, an end-to-end voice/avatar score or a prediction of performance on another organization's documents. A refusal when the answer is available in the knowledge base counts as FAIL. The Python voice template uses `gpt-realtime`; the `gpt-4o` text evaluation should not be attributed to that configuration.

The most useful insight was in the failures:

| Observed failure | Count | Suggested investigation—not a confirmed cause |
| --- | --- | --- |
| Incorrect facts or details | 5 | Compare each claim with the retrieved passage |
| Missed the intended question | 2 | Check whether the response addresses the requested subject and relation |
| Incomplete or overly general | 11 | Check whether the required details appear in retrieval and in the final answer |

**Eleven of the eighteen failures—61.11%—were incomplete answers.** Before adding more persona instructions, investigate whether relevant details are being found and used. Keep separate notes for missing evidence and evidence the answer failed to include; the observed categories alone do not identify a root cause.

The [evaluation summary][evaluation] also records a PASS for the Knowledge + Personal Voice + photo-avatar workflow in the portal, **58 passing offline Python tests with 0 skipped**, and **17 CLI checks with the expected outcomes**. These checks cover different parts of the sample. Playback, synchronization, interruption and latency need their own evaluation rather than being inferred from the knowledge score.

## Build personalized experiences responsibly

Tell people when speech and animation are synthetic, obtain the required permissions and complete the applicable consent process. Rights to a photograph, document or recording do not automatically authorize synthesizing someone's voice or likeness. Historical or public-domain material is not a substitute for product eligibility and consent requirements.

Personal Voice API access and custom photo-avatar access are subject to eligibility and approved-use requirements. Confirm the [Personal Voice requirements][personal-voice] and [custom photo-avatar requirements][photo-avatar] for the intended scenario; consent alone does not establish that a use case is approved.

Use authorized knowledge sources, review storage and retention settings, and design access controls for the audience. A convincing presentation should help people engage with information, not make unsupported answers harder to question.

## Choose your next step

- **Try the experience:** start with the [sample prerequisites][prerequisites], prepare a small authorized document set and consented assets, then follow the [portal walkthrough][portal-guide].
- **Build with code:** use the [personal-asset template][personal-template] and [Python workflow][python-guide] to validate, create and verify the agent configuration.
- **Evaluate a pilot:** use the [evaluation summary][evaluation] as a starting point. Test covered questions, detail-seeking follow-ups and out-of-scope requests; track answer correctness separately from the voice and avatar experience.
- **Explore the knowledge layer:** read the [Foundry IQ overview][iq-overview] to understand how reusable knowledge bases fit the design.

Start with one focused collection and three representative interactions. Establish that the answers are useful and supported, then refine the voice and visual experience around them.

[sample]: https://github.com/uchihaqyf-bot/Cognitive-Speech-TTS/blob/c84184b4d7c62cb838e7904ab201b948849517d2/VoiceAgent/samples/create-agent-with-iq-avatar-voice/README.md
[prerequisites]: https://github.com/uchihaqyf-bot/Cognitive-Speech-TTS/blob/c84184b4d7c62cb838e7904ab201b948849517d2/VoiceAgent/samples/create-agent-with-iq-avatar-voice/README.md#prepare-your-project-and-assets
[knowledge-guide]: https://github.com/uchihaqyf-bot/Cognitive-Speech-TTS/blob/c84184b4d7c62cb838e7904ab201b948849517d2/VoiceAgent/samples/create-agent-with-iq-avatar-voice/README.md#prepare-knowledge-in-the-portal
[asset-guide]: https://github.com/uchihaqyf-bot/Cognitive-Speech-TTS/blob/c84184b4d7c62cb838e7904ab201b948849517d2/VoiceAgent/samples/create-agent-with-iq-avatar-voice/README.md#create-your-photo-avatar
[voice-guide]: https://github.com/uchihaqyf-bot/Cognitive-Speech-TTS/blob/c84184b4d7c62cb838e7904ab201b948849517d2/VoiceAgent/samples/create-agent-with-iq-avatar-voice/README.md#create-your-personal-voice
[portal-guide]: https://github.com/uchihaqyf-bot/Cognitive-Speech-TTS/blob/c84184b4d7c62cb838e7904ab201b948849517d2/VoiceAgent/samples/create-agent-with-iq-avatar-voice/README.md#create-in-foundry-portal
[python-guide]: https://github.com/uchihaqyf-bot/Cognitive-Speech-TTS/blob/c84184b4d7c62cb838e7904ab201b948849517d2/VoiceAgent/samples/create-agent-with-iq-avatar-voice/README.md#create-with-python
[personal-template]: https://github.com/uchihaqyf-bot/Cognitive-Speech-TTS/blob/c84184b4d7c62cb838e7904ab201b948849517d2/VoiceAgent/samples/create-agent-with-iq-avatar-voice/agent.personal.example.json
[evaluation]: https://github.com/uchihaqyf-bot/Cognitive-Speech-TTS/blob/c84184b4d7c62cb838e7904ab201b948849517d2/VoiceAgent/samples/create-agent-with-iq-avatar-voice/docs/evaluation.md
[iq-overview]: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-foundry-iq
[personal-voice]: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/personal-voice-overview
[photo-avatar]: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/text-to-speech-avatar/custom-photo-avatar-create
