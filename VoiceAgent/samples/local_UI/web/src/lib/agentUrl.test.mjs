// Copyright (c) Microsoft. All rights reserved.

import test from "node:test";
import assert from "node:assert/strict";
import { withSelectedAgent } from "./agentUrl.mjs";

test("adds the selected agent while preserving route, query, and hash", () => {
  assert.equal(
    withSelectedAgent(
      "http://localhost:8095/demo/?backend=voice-live-tip&autostart=1#session",
      "finance agent/mcp",
    ),
    "http://localhost:8095/demo/?backend=voice-live-tip&autostart=1&agent=finance+agent%2Fmcp#session",
  );
});

test("replaces or removes only the selected agent", () => {
  const current = "http://localhost:8095/demo/?agent=old&backend=tip";
  assert.equal(
    withSelectedAgent(current, "new"),
    "http://localhost:8095/demo/?agent=new&backend=tip",
  );
  assert.equal(
    withSelectedAgent(current, ""),
    "http://localhost:8095/demo/?backend=tip",
  );
});
