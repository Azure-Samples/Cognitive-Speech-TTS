// Copyright (c) Microsoft. All rights reserved.
// Browser-level regression coverage; no Azure credentials or live agent creation.
import { test, expect } from "@playwright/test";
import { mountStudio, selectTab, CONFIG } from "./studio-fixtures.mjs";

test("default editor creates the same managed agent and selects it in the playground", async ({ page }) => {
  const api = await mountStudio(page);
  await page.getByRole("textbox", { name: /^Agent name/ }).fill("studio-test");
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect(page.getByLabel("Session agent", { exact: true })).toHaveValue("studio-test");
  expect(api.creates).toHaveLength(1);
  const definition = api.creates[0].definition;
  expect(definition).toMatchObject({
    kind: "voice", model_type: "managed", model: "gpt-realtime", store: true,
    instructions: "You are a helpful voice assistant. Respond naturally and concisely.",
    audio: { input: { echo_cancellation: { reference_source: "client", channels: 2 } } },
  });
  await expect(page.getByRole("button", { name: "Edit definition" })).toBeEnabled();
  expect(api.errors).toEqual([]);
});

test("all MCP, knowledge, toolbox and system-tool settings survive mode and source switches", async ({ page }) => {
  const api = await mountStudio(page);
  await selectTab(page, "Tools");
  await page.getByRole("checkbox", { name: /^MCP server/ }).check();
  await page.getByLabel("Authentication preset").selectOption("apikey");
  await page.getByLabel("Allowed MCP tools").fill("add, subtract");
  await page.getByRole("checkbox", { name: /^Approve MCP calls/ }).check();
  await page.getByRole("checkbox", { name: /^Foundry IQ/ }).check();
  await page.getByLabel("Allowed knowledge base tools").fill("knowledge_base_retrieve");
  await page.getByRole("checkbox", { name: /^Approve knowledge base calls/ }).check();
  await page.getByRole("checkbox", { name: /^Foundry Toolbox/ }).check();
  await page.getByLabel("Allowed toolbox tools").fill("web_search");
  await page.getByRole("checkbox", { name: /^End conversation/ }).check();
  await page.getByLabel("End-conversation instructions").fill("Say goodbye first.");
  await page.getByRole("button", { name: "Generate", exact: true }).click();
  await selectTab(page, "Tools");
  await expect(page.getByLabel("Allowed MCP tools")).toHaveValue("add, subtract");
  await page.getByRole("button", { name: "Configure", exact: true }).click();
  await selectTab(page, "Agent");
  await page.getByLabel("Model source", { exact: true }).selectOption("hosted_agent");
  await selectTab(page, "Tools");
  await expect(page.getByRole("checkbox", { name: /^MCP server/ })).toBeDisabled();
  await selectTab(page, "Agent");
  await page.getByLabel("Model source", { exact: true }).selectOption("deployment");
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect.poll(() => api.creates.length).toBe(1);
  expect(api.creates[0].definition).toMatchObject({ model_type: "self_deployed", model: "my-realtime" });
  expect(api.creates[0].definition.tools).toEqual([
    { type: "mcp", server_label: "apikey", project_connection_id: "/connections/apikey",
      require_approval: "always", allowed_tools: ["add", "subtract"] },
    { type: "toolbox", toolbox_name: "search-tools", toolbox_version: "2", allowed_tools: ["web_search"] },
    { type: "mcp", server_label: "knowledge", server_url: CONFIG.mcpAuthPresets[3].server_url,
      project_connection_id: "/connections/knowledge", require_approval: "always", allowed_tools: ["knowledge_base_retrieve"] },
    { type: "system", name: "end_conversation", description: "Say goodbye first." },
  ]);
  expect(api.errors).toEqual([]);
});

test("direct MCP authorization remains editable and is masked", async ({ page }) => {
  const api = await mountStudio(page);
  await selectTab(page, "Tools");
  await page.getByRole("checkbox", { name: /^MCP server/ }).check();
  await page.getByLabel("Authentication preset").selectOption("noauth");
  await page.getByLabel("Authorization token").fill("test-token-not-a-secret");
  await expect(page.getByLabel("Authorization token")).toHaveAttribute("type", "password");
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect.poll(() => api.creates.length).toBe(1);
  expect(api.creates[0].definition.tools[0]).toMatchObject({
    server_url: "https://mcp.example/noauth/mcp", authorization: "test-token-not-a-secret",
  });
});

test("manual prompt, voice, greeting, storage and avatar options reach the request intact", async ({ page }) => {
  const api = await mountStudio(page);
  await page.getByLabel("Instructions", { exact: false }).first().fill("Use my custom prompt.");
  await page.getByRole("checkbox", { name: /^Save conversations/ }).uncheck();
  await page.getByLabel("First message").selectOption("llm_generated");
  await page.getByLabel("Greeting prompt", { exact: true }).fill("Welcome the caller.");
  await page.getByLabel("Fallback greeting").fill("Hello.");
  await page.getByLabel("Greeting tool choice").selectOption("auto");
  await selectTab(page, "Voice");
  await page.getByRole("checkbox", { name: /^Video avatar/ }).check();
  await expect(page.getByRole("checkbox", { name: /^Live-reference/ })).not.toBeChecked();
  await expect(page.getByRole("combobox", { name: "Voice", exact: true }).locator("option[value=alloy]")).toHaveCount(0);
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect.poll(() => api.creates.length).toBe(1);
  expect(api.creates[0].definition).toMatchObject({
    instructions: "Use my custom prompt.", store: false, avatar: { type: "video-avatar" },
    greeting: { type: "llm_generated", prompt: "Welcome the caller.", fallback_text: "Hello.", tool_choice: "auto" },
  });
  expect(api.creates[0].definition.audio.input.echo_cancellation).toBeUndefined();
});

test("hosted agent wrappers preserve target validation and exclude target-owned fields", async ({ page }) => {
  const api = await mountStudio(page);
  await page.getByLabel("Model source", { exact: true }).selectOption("hosted_agent");
  await page.getByLabel("Target hosted agent").fill("hosted-target");
  await page.getByLabel("Target version").fill("1");
  await page.getByLabel("First message").selectOption("template");
  await page.getByLabel("Greeting text").fill("Hello hosted agent.");
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect.poll(() => api.creates.length).toBe(1);
  const definition = api.creates[0].definition;
  expect(definition).toMatchObject({
    model_type: "hosted_agent", target_agent: { name: "hosted-target", version: "1" },
    greeting: { type: "template", text: "Hello hosted agent." },
  });
  for (const key of ["model", "instructions", "tools", "handoff", "subagent_config"]) expect(definition[key]).toBeUndefined();
  expect(api.errors).toEqual([]);
});

test("greeting belongs to Agent and survives voice edits and authoring-mode switches", async ({ page }) => {
  const api = await mountStudio(page);
  const agentPanel = page.locator("#editor-panel-agent");
  const voicePanel = page.locator("#editor-panel-voice");
  await expect(agentPanel.getByLabel("First message")).toHaveValue("none");
  await expect(voicePanel.getByLabel("First message")).toHaveCount(0);
  await agentPanel.getByLabel("First message").selectOption("template");
  await agentPanel.getByLabel("Greeting text").fill("Welcome back, {{name}}.");
  await selectTab(page, "Voice");
  await expect(page.getByLabel("First message")).not.toBeVisible();
  await page.getByRole("combobox", { name: "Voice", exact: true }).selectOption("en-US-AndrewNeural");
  await selectTab(page, "Agent");
  await expect(agentPanel.getByLabel("Greeting text")).toHaveValue("Welcome back, {{name}}.");
  await page.getByRole("button", { name: "Generate", exact: true }).click();
  await page.getByRole("button", { name: "Configure", exact: true }).click();
  await expect(agentPanel.getByLabel("First message")).toHaveValue("template");
  await expect(agentPanel.getByLabel("Greeting text")).toHaveValue("Welcome back, {{name}}.");
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect.poll(() => api.creates.length).toBe(1);
  expect(api.creates[0].definition.greeting).toEqual({ type: "template", text: "Welcome back, {{name}}." });
  expect(api.creates[0].definition.audio.output.voice).toBe("en-US-AndrewNeural");
  expect(api.creates[0].definition.audio.output.voice_type).toBe("azure-standard");
  expect(api.creates[0].definition.audio.greeting).toBeUndefined();
  expect(api.errors).toEqual([]);
});

test("handoff, selected subagents and response policy survive navigation", async ({ page }) => {
  const api = await mountStudio(page);
  await selectTab(page, "Workflow");
  await page.getByRole("checkbox", { name: /^Customer-care handoff/ }).check();
  await page.getByRole("button", { name: "List agents", exact: true }).click();
  await page.getByRole("checkbox", { name: /billing-specialist/ }).check();
  await page.getByText("Response policy · billing-specialist", { exact: true }).click();
  await page.getByRole("checkbox", { name: /^Immediate acknowledgement/ }).check();
  await page.getByLabel("Gap-filling interval").fill("10");
  await selectTab(page, "Agent");
  await selectTab(page, "Workflow");
  await expect(page.getByRole("checkbox", { name: /billing-specialist/ })).toBeChecked();
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect.poll(() => api.creates.length).toBe(1);
  const definition = api.creates[0].definition;
  expect(definition.instructions).toContain("Contoso Mobile");
  expect(definition.handoff.nodes).toHaveLength(2);
  expect(definition.subagent_config).toEqual({
    subagents: [{
      agent_name: "billing-specialist", agent_capabilities: "Resolves billing",
      response_policy: {
        immediate_ack: true, gap_filling_interval: 10, enable_delta_progress: false, progress_update_interval: 15,
      },
    }],
  });
  expect(api.errors).toEqual([]);
});

test("structured inputs detect active templates, retain typed defaults and reach the session URL", async ({ page }) => {
  const api = await mountStudio(page);
  await page.getByLabel("Instructions", { exact: false }).first().fill("Assist {{customer_name}}. Priority {{priority}}. Debug {{debug}}.");
  await page.getByLabel("Default value for customer_name").fill("Ada");
  await page.getByLabel("Type for priority", { exact: true }).selectOption("integer");
  await page.getByLabel("Default value for priority").fill("7");
  await page.getByLabel("Type for debug", { exact: true }).selectOption("boolean");
  await page.getByLabel("Default value for debug").selectOption("true");
  await page.getByLabel("First message").selectOption("template");
  await page.getByLabel("Greeting text").fill("Hello {{customer_name}} from {{account.id}}.");
  await page.getByLabel("Type for account", { exact: true }).selectOption("object");
  await page.getByLabel("Default value for account").fill('{"id":"A1"}');
  await selectTab(page, "Voice");
  await selectTab(page, "Agent");
  await expect(page.getByLabel("Default value for customer_name")).toHaveValue("Ada");
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect.poll(() => api.creates.length).toBe(1);
  const definition = api.creates[0].definition;
  expect(definition.structured_inputs).toEqual({
    customer_name: { description: "Value for {{customer_name}}", default_value: "Ada", schema: { type: "string" } },
    priority: { description: "Value for {{priority}}", default_value: 7, schema: { type: "integer" } },
    debug: { description: "Value for {{debug}}", default_value: true, schema: { type: "boolean" } },
    account: { description: "Value for {{account}}", default_value: { id: "A1" }, schema: { type: "object" } },
  });
  await page.getByText("Session settings", { exact: true }).click();
  await expect(page.getByText("Declared keys:", { exact: false })).toContainText("customer_name, priority, debug, account");
  const values = { customer_name: "Grace", priority: 2, debug: false, account: { id: "B&+ 张" } };
  await page.getByLabel("Structured input JSON").fill(JSON.stringify(values, null, 2));
  await page.getByText("Session settings", { exact: true }).click();
  await api.start(api.creates[0].name);
  expect(new URL(api.sockets[0].url()).searchParams.get("structured_input")).toBe(JSON.stringify(values));
  expect(await page.locator(".main").innerText()).not.toContain("Grace");
  expect(api.versions).toHaveLength(0);
  expect(api.errors).toEqual([]);
});

test("structured input defaults validate before creation and omit inactive greetings", async ({ page }) => {
  const api = await mountStudio(page);
  await page.getByLabel("First message").selectOption("llm_generated");
  await page.getByLabel("Greeting prompt", { exact: true }).fill("Greet {{name}}.");
  await page.getByLabel("Fallback greeting").fill("Hello {{fallback_name}}.");
  await expect(page.getByLabel("Type for name", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Type for fallback_name", { exact: true })).toBeVisible();
  await page.getByLabel("First message").selectOption("none");
  await expect(page.getByLabel("Type for name", { exact: true })).toHaveCount(0);
  await page.getByLabel("Instructions", { exact: false }).first().fill("Use {{items}}.");
  await page.getByLabel("Type for items", { exact: true }).selectOption("array");
  await page.getByLabel("Default value for items").fill("{}");
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("must be a JSON array");
  expect(api.creates).toHaveLength(0);
  await page.getByLabel("Default value for items").fill('["one","two"]');
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect.poll(() => api.creates.length).toBe(1);
  expect(Object.keys(api.creates[0].definition.structured_inputs)).toEqual(["items"]);
  expect(api.creates[0].definition.structured_inputs.items.default_value).toEqual(["one", "two"]);
  expect(api.errors).toEqual([]);
});

test("invalid structured input never opens a socket and changing agents clears the session override", async ({ page }) => {
  const api = await mountStudio(page);
  await page.getByLabel("Session agent", { exact: true }).selectOption("realtime-agent");
  for (const invalid of ["[]", "null", '{"broken":']) {
    await page.getByText("Session settings", { exact: true }).click();
    await page.getByLabel("Structured input JSON").fill(invalid);
    await page.getByText("Session settings", { exact: true }).click();
    await page.getByRole("button", { name: "Connect & start session" }).click();
    await expect(page.getByRole("status").filter({ hasText: "invalid structured input" })).toBeVisible();
    expect(api.sockets).toHaveLength(0);
  }
  await page.getByLabel("Session agent", { exact: true }).selectOption("cascaded-agent");
  await page.getByText("Session settings", { exact: true }).click();
  await expect(page.getByLabel("Structured input JSON")).toHaveValue("");
  await page.getByText("Session settings", { exact: true }).click();
  await api.start("cascaded-agent");
  expect(new URL(api.sockets[0].url()).searchParams.has("structured_input")).toBe(false);
  expect(api.errors).toEqual([]);
});

test("workflow remains visible beside the session without unmounting conversation media", async ({ page }) => {
  const api = await mountStudio(page);
  await selectTab(page, "Workflow");
  await page.getByRole("checkbox", { name: /^Customer-care handoff/ }).check();
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect.poll(() => api.creates.length).toBe(1);
  await expect(page.getByRole("button", { name: /Agent Debug.*Expand panel/ })).toHaveAttribute("aria-expanded", "false");
  await api.start(api.creates[0].name);
  await expect(page.getByRole("button", { name: /Agent Debug.*Collapse panel/ })).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("button", { name: /Agent Creation.*Expand panel/ })).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator(".handoff-graph")).toBeVisible();
  await expect(page.getByRole("region", { name: "Agent debug" })).toBeVisible();
  await expect(page.locator(".review-session audio")).toHaveCount(1);
  await expect(page.locator(".review-session")).toBeVisible();
  await page.getByText("Session settings", { exact: true }).click();
  await page.getByRole("checkbox", { name: /^Developer mode/ }).check();
  await page.getByText("Session settings", { exact: true }).click();
  await expect(page.locator(".timeline.developer-events")).toBeVisible();
  await expect(page.locator(".event-type").filter({ hasText: "session.created" })).toBeVisible();
  await page.getByLabel("Filter protocol frames").fill("no-match");
  await expect(page.locator(".event-row")).toHaveCount(0);
  await page.getByLabel("Filter protocol frames").fill("session.");
  await expect(page.locator(".event-row")).not.toHaveCount(0);
  await page.getByRole("button", { name: "Clear chat" }).click();
  await expect(page.locator(".event-row")).toHaveCount(0);
  expect(api.errors).toEqual([]);
});

test("agent creation and agent debug panels collapse independently", async ({ page }) => {
  await mountStudio(page);
  await expect(page.getByRole("button", { name: /Agent Creation.*Collapse panel/ })).toHaveAttribute("aria-expanded", "true");
  const debugToggle = page.getByRole("button", { name: /Agent Debug.*Expand panel/ });
  await debugToggle.click();
  await expect(page.getByRole("button", { name: /Agent Debug.*Collapse panel/ })).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("button", { name: /Agent Creation.*Expand panel/ })).toHaveAttribute("aria-expanded", "false");

  const creationToggle = page.getByRole("button", { name: /Agent Creation.*Expand panel/ });
  await creationToggle.click();
  await expect(page.getByRole("button", { name: /Agent Creation.*Collapse panel/ })).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("button", { name: /Agent Debug.*Expand panel/ })).toHaveAttribute("aria-expanded", "false");
});

test("agent URLs select without automatically starting a credentialed session", async ({ page }) => {
  const api = await mountStudio(page, {}, "/demo/?agent=realtime-agent&autostart=1");
  await expect(page.getByLabel("Session agent", { exact: true })).toHaveValue("realtime-agent");
  await page.waitForLoadState("networkidle");
  expect(api.sockets).toHaveLength(0);
  await expect(page.getByRole("button", { name: "Connect & start session" })).toBeEnabled();
  expect(api.errors).toEqual([]);
});

test("a prompt specialist can still be created inline", async ({ page }) => {
  const api = await mountStudio(page);
  await selectTab(page, "Workflow");
  await page.getByText("Create a text subagent", { exact: true }).click();
  await page.getByLabel("Subagent name").fill("new-specialist");
  await page.getByLabel("Specialist capabilities").fill("Researches orders");
  await page.getByRole("button", { name: "Create text agent", exact: true }).click();
  await expect.poll(() => api.creates.length).toBe(1);
  expect(api.creates[0].definition.kind).toBe("prompt");
  await expect(page.getByRole("checkbox", { name: /new-specialist/ })).toBeChecked();
});

test("Generate retains defaults, optional inputs, shared tools and definition review", async ({ page }) => {
  const api = await mountStudio(page);
  await selectTab(page, "Tools");
  await page.getByRole("checkbox", { name: /^End conversation/ }).check();
  await page.getByRole("button", { name: "Generate", exact: true }).click();
  await page.getByLabel("Goal").fill("Help callers with billing.");
  await page.getByLabel("Generated agent name").fill("generated-agent");
  await page.getByLabel("Use case").selectOption("Retail banking self-service");
  await page.getByRole("button", { name: "Generate agent", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Definition", exact: true })).toHaveAttribute("aria-selected", "true");
  expect(api.generates).toEqual([{
    name: "generated-agent", kind: "voice", goal: "Help callers with billing.",
    use_case: "Retail banking self-service", draft: false, tools: [{ type: "system", name: "end_conversation" }],
  }]);
  await expect(page.locator(".review-definition")).toContainText("Generated instructions");
  // The chat and its media sinks stay mounted behind the review.
  await expect(page.locator(".review-session audio")).toHaveCount(1);
  await page.getByRole("tab", { name: "Session", exact: true }).click();
  await expect(page.getByLabel("Message your agent")).toBeVisible();
  expect(api.errors).toEqual([]);
});

test("Generate validates BYOM and sends explicit generation settings", async ({ page }) => {
  const api = await mountStudio(page);
  await page.getByRole("button", { name: "Generate", exact: true }).click();
  await page.getByText("Generation options", { exact: true }).click();
  await page.getByLabel("Generation model source").selectOption("self_deployed");
  await page.getByRole("button", { name: "Generate agent", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Model is required");
  expect(api.generates).toHaveLength(0);
  await page.getByLabel("Generation model", { exact: true }).fill("my-cascaded");
  await page.getByLabel("Generated agent description").fill("Generated description");
  await page.getByRole("checkbox", { name: /^Create as a draft/ }).check();
  await page.getByRole("button", { name: "Generate agent", exact: true }).click();
  await expect.poll(() => api.generates.length).toBe(1);
  expect(api.generates[0]).toMatchObject({
    model_type: "self_deployed", model: "my-cascaded", draft: true, description: "Generated description",
  });
});

test("leaving Generate still drops its late result instead of changing the selected agent", async ({ page }) => {
  const api = await mountStudio(page);
  let release;
  api.generateGate = new Promise((resolve) => { release = resolve; });
  await page.getByLabel("Session agent", { exact: true }).selectOption("realtime-agent");
  await page.getByRole("button", { name: "Generate", exact: true }).click();
  await page.getByRole("button", { name: "Generate agent", exact: true }).click();
  await expect.poll(() => api.generates.length).toBe(1);
  await page.getByRole("button", { name: "Configure", exact: true }).click();
  release();
  await expect(page.getByRole("button", { name: "Create agent", exact: true })).toBeEnabled();
  await expect(page.getByLabel("Session agent", { exact: true })).toHaveValue("realtime-agent");
  await expect(page.locator(".review-definition")).toHaveCount(0);
});

test("YAML editing creates a new version and preserves unknown definition fields", async ({ page }) => {
  const api = await mountStudio(page);
  await page.getByLabel("Session agent", { exact: true }).selectOption("cascaded-agent");
  await expect(page.locator(".selected-agent-meta")).toContainText("en-US-AndrewNeural");
  await page.getByRole("button", { name: "Edit definition" }).click();
  const editor = page.getByLabel("Agent definition YAML");
  await expect(editor).toContainText("kind: voice");
  await expect(editor).toHaveCSS("font-size", "15px");
  const yaml = await editor.inputValue();
  await editor.fill(`${yaml}\n  max_output_tokens: 1024\n  include:\n    - item.input_audio_transcription.logprobs\n`);
  await page.getByRole("button", { name: "Save as new version" }).click();
  await expect.poll(() => api.versions.length).toBe(1);
  expect(api.versions[0].definition).toMatchObject({ max_output_tokens: 1024, include: ["item.input_audio_transcription.logprobs"] });
  await expect(page.locator(".definition-save-state")).toContainText("Version 2 created");
  await page.getByRole("button", { name: "Close definition editor" }).click();
  await expect(page.locator(".selected-agent-meta")).toContainText("v2");
});

test("session overrides affect only the WebSocket and controls lock while connected", async ({ page }) => {
  const api = await mountStudio(page);
  await page.getByLabel("Session agent", { exact: true }).selectOption("realtime-agent");
  await page.getByText("Session settings", { exact: true }).click();
  await page.getByLabel("Voice override", { exact: true }).selectOption("marin");
  await page.getByLabel("Conversation storage override").selectOption("false");
  await page.getByText("Session settings", { exact: true }).click();
  await api.start();
  const url = new URL(api.sockets[0].url());
  expect(url.searchParams.get("voiceOverride")).toBe("marin");
  expect(url.searchParams.get("store")).toBe("false");
  expect(api.versions).toHaveLength(0);
  await expect(page.getByLabel("Session agent", { exact: true })).toBeDisabled();
  await expect(page.getByLabel("Agent backend", { exact: true })).toBeDisabled();
  const creationPanel = page.getByRole("button", { name: /Agent Creation.*Expand panel/ });
  await expect(creationPanel).toHaveAttribute("aria-expanded", "false");
  await creationPanel.click();
  await expect(page.getByRole("button", { name: "Create agent", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Edit definition" })).toBeDisabled();
  await page.getByRole("button", { name: "Mute mic" }).click();
  await expect(page.getByRole("button", { name: "Unmute mic" })).toBeVisible();
  await page.getByRole("button", { name: "Stop session" }).click();
  await expect(page.getByLabel("Session agent", { exact: true })).toBeEnabled();
});

test("echo-reference modes and WebRTC restrictions remain available", async ({ page }) => {
  const api = await mountStudio(page);
  await page.getByLabel("Session agent", { exact: true }).selectOption("echo-agent");
  await page.getByText("Session settings", { exact: true }).click();
  await expect(page.getByLabel("Transport", { exact: true })).toHaveValue("websocket");
  await expect(page.getByLabel("Transport", { exact: true }).locator("option[value=webrtc]")).toBeDisabled();
  await expect(page.getByLabel("Client reference audio").locator("option")).toHaveCount(3);
  await page.getByLabel("Session agent", { exact: true }).selectOption("cascaded-agent");
  await expect(page.getByLabel("Voice override", { exact: true }).locator("option[value=marin]")).toHaveCount(0);
  await page.getByLabel("Transport", { exact: true }).selectOption("webrtc");
  await page.getByText("Session settings", { exact: true }).click();
  await page.getByRole("button", { name: "Connect & start session" }).click();
  await expect.poll(() => api.sockets.length).toBe(1);
  expect(new URL(api.sockets[0].url()).searchParams.get("transport")).toBe("webrtc");
});

test("message sending, MCP cards, trace and persisted links work in the playground", async ({ page, context }) => {
  const api = await mountStudio(page);
  await api.start();
  await page.getByLabel("Message your agent").fill("Please add 5 and 7.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect.poll(() => api.messages.some((message) => message.type === "response.create")).toBe(true);
  api.send({ type: "response.created", response: { id: "resp-tool" } });
  api.send({ type: "response.output_item.added", item: { id: "mcp-1", type: "mcp_call", name: "add", server_label: "math" } });
  api.send({ type: "response.mcp_call_arguments.done", item_id: "mcp-1", arguments: '{"a":5,"b":7}' });
  api.send({ type: "response.done", response: { id: "resp-tool", status: "completed" } });
  api.send({ type: "response.mcp_call.in_progress", item_id: "mcp-1" });
  api.send({ type: "response.mcp_call.completed", item_id: "mcp-1", output: "12" });
  api.answer("5 plus 7 equals 12.");
  await expect(page.locator(".msg.mcp_call")).toContainText("12");
  await expect(page.locator(".msg.assistant")).toContainText("5 plus 7 equals 12.");
  await expect(page.locator(".msg.assistant .bubble")).toHaveCSS("font-size", "16px");
  await expect(page.locator(".msg.mcp_call .mcp-info")).toHaveCSS("font-size", "15px");
  const tracePopup = context.waitForEvent("page");
  await page.getByRole("button", { name: "View trace" }).click();
  const trace = await tracePopup;
  await expect.poll(() => trace.url()).toContain("/foundry-trace?agent=realtime-agent");
  await trace.close();
  const persistedPopup = context.waitForEvent("page");
  await page.getByRole("button", { name: "View persisted" }).click();
  const persisted = await persistedPopup;
  await expect.poll(() => persisted.url()).toContain("conversation=conv-studio-test");
  await persisted.close();
  await page.getByRole("button", { name: "Clear chat" }).click();
  await expect(page.locator(".msg")).toHaveCount(0);
});

test("digit-accuracy demo still creates control and verified agents", async ({ page }) => {
  const api = await mountStudio(page);
  await selectTab(page, "Demos");
  await page.getByRole("button", { name: "Create A/B pair" }).click();
  await expect.poll(() => api.creates.length).toBe(2);
  expect(api.creates[0].definition.tools).toBeUndefined();
  expect(api.creates[1].definition.tools[0]).toMatchObject({ type: "function", name: "verify_spoken_digits" });
  await expect(page.getByLabel("Session agent", { exact: true })).toHaveValue(api.creates[1].name);
  await selectTab(page, "Agent");
  await selectTab(page, "Demos");
  await expect(page.locator(".demo-scenario")).toContainText(api.creates[0].name);
});

test("create errors preserve the draft and allow retry", async ({ page }) => {
  const api = await mountStudio(page);
  api.rejectCreate = true;
  await page.getByRole("textbox", { name: /^Agent name/ }).fill("retry-agent");
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Fixture validation failed");
  await expect(page.getByRole("textbox", { name: /^Agent name/ })).toHaveValue("retry-agent");
  api.rejectCreate = false;
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect(page.getByLabel("Session agent", { exact: true })).toHaveValue("retry-agent");
});

test("keyboard tabs move focus without erasing the draft", async ({ page }) => {
  await mountStudio(page);
  await page.getByRole("textbox", { name: /^Agent name/ }).fill("keyboard-draft");
  await page.getByRole("tab", { name: "Agent", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Voice", exact: true })).toBeFocused();
  await expect(page.getByRole("combobox", { name: "Voice", exact: true })).toBeVisible();
  await expect(page.getByLabel("First message")).not.toBeVisible();
  await page.keyboard.press("Home");
  await expect(page.getByRole("textbox", { name: /^Agent name/ })).toHaveValue("keyboard-draft");
});

test("connecting while Generate is pending keeps the active agent and ignores its late review", async ({ page }) => {
  const api = await mountStudio(page);
  let release;
  api.generateGate = new Promise((resolve) => { release = resolve; });
  await page.getByRole("button", { name: "Generate", exact: true }).click();
  await page.getByRole("button", { name: "Generate agent", exact: true }).click();
  await expect.poll(() => api.generates.length).toBe(1);
  await api.start();
  release();
  await expect(page.locator(".editor-footer")).toContainText("Generated.");
  await expect(page.getByLabel("Session agent", { exact: true })).toHaveValue("realtime-agent");
  await expect(page.locator(".review-definition")).toHaveCount(0);
});

test("connecting while Create is pending does not relabel the active session", async ({ page }) => {
  const api = await mountStudio(page);
  let release;
  api.createGate = new Promise((resolve) => { release = resolve; });
  await page.getByRole("textbox", { name: /^Agent name/ }).fill("late-agent");
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect.poll(() => api.creates.length).toBe(1);
  await api.start();
  release();
  await expect(page.getByLabel("Session agent", { exact: true }).locator("option[value=late-agent]")).toHaveCount(1);
  await expect(page.getByLabel("Session agent", { exact: true })).toHaveValue("realtime-agent");
});

test("session settings closes on Escape and restores keyboard focus", async ({ page }) => {
  await mountStudio(page);
  await page.getByText("Session settings", { exact: true }).click();
  await page.getByLabel("Transport", { exact: true }).focus();
  await page.keyboard.press("Escape");
  await expect(page.locator(".session-settings")).not.toHaveAttribute("open", "");
  await expect(page.locator(".session-settings > summary")).toBeFocused();
});

test("MCP approval still sends the native approval response", async ({ page }) => {
  const api = await mountStudio(page);
  await api.start();
  api.send({ type: "conversation.item.added", item: {
    id: "approval-1", type: "mcp_approval_request", server_label: "math", name: "add", arguments: '{"a":5,"b":7}',
  } });
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect.poll(() => api.messages.some((message) =>
    message.item?.type === "mcp_approval_response" && message.item.approval_request_id === "approval-1"
      && message.item.approve === true)).toBe(true);
});

test("the digit demo client handler executes and renders its comparison", async ({ page }) => {
  const api = await mountStudio(page);
  await api.start();
  api.send({ type: "input_audio_buffer.speech_started", item_id: "user-digits" });
  api.send({ type: "input_audio_buffer.speech_stopped", item_id: "user-digits" });
  api.send({ type: "conversation.item.input_audio_transcription.completed", item_id: "user-digits",
    transcript: "My phone number is 4255550198." });
  api.send({ type: "response.created", response: { id: "resp-function" } });
  api.send({ type: "response.function_call_arguments.done", item_id: "function-1", call_id: "call-1",
    name: "verify_spoken_digits", arguments: '{"field":"phone_number","heard":"4255550199"}' });
  api.send({ type: "response.done", response: { id: "resp-function", status: "completed" } });
  await expect.poll(() => api.messages.some((message) => message.item?.type === "function_call_output")).toBe(true);
  const output = api.messages.find((message) => message.item?.type === "function_call_output");
  expect(JSON.parse(output.item.output).authoritative_value).toBe("4255550198");
  await expect(page.locator(".msg.function_call")).toContainText("4255550198");
  await expect(page.locator(".fn-compare")).toContainText("4255550199");
  expect(api.messages.filter((message) => message.type === "response.create")).toHaveLength(1);
});

test("backend selection still reloads the requested project", async ({ page }) => {
  await mountStudio(page);
  await page.getByLabel("Agent backend", { exact: true }).selectOption("another-project");
  await expect(page).toHaveURL(/\/demo\/\?backend=another-project$/);
});

test("the standalone WebRTC page keeps its independent layout", async ({ page }) => {
  const api = await mountStudio(page);
  await page.goto("/static/demo/webrtc.html");
  await expect(page.locator(".wrtc-shell")).toBeVisible();
  await expect(page.locator(".studio")).toHaveCount(0);
  await expect(page.locator(".wrtc-field select option")).toHaveCount(4);
  expect(api.errors).toEqual([]);
});

test("desktop workspace extends beyond a short viewport to preserve transcription space", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const api = await mountStudio(page);
  const studio = await page.locator(".studio").boundingBox();
  const timeline = await page.locator(".timeline").boundingBox();
  expect(studio.height).toBe(1200);
  expect(timeline.height).toBeGreaterThanOrEqual(600);
  expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeGreaterThan(720);
  expect(api.errors).toEqual([]);
});

for (const viewport of [{ width: 1280, height: 720 }, { width: 768, height: 1024 }, { width: 390, height: 844 }]) {
  test(`responsive editor keeps controls reachable at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const api = await mountStudio(page);
    // Narrow viewports should reflow the layout, not shrink the text back down.
    await expect(page.locator(".studio")).toHaveCSS("font-size", "16px");
    await expect(page.getByRole("textbox", { name: /^Agent name/ })).toHaveCSS("font-size", "16px");
    await expect(page.locator("#editor-panel-agent .field-label").first()).toHaveCSS("font-size", "15px");
    await expect(page.locator("#editor-panel-agent .field-hint").first()).toHaveCSS("font-size", "14px");
    await expect(page.getByRole("tab", { name: "Agent", exact: true })).toHaveCSS("font-size", "15px");
    await expect(page.getByRole("button", { name: "Create agent", exact: true })).toHaveCSS("font-size", "15px");
    await expect(page.getByRole("button", { name: "Connect & start session" })).toHaveCSS("font-size", "15px");
    await expect(page.getByLabel("Message your agent")).toHaveCSS("font-size", "16px");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
    const emblem = await page.locator(".voice-emblem").boundingBox();
    expect(emblem.width).toBe(emblem.height);
    for (const name of ["Agent", "Voice", "Tools", "Workflow", "Demos"]) {
      await selectTab(page, name);
      await expect(page.getByRole("button", { name: "Create agent", exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
    }
    await page.getByRole("button", { name: "Generate", exact: true }).click();
    await expect(page.getByLabel("Goal")).toBeVisible();
    await expect(page.getByLabel("Session agent", { exact: true })).toBeVisible();
    expect(api.errors).toEqual([]);
  });
}
