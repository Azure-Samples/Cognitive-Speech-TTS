// Copyright (c) Microsoft. All rights reserved.

export const STRUCTURED_INPUT_QUERY_PARAMETER = "structured_input";
export const STRUCTURED_INPUT_TYPES = Object.freeze([
  "string",
  "number",
  "integer",
  "boolean",
  "object",
  "array",
]);

const DEFAULT_VALUES = Object.freeze({
  string: "",
  number: "0",
  integer: "0",
  boolean: "false",
  object: "{}",
  array: "[]",
});

const HANDLEBARS_EXPRESSION = /\{\{\{?\s*([^{}]+?)\s*\}\}\}?/g;
const BLOCK_HELPERS_WITH_CONTEXT = new Set(["each", "if", "unless", "with"]);
const IGNORED_PATHS = new Set([
  ".",
  "else",
  "false",
  "null",
  "this",
  "true",
  "undefined",
]);

function structuredInputName(candidate) {
  let path = String(candidate || "").trim();
  while (path.startsWith("../")) path = path.slice(3);
  if (path.startsWith("./")) path = path.slice(2);
  if (!path || path.startsWith("@") || IGNORED_PATHS.has(path)) return null;
  if (/^["']|["']$/.test(path) || /^-?\d+(?:\.\d+)?$/.test(path)) return null;

  const root = path.split(/[.[\]]/, 1)[0];
  return /^[A-Za-z_][A-Za-z0-9_-]*$/.test(root) ? root : null;
}

function namesFromExpression(expression) {
  const normalized = expression.trim();
  if (!normalized || normalized.startsWith("!") || normalized.startsWith(">")) return [];
  if (normalized.startsWith("/")) return [];

  if (normalized.startsWith("#")) {
    const [helper, candidate] = normalized.slice(1).trim().split(/\s+/, 2);
    if (!BLOCK_HELPERS_WITH_CONTEXT.has(helper) || !candidate) return [];
    const name = structuredInputName(candidate);
    return name ? [name] : [];
  }

  // A multi-token expression is a helper invocation. Its first token is the helper name rather than
  // a structured input, and parsing arbitrary helper arguments would create false-positive fields.
  if (/\s/.test(normalized)) return [];
  const name = structuredInputName(normalized);
  return name ? [name] : [];
}

export function detectStructuredInputNames(templates) {
  const names = new Set();
  for (const template of Array.isArray(templates) ? templates : [templates]) {
    const text = String(template || "");
    for (const match of text.matchAll(HANDLEBARS_EXPRESSION)) {
      for (const name of namesFromExpression(match[1])) names.add(name);
    }
  }
  return [...names];
}

export function defaultStructuredInputValue(type) {
  if (!STRUCTURED_INPUT_TYPES.includes(type)) {
    throw new Error(`Unsupported structured input type: ${type}`);
  }
  return DEFAULT_VALUES[type];
}

export function reconcileStructuredInputConfigs(names, current = []) {
  const existing = new Map(current.map((item) => [item.name, item]));
  return names.map((name) => (
    existing.get(name) || {
      name,
      type: "string",
      defaultValue: defaultStructuredInputValue("string"),
    }
  ));
}

function parseDefaultValue(name, type, value) {
  const raw = String(value ?? "");
  if (type === "string") return raw;
  if (type === "boolean") {
    if (raw === "true") return true;
    if (raw === "false") return false;
    throw new Error(`Default for '${name}' must be true or false.`);
  }
  if (type === "number" || type === "integer") {
    const parsed = Number(raw);
    if (!raw.trim() || !Number.isFinite(parsed)) {
      throw new Error(`Default for '${name}' must be a valid ${type}.`);
    }
    if (type === "integer" && !Number.isInteger(parsed)) {
      throw new Error(`Default for '${name}' must be an integer.`);
    }
    return parsed;
  }

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error(`Default for '${name}' must be valid JSON.`);
  }
  if (type === "array" && !Array.isArray(parsed)) {
    throw new Error(`Default for '${name}' must be a JSON array.`);
  }
  if (
    type === "object"
    && (parsed === null || Array.isArray(parsed) || typeof parsed !== "object")
  ) {
    throw new Error(`Default for '${name}' must be a JSON object.`);
  }
  return parsed;
}

export function buildStructuredInputDefinitions(configs) {
  const definitions = {};
  for (const config of configs || []) {
    const name = String(config.name || "").trim();
    const type = String(config.type || "");
    if (!name) throw new Error("Structured input name is required.");
    if (!STRUCTURED_INPUT_TYPES.includes(type)) {
      throw new Error(`Unsupported structured input type for '${name}': ${type}`);
    }
    definitions[name] = {
      description: `Value for {{${name}}}`,
      default_value: parseDefaultValue(name, type, config.defaultValue),
      schema: { type },
    };
  }
  return definitions;
}

export function normalizeStructuredInputJson(value) {
  const raw = (value || "").trim();
  if (!raw) return "";

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error("Structured input must be valid JSON.");
  }

  if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("Structured input must be a JSON object.");
  }

  return JSON.stringify(parsed);
}
