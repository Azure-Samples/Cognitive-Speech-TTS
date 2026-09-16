// Copyright (c) Microsoft. All rights reserved.

import assert from "node:assert/strict";
import test from "node:test";

import {
  CONTROL_AGENT_INSTRUCTIONS,
  DIGIT_DEMO_VARIANTS,
  VERIFIED_AGENT_INSTRUCTIONS,
  VERIFY_FUNCTION_NAME,
  VERIFY_SPOKEN_DIGITS_TOOL,
  buildVerificationOutput,
  chooseDigitGroup,
  createDigitDemoFunctions,
  digitComparison,
  digitDemoAgentSpec,
  digitsOnly,
  expectedDigitLength,
  extractDigitGroups,
} from "./digitDemo.mjs";

test("the verify tool is a native client-executed function tool", () => {
  assert.equal(VERIFY_SPOKEN_DIGITS_TOOL.type, "function");
  assert.equal(VERIFY_SPOKEN_DIGITS_TOOL.name, VERIFY_FUNCTION_NAME);
  // A client function carries no server_url / project_connection_id: the CLIENT fulfills it.
  assert.equal(VERIFY_SPOKEN_DIGITS_TOOL.server_url, undefined);
  assert.equal(VERIFY_SPOKEN_DIGITS_TOOL.project_connection_id, undefined);
  assert.deepEqual(VERIFY_SPOKEN_DIGITS_TOOL.parameters.required, ["field", "heard"]);
  // `heard` is required so the model's own reading is always available to show beside the
  // recognizer's in the UI — the comparison is the demo.
  assert.match(VERIFY_SPOKEN_DIGITS_TOOL.parameters.properties.heard.description, /REQUIRED/);
});

test("the A/B pair differs only by the tool and the verification prompt", () => {
  const verified = digitDemoAgentSpec(DIGIT_DEMO_VARIANTS.VERIFIED);
  const control = digitDemoAgentSpec(DIGIT_DEMO_VARIANTS.CONTROL);

  assert.deepEqual(verified.tools, [VERIFY_SPOKEN_DIGITS_TOOL]);
  assert.deepEqual(control.tools, []);
  assert.equal(control.instructions, CONTROL_AGENT_INSTRUCTIONS);
  assert.equal(verified.instructions, VERIFIED_AGENT_INSTRUCTIONS);
  // The control prompt is a strict prefix of the verified one, so the read-back task is identical.
  assert.ok(VERIFIED_AGENT_INSTRUCTIONS.startsWith(CONTROL_AGENT_INSTRUCTIONS));
  assert.ok(VERIFIED_AGENT_INSTRUCTIONS.includes(VERIFY_FUNCTION_NAME));
  assert.ok(!CONTROL_AGENT_INSTRUCTIONS.includes(VERIFY_FUNCTION_NAME));
  // Same opening line, so both calls start identically.
  assert.deepEqual(verified.greeting, control.greeting);
  assert.notEqual(verified.namePrefix, control.namePrefix);
});

test("digitsOnly strips every separator", () => {
  assert.equal(digitsOnly("425-555-0198"), "4255550198");
  assert.equal(digitsOnly(null), "");
});

test("extractDigitGroups reads numerals written by the recognizer", () => {
  assert.deepEqual(extractDigitGroups("my number is 425-555-0198"), ["4255550198"]);
  assert.deepEqual(extractDigitGroups("it's 425 555 0198 thanks"), ["4255550198"]);
});

test("extractDigitGroups reads digits spoken as words", () => {
  assert.deepEqual(
    extractDigitGroups("four two five five five five oh one nine eight"),
    ["4255550198"],
  );
  assert.deepEqual(extractDigitGroups("double four seven triple zero"), ["447000"]);
});

test("extractDigitGroups keeps separate numbers separate", () => {
  assert.deepEqual(
    extractDigitGroups("phone 4255550198 and customer id 30514882"),
    ["4255550198", "30514882"],
  );
});

test("extractDigitGroups joins groups only across spoken separators", () => {
  assert.deepEqual(extractDigitGroups("four two five dash five five five"), ["425555"]);
  assert.deepEqual(extractDigitGroups("nine, then later, three"), []);
});

test("chooseDigitGroup prefers the length the field expects", () => {
  const groups = ["12", "4255550198", "30514882"];
  assert.equal(chooseDigitGroup(groups, { field: "phone_number" }), "4255550198");
  assert.equal(chooseDigitGroup(groups, { field: "customer_id" }), "30514882");
  assert.equal(expectedDigitLength("Phone Number"), 10);
  assert.equal(expectedDigitLength("nickname"), null);
});

test("chooseDigitGroup falls back to what the model claims it heard", () => {
  const groups = ["12", "987654"];
  assert.equal(chooseDigitGroup(groups, { field: "reference", heard: "987655" }), "987654");
  assert.equal(chooseDigitGroup([], { field: "reference" }), "");
});

test("buildVerificationOutput corrects the digits the model misheard", () => {
  const output = buildVerificationOutput(
    [
      { transcript: "my name is Dana", source: "azure-speech" },
      { transcript: "my number is 425-555-0198", source: "azure-speech" },
    ],
    { field: "phone_number", heard: "4255550189" },
  );

  assert.equal(output.transcript_available, true);
  assert.equal(output.authoritative_value, "4255550198");
  assert.equal(output.model_heard, "4255550189");
  assert.equal(output.matches_model, false);
  assert.equal(output.digit_count, 10);
  assert.equal(output.expected_digit_count, 10);
  assert.equal(output.last_user_transcript, "my number is 425-555-0198");
  assert.deepEqual(output.recent_user_transcripts, ["my number is 425-555-0198"]);
});

test("buildVerificationOutput confirms a match and honours the turns argument", () => {
  const turns = [
    { transcript: "hi there" },
    { transcript: "customer id 30514882" },
  ];
  const output = buildVerificationOutput(turns, {
    field: "customer_id",
    heard: "30514882",
    turns: 2,
  });
  assert.equal(output.matches_model, true);
  assert.equal(output.authoritative_value, "30514882");
  assert.deepEqual(output.recent_user_transcripts, ["hi there", "customer id 30514882"]);
});

test("buildVerificationOutput reports honestly when no transcript exists", () => {
  const output = buildVerificationOutput([], { field: "phone_number" });
  assert.equal(output.transcript_available, false);
  assert.equal(output.authoritative_value, undefined);
  assert.match(output.note, /no transcript/i);
});

test("the demo handler waits for the transcript before answering", async () => {
  const functions = createDigitDemoFunctions();
  const order = [];
  const output = await functions[VERIFY_FUNCTION_NAME](
    { field: "phone_number", heard: "4255550189" },
    {
      waitForUserTranscript: async () => { order.push("waited"); return { transcript: "425 555 0198" }; },
      recentUserTranscripts: () => {
        order.push("read");
        return [{ transcript: "425 555 0198" }];
      },
    },
  );
  assert.deepEqual(order, ["waited", "read"]);
  assert.equal(output.authoritative_value, "4255550198");
});

test("a timed-out transcript wait never returns the previous turn's digits", async () => {
  const functions = createDigitDemoFunctions();
  // The phone number from an earlier turn is still in history; asking about the customer id
  // when this turn produced no transcript must report unavailable, not that stale number.
  const output = await functions[VERIFY_FUNCTION_NAME](
    { field: "customer_id", heard: "30514882" },
    {
      waitForUserTranscript: async () => null,
      recentUserTranscripts: () => [{ transcript: "my number is 425-555-0198" }],
    },
  );
  assert.equal(output.transcript_available, false);
  assert.equal(output.authoritative_value, undefined);
  assert.equal(output.last_user_transcript, undefined);
});

test("digitComparison surfaces both readings so the UI can show them side by side", () => {
  const output = buildVerificationOutput(
    [{ transcript: "my number is 425-555-0198" }],
    { field: "phone_number", heard: "4255550189" },
  );
  const comparison = digitComparison(JSON.stringify(output));
  assert.equal(comparison.field, "phone_number");
  assert.equal(comparison.available, true);
  assert.equal(comparison.agentHeard, "4255550189");
  assert.equal(comparison.recognizerValue, "4255550198");
  assert.equal(comparison.matches, false);
  assert.equal(comparison.transcript, "my number is 425-555-0198");
});

test("digitComparison reports agreement when both readings match", () => {
  const output = buildVerificationOutput(
    [{ transcript: "customer id 30514882" }],
    { field: "customer_id", heard: "3051-4882" },
  );
  const comparison = digitComparison(JSON.stringify(output));
  assert.equal(comparison.agentHeard, "30514882");
  assert.equal(comparison.matches, true);
});

test("digitComparison has nothing to compare without a transcript or a heard value", () => {
  const missing = digitComparison(JSON.stringify(
    buildVerificationOutput([], { field: "phone_number", heard: "4255550198" }),
  ));
  assert.equal(missing.available, false);
  assert.equal(missing.recognizerValue, "");
  assert.equal(missing.matches, null);

  const noHeard = digitComparison(JSON.stringify(
    buildVerificationOutput([{ transcript: "425 555 0198" }], { field: "phone_number" }),
  ));
  assert.equal(noHeard.agentHeard, "");
  assert.equal(noHeard.matches, null);
});

test("digitComparison ignores output from an unrelated client function", () => {
  assert.equal(digitComparison('{"ok":true}'), null);
  assert.equal(digitComparison("not json"), null);
  assert.equal(digitComparison(""), null);
  assert.equal(digitComparison("[1,2]"), null);
});
