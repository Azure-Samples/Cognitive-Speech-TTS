// Copyright (c) Microsoft. All rights reserved.

function errorMessage(data, fallback) {
  const error = data && data.error;
  if (typeof error === "string") return error;
  if (error && typeof error.message === "string") return error.message;
  if (data && typeof data.message === "string") return data.message;
  return fallback;
}

export function asVoiceAgent(resource) {
  const latest = resource?.versions?.latest;
  const definition = latest?.definition;
  if (!resource?.name || definition?.kind !== "voice") return null;

  // Vienna normalizes current definitions to a flat voice string, while older
  // deployed versions return { type, name }. Both must remain selectable.
  const outputVoice = definition.audio?.output?.voice;
  const voice = typeof outputVoice === "string" ? outputVoice : outputVoice?.name || "";
  const echoCancellation = definition.audio?.input?.echo_cancellation;
  const store = typeof definition.store === "boolean"
    ? definition.store
    : definition.audio_logging === "enabled";

  return {
    name: resource.name,
    model: definition.model || "",
    voice,
    avatar: definition.avatar ? { ...definition.avatar } : null,
    greeting: definition.greeting ? { ...definition.greeting } : null,
    inferenceMode: definition.model_type === "hosted_agent"
      ? "hosted_agent"
      : definition.model_type === "self_deployed"
        ? "deployment"
        : "model",
    targetAgent: definition.target_agent ? { ...definition.target_agent } : null,
    clientReferenceEc: echoCancellation?.reference_source === "client"
      && echoCancellation?.channels === 2,
    store,
    toolCount: Array.isArray(definition.tools) ? definition.tools.length : 0,
    handoff: definition.handoff ? structuredClone(definition.handoff) : null,
    definition: structuredClone(definition),
    description: latest.description || "",
    metadata: latest.metadata ? { ...latest.metadata } : {},
    version: String(latest.version || ""),
    createdAt: Number(latest.created_at) || 0,
  };
}

export async function loadVoiceAgent(cfg, name, fetchImpl = fetch) {
  const path = `/agents/${encodeURIComponent(name)}?api-version=${encodeURIComponent(cfg.apiVersion)}`;
  const response = await fetchImpl(path, {
    headers: { "Foundry-Features": cfg.foundryFeatures },
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(errorMessage(data, `GET ${path} failed with HTTP ${response.status}`));
  }
  return data;
}

export function hostedAgentTargetPath(cfg, name, version) {
  const encodedName = encodeURIComponent(String(name || "").trim());
  const encodedVersion = encodeURIComponent(String(version || "").trim());
  const suffix = encodedVersion ? `/versions/${encodedVersion}` : "";
  return `/agents/${encodedName}${suffix}?api-version=${encodeURIComponent(cfg.apiVersion)}`;
}

function bridgeTargetVersion(resource) {
  return resource?.versions?.latest || resource;
}

export function assertBridgeCompatibleHostedAgent(resource, name, version) {
  const targetName = String(name || "").trim();
  const targetVersion = String(version || "").trim();
  const label = targetVersion ? `${targetName}:${targetVersion}` : targetName;
  const selected = bridgeTargetVersion(resource);
  const definition = selected?.definition || {};
  const metadata = selected?.metadata || {};

  if (definition.kind !== "hosted") {
    throw new Error(
      `Target agent '${label}' is kind '${definition.kind || "unknown"}'; `
      + "expected a hosted agent that supports Voice Live Bridge Protocol 1.0.",
    );
  }
  if (selected.status && selected.status !== "active") {
    throw new Error(
      `Target hosted agent '${label}' is '${selected.status}', not active.`,
    );
  }

  const protocols = [
    ...(definition.protocol_versions || []),
    ...(definition.container_protocol_versions || []),
  ];
  const supportsInvocationsWs = protocols.some(
    (item) => item?.protocol === "invocations_ws" && item?.version === "1.0.0",
  );
  const voiceLiveCompatible = String(metadata.voiceLiveCompatible).toLowerCase() === "true";
  const bridgeProtocolVersion = String(metadata.bridgeProtocolVersion || "");
  const missing = [];
  if (!supportsInvocationsWs) missing.push("invocations_ws 1.0.0");
  if (!voiceLiveCompatible) missing.push("voiceLiveCompatible=true");
  if (bridgeProtocolVersion !== "1.0") missing.push("bridgeProtocolVersion=1.0");
  if (missing.length) {
    throw new Error(
      `Target hosted agent '${label}' does not support Voice Live Bridge Protocol 1.0; `
      + `missing ${missing.join(", ")}.`,
    );
  }
  return selected;
}

export async function validateHostedAgentTarget(
  cfg,
  name,
  version,
  fetchImpl = fetch,
) {
  const targetName = String(name || "").trim();
  const targetVersion = String(version || "").trim();
  if (!targetName) throw new Error("Target hosted agent name is required");
  const label = targetVersion ? `${targetName}:${targetVersion}` : targetName;
  const path = hostedAgentTargetPath(cfg, targetName, targetVersion);
  const response = await fetchImpl(path, {
    headers: { "Foundry-Features": cfg.foundryFeatures },
  });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(
        `Target hosted agent '${label}' was not found in the selected Foundry project.`,
      );
    }
    throw new Error(errorMessage(data, `GET ${path} failed with HTTP ${response.status}`));
  }
  return assertBridgeCompatibleHostedAgent(data, targetName, targetVersion);
}

export async function loadVoiceAgents(cfg, fetchImpl = fetch) {
  const agents = new Map();
  const seenCursors = new Set();
  let after = "";

  while (true) {
    const query = new URLSearchParams({
      "api-version": cfg.apiVersion,
      kind: "voice",
      limit: "100",
    });
    if (after) query.set("after", after);

    const path = `/agents?${query.toString()}`;
    const response = await fetchImpl(path, {
      headers: { "Foundry-Features": cfg.foundryFeatures },
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(errorMessage(data, `GET ${path} failed with HTTP ${response.status}`));
    }

    for (const resource of data.data || []) {
      const agent = asVoiceAgent(resource);
      if (agent) agents.set(agent.name, agent);
    }

    if (!data.has_more) break;
    const next = data.last_id;
    if (!next || seenCursors.has(next)) {
      throw new Error("List agents returned has_more without a usable pagination cursor");
    }
    seenCursors.add(next);
    after = next;
  }

  return [...agents.values()].sort(
    (left, right) => right.createdAt - left.createdAt || left.name.localeCompare(right.name),
  );
}
