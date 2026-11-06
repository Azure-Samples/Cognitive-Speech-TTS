// Copyright (c) Microsoft. All rights reserved.

import test from "node:test";
import assert from "node:assert/strict";
import { buildGreetingConfig } from "./greeting.mjs";

test("omits greeting when the agent should wait for the user", () => {
  assert.equal(buildGreetingConfig({ mode: "none" }), null);
});

test("builds template greeting without changing exact text", () => {
  assert.deepEqual(
    buildGreetingConfig({ mode: "template", text: "Hello Grace. " }),
    { type: "template", text: "Hello Grace. " },
  );
});

test("builds generated greeting with fallback and tool choice", () => {
  assert.deepEqual(
    buildGreetingConfig({
      mode: "llm_generated",
      prompt: "Greet Grace.",
      fallbackText: "Hello Grace.",
      toolChoice: "auto",
    }),
    {
      type: "llm_generated",
      prompt: "Greet Grace.",
      fallback_text: "Hello Grace.",
      tool_choice: "auto",
    },
  );
});

test("omits an empty optional fallback", () => {
  assert.deepEqual(
    buildGreetingConfig({
      mode: "llm_generated",
      prompt: "Say hello.",
      fallbackText: "   ",
    }),
    {
      type: "llm_generated",
      prompt: "Say hello.",
      tool_choice: "none",
    },
  );
});

test("rejects blank required content and invalid tool choice", () => {
  assert.throws(
    () => buildGreetingConfig({ mode: "template", text: "  " }),
    /text is required/,
  );
  assert.throws(
    () => buildGreetingConfig({ mode: "llm_generated", prompt: "  " }),
    /prompt is required/,
  );
  assert.throws(
    () => buildGreetingConfig({
      mode: "llm_generated",
      prompt: "Say hello.",
      toolChoice: "sometimes",
    }),
    /Unsupported greeting tool choice/,
  );
});
