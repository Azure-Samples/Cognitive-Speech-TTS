// Copyright (c) Microsoft. All rights reserved.

import assert from "node:assert/strict";
import test from "node:test";

import {
  STRUCTURED_INPUT_QUERY_PARAMETER,
  buildStructuredInputDefinitions,
  detectStructuredInputNames,
  normalizeStructuredInputJson,
  reconcileStructuredInputConfigs,
} from "./structuredInput.mjs";

test("uses the service structured-input query parameter name", () => {
  assert.equal(STRUCTURED_INPUT_QUERY_PARAMETER, "structured_input");
});

test("normalizes a structured-input JSON object", () => {
  assert.equal(
    normalizeStructuredInputJson(' { "customer_name": "Grace", "retry": 2 } '),
    '{"customer_name":"Grace","retry":2}',
  );
});

test("allows an omitted structured input", () => {
  assert.equal(normalizeStructuredInputJson("  "), "");
});

test("rejects invalid JSON and non-object values", () => {
  assert.throws(
    () => normalizeStructuredInputJson("{not-json"),
    /valid JSON/,
  );
  for (const value of ["null", "[]", '"Grace"', "42", "true"]) {
    assert.throws(
      () => normalizeStructuredInputJson(value),
      /JSON object/,
    );
  }
});

test("detects and deduplicates structured inputs across prompt templates", () => {
  assert.deepEqual(
    detectStructuredInputNames([
      "Help {{customer_name}} with {{order.id}}.",
      "Hello {{customer_name}}. {{#if membership_tier}}Welcome back.{{/if}}",
      "{{! ignored comment }} {{uppercase customer_name}}",
    ]),
    ["customer_name", "order", "membership_tier"],
  );
});

test("reconciles detected names while preserving edited type and default", () => {
  assert.deepEqual(
    reconcileStructuredInputConfigs(
      ["customer_name", "retry"],
      [{
        name: "customer_name",
        type: "object",
        defaultValue: '{"first":"Grace"}',
      }],
    ),
    [
      {
        name: "customer_name",
        type: "object",
        defaultValue: '{"first":"Grace"}',
      },
      {
        name: "retry",
        type: "string",
        defaultValue: "",
      },
    ],
  );
});

test("builds typed structured-input definitions", () => {
  const definitions = buildStructuredInputDefinitions([
    { name: "name", type: "string", defaultValue: "Grace" },
    { name: "temperature", type: "number", defaultValue: "0.5" },
    { name: "retry", type: "integer", defaultValue: "2" },
    { name: "vip", type: "boolean", defaultValue: "true" },
    { name: "profile", type: "object", defaultValue: '{"tier":"gold"}' },
    { name: "tags", type: "array", defaultValue: '["priority"]' },
  ]);

  assert.deepEqual(definitions.name, {
    description: "Value for {{name}}",
    default_value: "Grace",
    schema: { type: "string" },
  });
  assert.equal(definitions.temperature.default_value, 0.5);
  assert.equal(definitions.retry.default_value, 2);
  assert.equal(definitions.vip.default_value, true);
  assert.deepEqual(definitions.profile.default_value, { tier: "gold" });
  assert.deepEqual(definitions.tags.default_value, ["priority"]);
});

test("rejects defaults that do not match the selected type", () => {
  assert.throws(
    () => buildStructuredInputDefinitions([
      { name: "retry", type: "integer", defaultValue: "2.5" },
    ]),
    /must be an integer/,
  );
  assert.throws(
    () => buildStructuredInputDefinitions([
      { name: "profile", type: "object", defaultValue: "[]" },
    ]),
    /JSON object/,
  );
});
