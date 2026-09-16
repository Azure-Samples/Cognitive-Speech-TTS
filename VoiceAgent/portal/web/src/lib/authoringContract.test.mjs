// Copyright (c) Microsoft. All rights reserved.
// Tests for the mirrored POST /agents:generate contract. These exist because the form
// makes promises to the user about what the service accepts; if the mirror drifts, the
// form starts lying and the user finds out from a rejected request.

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  KIND,
  LIMITS,
  MODEL_TYPE_OPTIONS,
  MODEL_TYPE_SELF_DEPLOYED,
  NAME_PATTERN,
  USE_CASE_GROUPS,
  describeRejection,
} from "./authoringContract.mjs";

const valid = { name: "clinic-line", useCase: "inbound line for a dental clinic" };

describe("contract constants", () => {
  it("pins the limits Vienna's validator enforces", () => {
    // Transcribed from ValidationMessages.cs. A silent drift here is the whole failure
    // mode this module exists to prevent, so the numbers are asserted, not derived.
    assert.equal(LIMITS.name, 63);
    assert.equal(LIMITS.useCase, 128);
    assert.equal(LIMITS.goal, 4096);
    assert.equal(LIMITS.model, 256);
    assert.equal(LIMITS.description, 512);
  });

  it("offers omission as its own model_type choice", () => {
    // Omitting model_type is documented behaviour -- the service then resolves managed
    // plus its own model -- so it must be selectable, not merely the absence of input.
    assert.equal(MODEL_TYPE_OPTIONS[0].value, "");
    assert.deepEqual(
      MODEL_TYPE_OPTIONS.map((opt) => opt.value),
      ["", "managed", "self_deployed"],
    );
  });

  it("has exactly one accepted kind", () => {
    assert.equal(KIND, "voice");
  });
});

describe("USE_CASE_GROUPS", () => {
  const options = USE_CASE_GROUPS.flatMap((g) => g.items);

  it("offers the four portal sections and their eight scenarios", () => {
    assert.deepEqual(
      USE_CASE_GROUPS.map((g) => g.label),
      ["Finance", "Healthcare", "Travel", "Education"],
    );
    assert.equal(options.length, 8);
    assert.equal(new Set(options).size, options.length, "duplicate option value");
  });

  it("offers nothing the service would reject", () => {
    // The list is a suggestion, but the form still has to be honest: an option the user can
    // pick and the service then refuses is the one failure this file exists to prevent.
    for (const useCase of options) {
      assert.ok(useCase.trim(), "option must be a non-empty string");
      assert.ok(
        useCase.length <= LIMITS.useCase,
        `"${useCase}" is ${useCase.length} chars, over the ${LIMITS.useCase} cap`,
      );
      assert.equal(
        describeRejection({ name: "clinic-line", useCase }),
        null,
        `"${useCase}" would be rejected`,
      );
    }
  });
});

describe("describeRejection", () => {
  it("accepts a request the service would accept", () => {
    assert.equal(describeRejection(valid), null);
  });

  it("requires a name", () => {
    assert.match(describeRejection({ ...valid, name: "  " }), /name is required/i);
  });

  it("applies the DNS label rule rather than length alone", () => {
    // Vienna validates the name with IsValidDnsName, so a short but malformed name is
    // rejected there. Checking length only would let it through to a 400.
    assert.ok(NAME_PATTERN.test("a1"));
    assert.ok(NAME_PATTERN.test("clinic-line-2"));
    assert.ok(!NAME_PATTERN.test("-leading"));
    assert.ok(!NAME_PATTERN.test("trailing-"));
    assert.ok(!NAME_PATTERN.test("under_score"));

    assert.match(describeRejection({ ...valid, name: "-bad" }), /start and end/i);
  });

  it("rejects each field one character past its cap", () => {
    for (const [field, cap] of [
      ["name", LIMITS.name],
      ["useCase", LIMITS.useCase],
      ["goal", LIMITS.goal],
      ["model", LIMITS.model],
      ["description", LIMITS.description],
    ]) {
      const overflowing = field === "name" ? "a".repeat(cap + 1) : "a".repeat(cap + 1);
      const reason = describeRejection({ ...valid, [field]: overflowing });

      assert.ok(reason, `${field} at ${cap + 1} should be rejected`);
      assert.match(reason, new RegExp(String(cap)));
    }
  });

  it("accepts each field exactly at its cap", () => {
    assert.equal(describeRejection({ ...valid, useCase: "a".repeat(LIMITS.useCase) }), null);
    assert.equal(describeRejection({ ...valid, goal: "a".repeat(LIMITS.goal) }), null);
    assert.equal(
      describeRejection({ ...valid, description: "a".repeat(LIMITS.description) }),
      null,
    );
  });

  it("treats use_case as optional", () => {
    // Optional on both sides. Voice Live opens the generator's brief on a general-purpose
    // assistant when it is absent, so omitting it is a real request rather than a
    // malformed one -- and `goal` still carries whatever the caller wants to say.
    assert.equal(describeRejection({ name: "clinic-line" }), null);
    assert.equal(describeRejection({ ...valid, useCase: "" }), null);
    assert.equal(describeRejection({ ...valid, useCase: "   " }), null);
  });

  it("rejects a model_type outside the accepted set", () => {
    // Closed on both sides now. `hosted_agent` is a real VoiceModelTypes value but is not
    // generatable -- the target agent owns its prompt and tools.
    assert.match(describeRejection({ ...valid, modelType: "future_model_type" }), /must be one of/);
    assert.match(describeRejection({ ...valid, modelType: "hosted_agent" }), /must be one of/);
    assert.equal(describeRejection({ ...valid, modelType: "managed" }), null);
  });

  it("requires a model only for self_deployed", () => {
    assert.match(
      describeRejection({ ...valid, modelType: MODEL_TYPE_SELF_DEPLOYED }),
      /required when model_type is self_deployed/,
    );
    assert.equal(
      describeRejection({ ...valid, modelType: MODEL_TYPE_SELF_DEPLOYED, model: "my-dep" }),
      null,
    );
    assert.equal(describeRejection({ ...valid, modelType: "managed" }), null);
    assert.equal(describeRejection({ ...valid, modelType: "" }), null);
  });

  it("reports the first failure in the order the service checks", () => {
    // Two problems at once should surface the name, because that is what Vienna rejects
    // first -- otherwise fixing the reported field just reveals another rejection.
    const reason = describeRejection({ name: "", useCase: "a".repeat(LIMITS.useCase + 1) });

    assert.match(reason, /name is required/i);
  });
});
