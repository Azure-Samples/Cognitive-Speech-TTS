// Copyright (c) Microsoft. All rights reserved.
// Pure presentation helpers for the generate review stage: turning an agent
// definition into the chips and the YAML-ish body the reviewer reads. Kept out of
// the component so the formatting rules can be tested without rendering React.

/* Keys renderDefinition orders by hand so the reader meets them in a useful sequence.
 * Being listed here does NOT mean a key may be summarised: every branch below prints
 * the whole value. Anything absent falls through to the generic tail. */
const ORDERED_KEYS = ["kind", "model_type", "model", "instructions", "greeting", "tools"];

/* Prose arrives with newlines in it. Interpolated into `key: value` the continuation
 * lines land at column zero and read as sibling fields -- a description ending in
 * "kind: spoof" renders a `kind:` line that was never in the definition. A block scalar
 * is both correct YAML and unambiguous to a human. */
function pushScalar(lines, key, value, indent = "") {
  const text = String(value);
  if (!text.includes("\n")) {
    lines.push(`${indent}${key}: ${text}`);
    return;
  }
  lines.push(`${indent}${key}: |-`);
  for (const line of text.split("\n")) {
    lines.push(line ? `${indent}  ${line}` : "");
  }
}

/* Objects and arrays are dumped whole. We cannot know their shape -- and a summary is
 * how a reviewer ends up approving a tool whose server URL they were never shown. */
function pushValue(lines, key, value, indent = "") {
  if (value === undefined || value === null) return;
  if (typeof value === "object") {
    lines.push(`${indent}${key}:`);
    const json = JSON.stringify(value, null, 2).split("\n").join(`\n${indent}  `);
    lines.push(`${indent}  ${json}`);
    return;
  }
  pushScalar(lines, key, value, indent);
}

/* The definition as YAML-ish text. Not a JSON dump: instructions are prose with newlines
 * in them, and JSON.stringify turns those into escapes that nobody can read.
 *
 * `identity` comes from outside the definition -- name, version and draft live on the
 * agent resource, not on the definition it holds -- but they belong at the top of what a
 * reader sees. The Connection dropdown below lists agents by name, and without the name
 * here there is nothing tying what you just read to what you are about to select. */
export function renderDefinition(definition, identity) {
  const lines = [];

  if (identity) {
    for (const key of ["name", "version", "description"]) {
      const value = identity[key];
      if (value !== undefined && value !== null && value !== "") {
        pushScalar(lines, key, value);
      }
    }
    /* Only worth a line when true: every non-draft agent would otherwise carry
     * `draft: false`, which is noise on the field that matters least. */
    if (identity.draft) lines.push("draft: true");
  }

  for (const key of ["kind", "model_type", "model"]) {
    if (definition[key]) pushScalar(lines, key, definition[key]);
  }

  if (definition.instructions) pushScalar(lines, "instructions", definition.instructions);

  /* Every greeting field, not just type and text. An llm_generated greeting carries the
   * `prompt` that decides what the agent opens with and the `fallback_text` it falls back
   * to; showing only `type: llm_generated` tells the reviewer nothing about either while
   * looking like it was reviewed. */
  const greeting = definition.greeting;
  if (greeting && typeof greeting === "object") {
    lines.push("greeting:");
    for (const [key, value] of Object.entries(greeting)) {
      pushValue(lines, key, value, "  ");
    }
  } else if (greeting) {
    pushScalar(lines, "greeting", greeting);
  }

  /* Whole objects. Summarising to `tools: mcp, mcp, toolbox` made two entirely different
   * tool sets render byte-for-byte identically, hiding the server URLs, allowlists and
   * approval policy that decide what the agent can reach. */
  if (Array.isArray(definition.tools) && definition.tools.length) {
    pushValue(lines, "tools", definition.tools);
  }

  /* Everything the branches above did not claim -- `audio`, `store`, `output_modalities`,
   * `avatar`, `handoff`, and whatever the service adds next. The point of this panel is to
   * show what was generated, so an unrecognised field has to appear rather than be
   * silently dropped; a reviewer cannot question a field they were never shown. */
  for (const [key, value] of Object.entries(definition)) {
    if (ORDERED_KEYS.includes(key)) continue;
    pushValue(lines, key, value);
  }

  return lines.join("\n");
}

/* Fields worth seeing first, in the order a reader asks about them: what it
 * runs on, then how it sounds, then how it decides you stopped talking. The
 * rest stays in the definition body below. */
export function summaryChips(definition) {
  if (!definition) return [];
  const audio = definition.audio || {};
  const output = audio.output || {};
  const turnDetection = (audio.input || {}).turn_detection || {};
  const chips = [];
  if (definition.model) chips.push(["model", definition.model]);
  if (definition.model_type) chips.push(["hosting", definition.model_type]);
  /* Voice arrives flattened by the service's compatibility layer, but a direct Voice
   * Live response still nests it. Read both so this panel does not depend on
   * which side of that normalisation the caller sat on. */
  const voice = typeof output.voice === "string" ? output.voice : (output.voice || {}).name;
  if (voice) chips.push(["voice", voice]);
  if (turnDetection.type) chips.push(["turn detection", turnDetection.type]);
  return chips;
}

/* The two decisions the generate round trip makes about its own response, pulled out of
 * the component so they can be tested without a DOM. Both protect the same invariant --
 * the definition on screen describes the agent Connect will talk to -- and both are the
 * kind of guard that is easy to delete during a refactor and produces no visible symptom
 * until someone is speaking to the wrong agent. */

/**
 * The definition inside a `/agents:generate` response, or null when there is not one.
 *
 * A 200 carrying no definition is not a success anyone can present: reporting one puts
 * "generated" on screen beside an empty review while selecting an agent whose displayed
 * model and voice are invented, so the user connects to something they were never shown.
 */
export function definitionFromResponse(data) {
  const latest = (data && data.versions && data.versions.latest) || {};
  const definition = latest.definition || {};
  return Object.keys(definition).length ? { definition, latest } : null;
}

/**
 * Whether a landed generate response should still be applied.
 *
 * A generate the user walked away from must have no effect at all -- not on the review,
 * and not on which agent is selected, because that is what Connect talks to. Connecting
 * counts as walking away: Connect sits outside the authoring panes and is enabled as soon
 * as an agent is selected, so it can be pressed while a generate is still outstanding, and
 * the session binds to whatever was selected at that moment.
 */
export function shouldApplyGenerateResponse({ requestToken, currentToken, isConnected }) {
  return requestToken === currentToken && !isConnected;
}
