// Copyright (c) Microsoft. All rights reserved.

import assert from "node:assert/strict";
import test from "node:test";

import {
  agentDefinitionToYaml,
  parseAgentDefinitionYaml,
} from "./agentDefinition.mjs";

test("round trips a voice definition through portal-style YAML", () => {
  const definition = {
    kind: "voice",
    model_type: "managed",
    model: "azure-realtime",
    instructions: "First line.\nSecond line.",
    output_modalities: ["text", "audio"],
    store: true,
  };

  const yaml = agentDefinitionToYaml(definition);

  assert.match(yaml, /^definition:/);
  assert.match(yaml, /instructions: \|-/);
  assert.deepEqual(parseAgentDefinitionYaml(yaml), definition);
});

test("requires a top-level voice definition", () => {
  assert.throws(
    () => parseAgentDefinitionYaml("kind: voice\n"),
    /top-level definition object/,
  );
  assert.throws(
    () => parseAgentDefinitionYaml("definition:\n  kind: prompt\n"),
    /definition\.kind must be "voice"/,
  );
  assert.throws(
    () => parseAgentDefinitionYaml("definition: ["),
    /Invalid YAML/,
  );
});
