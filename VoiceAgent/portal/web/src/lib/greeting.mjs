// Copyright (c) Microsoft. All rights reserved.

export const GREETING_MODES = Object.freeze({
  NONE: "none",
  TEMPLATE: "template",
  LLM_GENERATED: "llm_generated",
});

export const GREETING_TOOL_CHOICES = Object.freeze(["none", "auto", "required"]);

export function buildGreetingConfig({
  mode,
  text,
  prompt,
  fallbackText,
  toolChoice,
}) {
  if (!mode || mode === GREETING_MODES.NONE) return null;

  if (mode === GREETING_MODES.TEMPLATE) {
    if (!text || !text.trim()) {
      throw new Error("Template greeting text is required.");
    }
    return { type: GREETING_MODES.TEMPLATE, text };
  }

  if (mode === GREETING_MODES.LLM_GENERATED) {
    if (!prompt || !prompt.trim()) {
      throw new Error("LLM-generated greeting prompt is required.");
    }
    const choice = toolChoice || "none";
    if (!GREETING_TOOL_CHOICES.includes(choice)) {
      throw new Error(`Unsupported greeting tool choice: ${choice}`);
    }
    const greeting = {
      type: GREETING_MODES.LLM_GENERATED,
      prompt,
      tool_choice: choice,
    };
    if (fallbackText && fallbackText.trim()) {
      greeting.fallback_text = fallbackText;
    }
    return greeting;
  }

  throw new Error(`Unsupported greeting mode: ${mode}`);
}
