// Copyright (c) Microsoft. All rights reserved.
// Tests for the generate review formatters. These cover what a reviewer is
// entitled to see: the identity of the agent being described, the prose fields
// unescaped, and every field the service sent -- including ones this code was
// never taught about.

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  definitionFromResponse,
  renderDefinition,
  shouldApplyGenerateResponse,
  summaryChips,
} from "./agentReview.mjs";

const definition = {
  kind: "voice",
  model_type: "managed",
  model: "gpt-realtime",
  instructions: "Line one.\nLine two.",
};

describe("renderDefinition", () => {
  it("puts the agent identity above the definition body", () => {
    const out = renderDefinition(definition, { name: "clinic-line", version: 3 });
    const lines = out.split("\n");

    assert.equal(lines[0], "name: clinic-line");
    assert.equal(lines[1], "version: 3");
    // The Connection dropdown lists agents by name, so the name has to precede
    // the body a reader is deciding about.
    assert.ok(lines.indexOf("kind: voice") > lines.indexOf("name: clinic-line"));
  });

  it("prints draft only when the agent is one", () => {
    assert.ok(renderDefinition(definition, { name: "a", draft: true }).includes("draft: true"));
    assert.ok(!renderDefinition(definition, { name: "a", draft: false }).includes("draft"));
  });

  it("omits identity fields the service left empty", () => {
    const out = renderDefinition(definition, { name: "a", version: undefined, description: "" });

    assert.ok(!out.includes("version:"));
    assert.ok(!out.includes("description:"));
  });

  it("renders instructions as a block rather than an escaped string", () => {
    const out = renderDefinition(definition, null);

    assert.ok(out.includes("instructions: |-"));
    assert.ok(out.includes("  Line one."));
    assert.ok(out.includes("  Line two."));
    assert.ok(!out.includes("\\n"));
  });

  it("shows fields it was never taught about", () => {
    // The regression this exists for: a definition field the service adds is
    // dropped silently, and the reviewer approves an agent they did not see.
    const out = renderDefinition(
      { ...definition, store: true, output_modalities: ["audio"], handoff: { target: "x" } },
      null,
    );

    assert.ok(out.includes("store: true"), out);
    assert.ok(out.includes("output_modalities:"), out);
    assert.ok(out.includes("handoff:"), out);
    assert.ok(out.includes('"target": "x"'), out);
  });

  it("does not repeat a field the named branches already rendered", () => {
    const out = renderDefinition(definition, null);

    assert.equal(out.split("\n").filter((line) => line.startsWith("model:")).length, 1);
    assert.equal(out.match(/instructions:/g).length, 1);
  });

  it("skips null and undefined rather than printing them", () => {
    const out = renderDefinition({ ...definition, avatar: null, handoff: undefined }, null);

    assert.ok(!out.includes("avatar"));
    assert.ok(!out.includes("handoff"));
  });

  it("survives a definition with nothing in it", () => {
    assert.equal(renderDefinition({}, null), "");
  });
});

describe("renderDefinition does not summarise away the things that decide trust", () => {
  const mcp = (label, url) => ({ type: "mcp", server_label: label, server_url: url, require_approval: "never" });

  it("distinguishes two different tool sets", () => {
    // The regression: `tools` printed only `name || type`, and MCP/toolbox entries carry
    // neither. Two unrelated tool sets rendered byte-for-byte identically, so a reviewer
    // could approve an agent wired to a server they never saw.
    const a = renderDefinition({ ...definition, tools: [mcp("deepwiki", "https://deepwiki.example/mcp")] }, null);
    const b = renderDefinition({ ...definition, tools: [mcp("billing", "https://billing.example/mcp")] }, null);

    assert.notEqual(a, b);
    assert.ok(a.includes("https://deepwiki.example/mcp"), a);
    assert.ok(a.includes("deepwiki"), a);
    assert.ok(a.includes("require_approval"), a);
  });

  it("shows what an llm_generated greeting will actually say", () => {
    const out = renderDefinition({
      ...definition,
      greeting: {
        type: "llm_generated",
        prompt: "Greet the caller by clinic name and offer to book.",
        fallback_text: "Hello, dental clinic.",
        tool_choice: "none",
      },
    }, null);

    assert.ok(out.includes("Greet the caller by clinic name"), out);
    assert.ok(out.includes("Hello, dental clinic."), out);
    assert.ok(out.includes("tool_choice"), out);
  });

  it("keeps a multi-line description from impersonating other fields", () => {
    // A description ending in "kind: spoof" must not emit a `kind:` line at column zero:
    // it would read as a definition field the service never sent.
    const out = renderDefinition(definition, {
      name: "n",
      description: "line one\nkind: spoof",
    });
    const topLevelKinds = out.split("\n").filter((line) => line.startsWith("kind:"));

    assert.equal(topLevelKinds.length, 1);
    assert.equal(topLevelKinds[0], "kind: voice");
    assert.ok(out.includes("description: |-"), out);
  });

  it("keeps a multi-line unknown scalar out of the top level", () => {
    const out = renderDefinition({ ...definition, note: "first\nmodel: fake" }, null);
    const models = out.split("\n").filter((line) => line.startsWith("model:"));

    assert.equal(models.length, 1);
    assert.equal(models[0], "model: gpt-realtime");
  });

  it("renders the audio stack in full", () => {
    // `audio` is no longer a hand-written branch; it goes through the generic tail.
    const out = renderDefinition({
      ...definition,
      audio: { input: { turn_detection: { type: "server_vad", threshold: 0.5 } } },
    }, null);

    assert.ok(out.includes("audio:"), out);
    assert.ok(out.includes("server_vad"), out);
    assert.ok(out.includes("0.5"), out);
  });
});

describe("summaryChips", () => {
  const voiceOf = (chips) => (chips.find(([label]) => label === "voice") || [])[1];

  it("reads the voice whether it is nested or already flattened", () => {
    // Vienna's compatibility layer flattens `voice` to a string; a direct Voice
    // Live response still nests it under `.name`. Both reach this panel.
    const nested = summaryChips({
      ...definition,
      audio: { output: { voice: { name: "en-US-Ava:DragonHDLatestNeural" } } },
    });
    const flat = summaryChips({
      ...definition,
      audio: { output: { voice: "en-US-Ava:DragonHDLatestNeural" } },
    });

    assert.equal(voiceOf(nested), "en-US-Ava:DragonHDLatestNeural");
    assert.equal(voiceOf(flat), "en-US-Ava:DragonHDLatestNeural");
  });

  it("reports the turn detection type from the input side", () => {
    const chips = summaryChips({
      ...definition,
      audio: { input: { turn_detection: { type: "server_vad" } } },
    });

    assert.deepEqual(chips.find(([label]) => label === "turn detection"), ["turn detection", "server_vad"]);
  });

  it("returns nothing for an empty definition", () => {
    assert.deepEqual(summaryChips({}), []);
  });
});

describe("definitionFromResponse", () => {
  const withDefinition = { versions: { latest: { version: 1, definition: { model: "gpt-realtime" } } } };

  it("finds the definition and the version it came from", () => {
    const found = definitionFromResponse(withDefinition);

    assert.deepEqual(found.definition, { model: "gpt-realtime" });
    assert.equal(found.latest.version, 1);
  });

  it("refuses a 200 that carries no definition", () => {
    // The regression: reporting success here put "generated" on screen beside an empty
    // review while selecting an agent whose model and voice were invented, so the user
    // connected to something they were never shown.
    assert.equal(definitionFromResponse({ name: "a" }), null);
    assert.equal(definitionFromResponse({ versions: {} }), null);
    assert.equal(definitionFromResponse({ versions: { latest: {} } }), null);
    assert.equal(definitionFromResponse({ versions: { latest: { definition: {} } } }), null);
    assert.equal(definitionFromResponse(null), null);
  });
});

describe("shouldApplyGenerateResponse", () => {
  const fresh = { requestToken: 3, currentToken: 3, isConnected: false };

  it("applies a response the user is still waiting for", () => {
    assert.equal(shouldApplyGenerateResponse(fresh), true);
  });

  it("drops a response whose request was superseded", () => {
    // Leaving the Generate tab, or starting another generate, bumps the token.
    assert.equal(shouldApplyGenerateResponse({ ...fresh, currentToken: 4 }), false);
  });

  it("drops a response that lands after the user connected", () => {
    // Connect sits outside the authoring panes and is enabled as soon as an agent is
    // selected, so it can be pressed mid-generate. Applying the response then would
    // repoint the review at the generated agent while the microphone stayed on the one
    // the session actually bound to.
    assert.equal(shouldApplyGenerateResponse({ ...fresh, isConnected: true }), false);
  });
});
