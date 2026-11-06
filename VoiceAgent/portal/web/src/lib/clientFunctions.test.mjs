// Copyright (c) Microsoft. All rights reserved.

import assert from "node:assert/strict";
import test from "node:test";

import {
  COMPLETED_FUNCTION_ITEM_EVENTS,
  appendTranscript,
  functionCallFromArgumentsDone,
  functionCallFromItem,
  functionCallsFromResponseDone,
  functionErrorOutput,
  functionOutputFrames,
  functionOutputItemFrame,
  isClientOwnedFunction,
  mergeFunctionCall,
  parseFunctionArguments,
  resolveFunctionArgumentsRaw,
  responseCreateFrame,
  serializeFunctionOutput,
} from "./clientFunctions.mjs";

test("mergeFunctionCall never lets an empty field erase a known one", () => {
  const first = mergeFunctionCall(null, {
    itemId: "item_1",
    callId: "call_1",
    name: "verify_spoken_digits",
    argumentsRaw: "",
    complete: false,
  });
  assert.equal(first.name, "verify_spoken_digits");
  assert.equal(first.complete, undefined);

  const second = mergeFunctionCall(first, { argumentsRaw: '{"field":"phone"}', complete: true });
  assert.equal(second.name, "verify_spoken_digits");
  assert.equal(second.callId, "call_1");
  assert.equal(second.argumentsRaw, '{"field":"phone"}');
  assert.equal(second.complete, true);

  // A later, argument-less announcement must not undo completeness.
  const third = mergeFunctionCall(second, { argumentsRaw: "", complete: false });
  assert.equal(third.argumentsRaw, '{"field":"phone"}');
  assert.equal(third.complete, true);
});

test("streamed argument deltas accumulate as the fallback payload", () => {
  let call = mergeFunctionCall(null, { callId: "call_1", name: "f" });
  for (const delta of ['{"field"', ':"phone_number"', "}"]) {
    call = mergeFunctionCall(call, { argumentsDelta: delta });
  }
  assert.equal(call.argumentsStream, '{"field":"phone_number"}');
  // The terminal payload wins when present; the stream covers an empty one.
  assert.equal(resolveFunctionArgumentsRaw(call), '{"field":"phone_number"}');
  const withRaw = mergeFunctionCall(call, { argumentsRaw: '{"field":"customer_id"}' });
  assert.equal(resolveFunctionArgumentsRaw(withRaw), '{"field":"customer_id"}');
  assert.equal(resolveFunctionArgumentsRaw(null), "");
});

test("the full realtime event sequence executes once, with real arguments", () => {
  // Replays the order Voice Live emits: the item is announced (and mirrored into the
  // conversation) BEFORE the arguments stream, so neither announcement may trigger execution.
  const events = [
    ["response.output_item.added", { id: "item_1", type: "function_call", call_id: "call_1", name: "f", arguments: "" }],
    ["conversation.item.created", { id: "item_1", type: "function_call", call_id: "call_1", name: "f", arguments: "" }],
  ];
  let call = null;
  const executions = [];
  const note = (patch) => {
    if (!patch) return;
    call = mergeFunctionCall(call, patch);
    if (call.callId && call.name && call.complete) {
      executions.push(resolveFunctionArgumentsRaw(call));
    }
  };

  for (const [type, item] of events) {
    note(functionCallFromItem(item, COMPLETED_FUNCTION_ITEM_EVENTS.has(type)));
  }
  assert.deepEqual(executions, [], "an announced item must not run before its arguments");

  note({ argumentsDelta: '{"field":"phone_number",' });
  note({ argumentsDelta: '"heard":"4255550198"}' });
  assert.deepEqual(executions, []);

  note(functionCallFromArgumentsDone({
    item_id: "item_1",
    call_id: "call_1",
    name: "f",
    arguments: '{"field":"phone_number","heard":"4255550198"}',
  }));
  assert.deepEqual(executions, ['{"field":"phone_number","heard":"4255550198"}']);
  assert.deepEqual(
    parseFunctionArguments(executions[0]),
    { field: "phone_number", heard: "4255550198" },
  );
});

test("function call details are read from items and from the arguments.done event", () => {
  assert.equal(functionCallFromItem({ type: "message" }), null);
  assert.deepEqual(
    functionCallFromItem(
      { id: "item_1", type: "function_call", call_id: "call_1", name: "f", arguments: "{}" },
      true,
    ),
    { itemId: "item_1", callId: "call_1", name: "f", argumentsRaw: "{}", complete: true },
  );
  // An item announced before the arguments finish streaming is not complete.
  assert.equal(
    functionCallFromItem({ id: "item_1", type: "function_call", call_id: "call_1", name: "f" }).complete,
    false,
  );
  assert.deepEqual(
    functionCallFromArgumentsDone({
      item_id: "item_1",
      call_id: "call_1",
      name: "f",
      arguments: '{"a":1}',
    }),
    { itemId: "item_1", callId: "call_1", name: "f", argumentsRaw: '{"a":1}', complete: true },
  );
});

test("conversation.item.created is not treated as carrying final arguments", () => {
  assert.ok(COMPLETED_FUNCTION_ITEM_EVENTS.has("response.output_item.done"));
  assert.ok(COMPLETED_FUNCTION_ITEM_EVENTS.has("conversation.item.done"));
  assert.ok(!COMPLETED_FUNCTION_ITEM_EVENTS.has("conversation.item.created"));
  assert.ok(!COMPLETED_FUNCTION_ITEM_EVENTS.has("response.output_item.added"));
});

test("response.done restates function calls as a backstop", () => {
  const calls = functionCallsFromResponseDone({
    type: "response.done",
    response: {
      output: [
        { type: "message", id: "msg_1" },
        { id: "item_1", type: "function_call", call_id: "call_1", name: "f", arguments: "{}" },
      ],
    },
  });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].callId, "call_1");
  assert.equal(calls[0].complete, true);
  assert.deepEqual(functionCallsFromResponseDone({ type: "response.done" }), []);
});

test("parseFunctionArguments tolerates anything the model emits", () => {
  assert.deepEqual(parseFunctionArguments('{"field":"phone"}'), { field: "phone" });
  assert.deepEqual(parseFunctionArguments(""), {});
  assert.deepEqual(parseFunctionArguments("not json"), {});
  assert.deepEqual(parseFunctionArguments("[1,2]"), {});
  assert.deepEqual(parseFunctionArguments(null), {});
});

test("serializeFunctionOutput always produces a string", () => {
  assert.equal(serializeFunctionOutput("done"), "done");
  assert.equal(serializeFunctionOutput({ a: 1 }), '{"a":1}');
  assert.equal(serializeFunctionOutput(undefined), "");
});

test("a failed call still returns an answerable output", () => {
  const output = functionErrorOutput("f", new Error("boom"));
  assert.equal(output.error, "client_function_failed");
  assert.equal(output.function, "f");
  assert.equal(output.message, "boom");
});

test("a batch of calls is answered with one response request", () => {
  assert.deepEqual(functionOutputItemFrame("call_1", '{"ok":true}'), {
    type: "conversation.item.create",
    item: { type: "function_call_output", call_id: "call_1", output: '{"ok":true}' },
  });
  assert.deepEqual(responseCreateFrame(), { type: "response.create" });

  const frames = functionOutputFrames([
    { callId: "call_1", outputText: "a" },
    { callId: "call_2", outputText: "b" },
  ]);
  // Both outputs must be in the conversation before the single response is requested.
  assert.equal(frames.length, 3);
  assert.equal(frames[0].item.call_id, "call_1");
  assert.equal(frames[1].item.call_id, "call_2");
  assert.deepEqual(frames[2], { type: "response.create" });
  assert.equal(frames.filter((f) => f.type === "response.create").length, 1);
  assert.deepEqual(functionOutputFrames([]), []);
});

test("transcript history stays bounded and ordered oldest-first", () => {
  let history = [];
  for (let i = 0; i < 5; i += 1) {
    history = appendTranscript(history, { transcript: `t${i}` }, 3);
  }
  assert.deepEqual(history.map((x) => x.transcript), ["t2", "t3", "t4"]);
});

test("only calls with a registered handler are this client's to answer", () => {
  // `end_conversation` is a server-owned system tool that Voice Live also surfaces as a
  // `function_call` item. The service runs it and closes the session, so answering it would
  // push a bogus output into a terminating conversation.
  const registry = { verify_spoken_digits: () => ({}) };
  assert.equal(isClientOwnedFunction("verify_spoken_digits", registry), true);
  assert.equal(isClientOwnedFunction("end_conversation", registry), false);
  assert.equal(isClientOwnedFunction("", registry), false);
  assert.equal(isClientOwnedFunction("verify_spoken_digits", {}), false);
  assert.equal(isClientOwnedFunction("verify_spoken_digits", null), false);
  // A non-callable entry is not a handler.
  assert.equal(isClientOwnedFunction("x", { x: "nope" }), false);
});
