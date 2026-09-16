// Copyright (c) Microsoft. All rights reserved.
// Config loading + model/voice helpers (mirrors the demo's /config contract).

export async function loadConfig() {
  const resp = await fetch("/config");
  if (!resp.ok) throw new Error(`/config HTTP ${resp.status}`);
  return resp.json();
}

// Dynamically discover the BYOM Foundry account's usable deployments (realtime + cascaded), so BYOM
// mode isn't limited to hardcoded names. The backend returns `{realtime:[{deployment,model}], cascaded,
// account, source}` and already degrades to the static fallback list on any ARM/auth error, so this
// never throws for the caller's purposes — but guard anyway and let callers keep the /config fallback.
export async function loadDeployments() {
  const resp = await fetch("/deployments");
  if (!resp.ok) throw new Error(`/deployments HTTP ${resp.status}`);
  return resp.json();
}

// Cascaded models (e.g. gpt-4.1) use Azure Neural TTS and ONLY accept Azure voices. Covers both the
// managed model names and the BYOM cascaded deployment names.
export function isCascaded(cfg, model) {
  return (cfg?.cascadedModels || []).includes(model) || (cfg?.byomCascadedModels || []).includes(model);
}

// Build grouped options for a <select> of models: Realtime vs Cascaded. When `byom` is true, offer the
// BYOM DEPLOYMENT names (self_deployed) rather than the managed model names — Voice Live connects to
// the deployment directly, so it must be a real, reachable deployment (not a managed model name).
export function modelGroups(cfg, byom) {
  const realtime = byom ? (cfg?.byomRealtimeModels || []) : (cfg?.realtimeModels || []);
  const cascaded = byom ? (cfg?.byomCascadedModels || []) : (cfg?.cascadedModels || []);
  const groups = [
    { label: byom ? "Realtime — BYOM deployment" : "Realtime (native speech-to-speech)", items: realtime },
    { label: byom ? "Cascaded — BYOM deployment" : "Cascaded (text model + STT/TTS)", items: cascaded },
  ];
  if (!byom) {
    const known = new Set([...realtime, ...cascaded]);
    const other = (cfg.models || []).filter((m) => !known.has(m));
    if (other.length) groups.push({ label: "Other", items: other });
  }
  return groups.filter((g) => g.items.length);
}

// Build grouped voice options. When azureOnly is true (cascaded models), only Azure voices.
export function voiceGroups(cfg, azureOnly) {
  const groups = [{ label: "Azure", items: cfg.azureVoices || [] }];
  if (!azureOnly) groups.unshift({ label: "OpenAI", items: cfg.openaiVoices || [] });
  return groups.filter((g) => g.items.length);
}

// Default voice to preselect for a given model family. DragonHD is the recommended default for
// BOTH realtime and cascaded; it is an Azure voice and is valid in every mode.
export function defaultVoiceFor(cfg, model) {
  if (cfg?.defaultAzureVoice) return cfg.defaultAzureVoice;
  if (cfg?.defaultVoice) return cfg.defaultVoice;
  if (isCascaded(cfg, model)) return (cfg.azureVoices || [])[0] || "en-US-Ava:DragonHDLatestNeural";
  return (cfg.openaiVoices || [])[0] || "alloy";
}
