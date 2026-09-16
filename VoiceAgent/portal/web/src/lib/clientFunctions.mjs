// Copyright (c) Microsoft. All rights reserved.
// Client-executed `function` tools (design §6.1). Voice Live declares the tool to the model but
// never runs it: it forwards a `function_call` to whoever holds the session WebSocket and relays
// that peer's `function_call_output` back into the conversation. These helpers are the pure part
// of that contract -- argument parsing, output shaping, and the two frames to send -- so the
// session hook only has to own the transport and the UI.

/**
 * Merge the pieces of a function call that arrive across several events into one record.
 * Falsy fields are ignored so an early, argument-less `response.output_item.added` cannot
 * erase the name, call id, or arguments a later event supplied. `argumentsDelta` is the one
 * accumulating field: the model streams arguments, and the deltas are the fallback when the
 * terminal event carries an empty `arguments` string.
 */
export function mergeFunctionCall(existing, patch) {
  const merged = { ...(existing || {}) };
  for (const [key, value] of Object.entries(patch || {})) {
    if (!value) continue;
    if (key === "argumentsDelta") {
      merged.argumentsStream = (merged.argumentsStream || "") + value;
      continue;
    }
    merged[key] = value;
  }
  return merged;
}

/** The arguments to execute a call with: the terminal payload, else the streamed deltas. */
export function resolveFunctionArgumentsRaw(call) {
  return (call && (call.argumentsRaw || call.argumentsStream)) || "";
}

/**
 * The `function_call` details carried by a conversation/response item, or null.
 * `complete` marks the events whose item carries the FINAL arguments; the model streams
 * arguments, so an item announced before they finish must not be executed yet.
 */
export function functionCallFromItem(item, complete = false) {
  if (!item || item.type !== "function_call") return null;
  return {
    itemId: item.id || "",
    callId: item.call_id || item.callId || "",
    name: item.name || "",
    argumentsRaw: typeof item.arguments === "string" ? item.arguments : "",
    complete: Boolean(complete),
  };
}

/** The `function_call` details carried by a `response.function_call_arguments.done` event. */
export function functionCallFromArgumentsDone(event) {
  if (!event) return null;
  return {
    itemId: event.item_id || "",
    callId: event.call_id || event.callId || "",
    name: event.name || "",
    argumentsRaw: typeof event.arguments === "string" ? event.arguments : "",
    complete: true,
  };
}

/**
 * Event types whose `function_call` item carries the completed arguments.
 *
 * `conversation.item.created` is deliberately NOT here: the realtime protocol emits it for a
 * `function_call` item alongside `response.output_item.added`, before the arguments finish
 * streaming, so trusting it would execute the call with `{}` and discard the real arguments.
 * The repository's other Voice Live clients (functional_test_harness.py, webrtc_session.py)
 * likewise wait for a terminal event.
 */
export const COMPLETED_FUNCTION_ITEM_EVENTS = Object.freeze(new Set([
  "response.output_item.done",
  "conversation.item.done",
]));

/**
 * Every completed `function_call` in a `response.done` payload. `response.output` repeats the
 * response's items in final form, which makes this the backstop when the per-item events are
 * not delivered — the same source the dashboard's server-side bridge reads.
 */
export function functionCallsFromResponseDone(event) {
  const output = event && event.response && event.response.output;
  if (!Array.isArray(output)) return [];
  return output.map((item) => functionCallFromItem(item, true)).filter(Boolean);
}

/** Model-authored arguments are a JSON string; a non-object (or unparsable) call gets `{}`. */
export function parseFunctionArguments(raw) {
  const text = String(raw == null ? "" : raw).trim();
  if (!text) return {};
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

/** `output` travels as a string; objects are JSON-encoded, everything else stringified. */
export function serializeFunctionOutput(value) {
  if (typeof value === "string") return value;
  if (value === undefined) return "";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

/** A failure still has to be answered, or the model waits on a call that will never return. */
export function functionErrorOutput(name, error) {
  const message = error instanceof Error ? error.message : String(error);
  return {
    error: "client_function_failed",
    function: name || "",
    message,
    instruction:
      "The client could not run this function. Continue without it and, if the value matters, "
      + "ask the caller to confirm it directly.",
  };
}

/**
 * The output item answering one call. It is sent on its own, and a SINGLE `response.create`
 * follows the whole batch: one `response.create` per call would start the follow-up before the
 * later outputs were added, and every extra request is refused as
 * `conversation_already_has_active_response`.
 */
export function functionOutputItemFrame(callId, outputText) {
  return {
    type: "conversation.item.create",
    item: { type: "function_call_output", call_id: callId, output: outputText },
  };
}

/** Ask for the answer that consumes the outputs sent above. */
export function responseCreateFrame() {
  return { type: "response.create" };
}

/** The frames answering a batch of calls: every output item, then one response request. */
export function functionOutputFrames(outputs) {
  const items = (outputs || []).map(
    ({ callId, outputText }) => functionOutputItemFrame(callId, outputText),
  );
  return items.length ? [...items, responseCreateFrame()] : [];
}

/** Keep the transcript history bounded; the demo only ever reads the newest few entries. */
export function appendTranscript(history, entry, limit = 20) {
  const next = [...(history || []), entry];
  return next.length > limit ? next.slice(next.length - limit) : next;
}

/**
 * Whether this client is the executor of `name`.
 *
 * Voice Live emits `function_call` items for SERVER-owned system tools too — `end_conversation`
 * is one — and those are not ours to answer: the service runs them and closes the session
 * itself, so a client `function_call_output` would inject a spurious result into a conversation
 * that is already terminating. A registered handler is the only signal that a call belongs to
 * this client; anything else is observed and left alone.
 */
export function isClientOwnedFunction(name, registry) {
  return typeof (registry || {})[String(name || "")] === "function";
}
