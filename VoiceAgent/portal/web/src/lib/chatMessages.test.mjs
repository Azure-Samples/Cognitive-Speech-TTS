// Copyright (c) Microsoft. All rights reserved.

import test from "node:test";
import assert from "node:assert/strict";
import {
  describeSessionClose,
  insertBeforeMessage,
  shouldDrainSessionAudio,
} from "./chatMessages.mjs";

test("tool status is inserted before an already-visible assistant response", () => {
  const messages = [
    { id: "user-1", type: "user" },
    { id: "assistant-1", type: "assistant" },
  ];
  const next = insertBeforeMessage(
    messages,
    { id: "tool-1", type: "mcp_call" },
    "assistant-1",
  );

  assert.deepEqual(next.map((item) => item.id), ["user-1", "tool-1", "assistant-1"]);
});

test("tool status stays first when the assistant response has not rendered yet", () => {
  const next = insertBeforeMessage(
    [{ id: "user-1", type: "user" }],
    { id: "tool-1", type: "mcp_call" },
    "assistant-1",
  );
  next.push({ id: "assistant-1", type: "assistant" });

  assert.deepEqual(next.map((item) => item.id), ["user-1", "tool-1", "assistant-1"]);
});

test("describes an agent-initiated conversation close as successful", () => {
  assert.deepEqual(
    describeSessionClose(1001, "Conversation ended by agent"),
    { text: "conversation ended by agent", kind: "ok" },
  );
  assert.deepEqual(
    describeSessionClose(1001, ""),
    { text: "session ended (idle/timeout)", kind: "" },
  );
});

test("drains audio only for an agent-initiated end-conversation close", () => {
  assert.equal(
    shouldDrainSessionAudio(1001, "Conversation ended by agent", false),
    true,
  );
  assert.equal(
    shouldDrainSessionAudio(1001, "Conversation ended by agent", true),
    false,
  );
  assert.equal(shouldDrainSessionAudio(1001, "", false), false);
  assert.equal(shouldDrainSessionAudio(1000, "client stopped session", false), false);
});
