// Copyright (c) Microsoft. All rights reserved.

import { dump, JSON_SCHEMA, load } from "js-yaml";

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function agentDefinitionToYaml(definition) {
  if (!isObject(definition)) {
    throw new Error("The selected agent does not have a definition");
  }
  return dump(
    { definition },
    {
      schema: JSON_SCHEMA,
      indent: 2,
      lineWidth: 100,
      noArrayIndent: false,
      noCompatMode: true,
      noRefs: true,
      sortKeys: false,
    },
  );
}

export function parseAgentDefinitionYaml(source) {
  let document;
  try {
    document = load(source, { schema: JSON_SCHEMA });
  } catch (error) {
    throw new Error(`Invalid YAML: ${error.message}`);
  }
  if (!isObject(document) || !isObject(document.definition)) {
    throw new Error("YAML must contain a top-level definition object");
  }
  if (document.definition.kind !== "voice") {
    throw new Error('definition.kind must be "voice"');
  }
  return document.definition;
}
