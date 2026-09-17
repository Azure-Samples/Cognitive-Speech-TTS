// Copyright (c) Microsoft. All rights reserved.
import { expect } from "@playwright/test";

export const CONFIG = {
  backend: "sample-project",
  backends: ["sample-project", "another-project"],
  project: "sample-account@sample-project",
  host: "https://example.invalid/api/projects/test",
  apiVersion: "v1",
  foundryFeatures: "VoiceAgents=V1Preview",
  defaultModel: "gpt-realtime",
  defaultVoice: "en-US-AvaNeural",
  defaultAzureVoice: "en-US-AvaNeural",
  defaultInferenceMode: "model",
  inputTranscriptionModel: "azure-speech",
  models: ["gpt-realtime", "gpt-4.1"],
  realtimeModels: ["gpt-realtime"],
  cascadedModels: ["gpt-4.1"],
  byomRealtimeModels: ["my-realtime"],
  byomCascadedModels: ["my-cascaded"],
  azureVoices: ["en-US-AvaNeural", "en-US-AndrewNeural", "en-US-JennyNeural"],
  openaiVoices: ["alloy", "marin"],
  inferenceModes: [{ value: "model" }, { value: "deployment" }, { value: "hosted_agent" }],
  defaultToolbox: { name: "search-tools", version: "2" },
  mcpAuthPresets: [
    { value: "apikey", label: "API key", mode: "connection", server_label: "apikey", project_connection_id: "/connections/apikey" },
    { value: "entra", label: "Microsoft Entra", mode: "connection", server_label: "entra", project_connection_id: "/connections/entra" },
    { value: "noauth", label: "No authentication", mode: "url", server_label: "public", server_url: "https://mcp.example/noauth/mcp" },
    { value: "knowledge", label: "Foundry IQ", mode: "foundry_iq", server_label: "knowledge",
      server_url: "https://search.example/knowledgebases/test/mcp", project_connection_id: "/connections/knowledge" },
  ],
};

export function resource(name, definition, extra = {}) {
  return {
    name,
    versions: { latest: { version: "1", created_at: 1, definition, description: "Test fixture", metadata: {}, ...extra } },
  };
}

const voiceDefinition = (model, voice, clientReferenceEc = false) => ({
  kind: "voice",
  model_type: "managed",
  model,
  instructions: "Answer concisely.",
  store: true,
  audio: {
    input: {
      format: { type: "audio/pcm", rate: 24000 },
      ...(clientReferenceEc ? { echo_cancellation: { type: "server_echo_cancellation", reference_source: "client", channels: 2 } } : {}),
    },
    output: { voice },
  },
});

export async function mountStudio(page, configPatch = {}, path = "/demo/") {
  const api = {
    creates: [], generates: [], versions: [], sockets: [], messages: [], errors: [],
    rejectCreate: false, createGate: null, generateGate: null, autoReply: false,
  };
  const entries = [
    resource("realtime-agent", voiceDefinition("gpt-realtime", { type: "azure-standard", name: "en-US-AvaNeural" })),
    resource("echo-agent", voiceDefinition("gpt-realtime", { type: "azure-standard", name: "en-US-AvaNeural" }, true)),
    resource("cascaded-agent", voiceDefinition("gpt-4.1", "en-US-AndrewNeural")),
    resource("billing-specialist", { kind: "prompt", model: "gpt-4.1", instructions: "Handle billing." }, { description: "Resolves billing" }),
    resource("hosted-target", { kind: "hosted", protocol_versions: [{ protocol: "invocations_ws", version: "1.0.0" }] },
      { metadata: { voiceLiveCompatible: "true", bridgeProtocolVersion: "1.0" }, status: "active" }),
  ];
  const agents = new Map(entries.map((item) => [item.name, item]));
  page.on("pageerror", (error) => api.errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") api.errors.push(message.text()); });

  // Abort outside requests: a browser regression must never accidentally talk to Azure.
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.hostname !== "127.0.0.1") return route.abort();
    const json = (body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (url.pathname === "/config") return json({ ...CONFIG, ...configPatch });
    if (url.pathname === "/deployments") return json({
      realtime: [{ deployment: "my-realtime", model: "gpt-realtime" }],
      cascaded: [{ deployment: "my-cascaded", model: "gpt-4.1" }],
    });
    if (url.pathname === "/agents:generate") {
      const body = request.postDataJSON();
      api.generates.push(body);
      if (api.generateGate) await api.generateGate;
      const item = resource(body.name, {
        ...voiceDefinition(body.model || "gpt-realtime", { type: "azure-standard", name: "en-US-AvaNeural" }),
        instructions: "Generated instructions for the requested goal.",
        tools: body.tools || [],
      });
      agents.set(item.name, item);
      return json(item);
    }
    const createRoute = url.pathname.match(/^\/agents\/([^/]+)\/versions$/);
    if (createRoute && request.method() === "POST" && !agents.has(decodeURIComponent(createRoute[1]))) {
      const name = decodeURIComponent(createRoute[1]);
      const body = request.postDataJSON();
      // Keep the fixture's authoring summary, but enforce the public wire shape.
      expect(body).not.toHaveProperty("name");
      api.creates.push({ name, ...body });
      if (api.createGate) await api.createGate;
      if (api.rejectCreate) return json({ message: "Fixture validation failed" }, 400);
      const item = resource(name, body.definition, { description: body.description || "" });
      agents.set(item.name, item);
      return json(item.versions.latest);
    }
    if (url.pathname === "/agents") {
      const data = [...agents.values()].filter((item) => !url.searchParams.has("kind") || item.versions.latest.definition.kind === "voice");
      return json({ data, has_more: false });
    }
    const agentRoute = url.pathname.match(/^\/agents\/([^/]+)(?:\/versions(?:\/([^/]+))?)?$/);
    if (agentRoute) {
      const name = decodeURIComponent(agentRoute[1]);
      const item = agents.get(name);
      if (!item) return json({ message: "Not found" }, 404);
      if (request.method() === "POST") {
        const body = request.postDataJSON();
        api.versions.push(body);
        item.versions.latest = { ...item.versions.latest, ...body, version: "2" };
        return json({ version: "2" });
      }
      return json(agentRoute[2] ? item.versions.latest : item);
    }
    if (url.pathname === "/foundry-trace" || url.pathname.endsWith("persisted.html")) {
      return route.fulfill({ contentType: "text/html", body: "<title>Fixture detail page</title>" });
    }
    return route.continue();
  });
  await page.routeWebSocket("**/agents/**/endpoint/protocols/voice?*", (socket) => {
    api.sockets.push(socket);
    socket.onMessage((raw) => {
      const message = JSON.parse(String(raw));
      // Avoid filling the trace with fake microphone PCM.
      if (message.type !== "input_audio_buffer.append") api.messages.push(message);
      if (api.autoReply && message.type === "response.create") api.answer("Fixture response");
    });
  });
  api.send = (event) => api.sockets.at(-1).send(JSON.stringify(event));
  api.answer = (text) => {
    api.send({ type: "response.created", response: { id: "resp-answer" } });
    api.send({ type: "response.output_text.delta", response_id: "resp-answer", delta: text });
    api.send({ type: "response.output_text.done", response_id: "resp-answer", text });
    api.send({ type: "response.done", response: { id: "resp-answer", status: "completed", output: [
      { type: "message", content: [{ type: "output_text", text }] },
    ] } });
  };
  api.start = async (name = "realtime-agent") => {
    await page.getByLabel("Session agent", { exact: true }).selectOption(name);
    await page.getByRole("button", { name: "Connect & start session" }).click();
    await expect.poll(() => api.sockets.length).toBeGreaterThan(0);
    await expect(page.getByRole("button", { name: "Stop session" })).toBeVisible();
    api.send({ type: "session.created", conversation_id: "conv-studio-test", session: { id: "sess-studio-test" } });
    api.send({ type: "session.updated", session: {
      id: "sess-studio-test", ...agents.get(name).versions.latest.definition,
    } });
    await expect(page.getByRole("button", { name: "Mute mic" })).toBeEnabled();
  };
  await page.goto(path);
  await expect(page.getByRole("heading", { name: "Agent Creation" })).toBeVisible();
  return api;
}

export async function selectTab(page, name) {
  await page.getByRole("complementary", { name: "Agent editor" })
    .getByRole("tab", { name: new RegExp(`^${name}(?:\\d+)?$`) }).click();
}
