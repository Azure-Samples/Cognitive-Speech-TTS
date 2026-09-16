// Copyright (c) Microsoft. All rights reserved.
// Pure avatar helpers shared by the portal UI and node tests. The persisted shape matches the
// Agents voice definition; the runtime helpers match the raw Voice Live WebSocket wire.

export const AVATAR_PRESETS = [
  { id: "lisa-casual-sitting", label: "Lisa — casual sitting", character: "lisa", style: "casual-sitting" },
  { id: "harry-business", label: "Harry — business", character: "harry", style: "business" },
  { id: "harry-casual", label: "Harry — casual", character: "harry", style: "casual" },
  { id: "jeff-business", label: "Jeff — business", character: "jeff", style: "business" },
  { id: "jeff-formal", label: "Jeff — formal", character: "jeff", style: "formal" },
  { id: "lori-casual", label: "Lori — casual", character: "lori", style: "casual" },
  { id: "lori-formal", label: "Lori — formal", character: "lori", style: "formal" },
  { id: "max-business", label: "Max — business", character: "max", style: "business" },
  { id: "max-casual", label: "Max — casual", character: "max", style: "casual" },
  { id: "meg-business", label: "Meg — business", character: "meg", style: "business" },
  { id: "meg-casual", label: "Meg — casual", character: "meg", style: "casual" },
];

export const DEFAULT_AVATAR_PRESET_ID = "lisa-casual-sitting";

export function buildAvatarDefinition(enabled, presetId = DEFAULT_AVATAR_PRESET_ID) {
  if (!enabled) return null;
  const preset = AVATAR_PRESETS.find((item) => item.id === presetId)
    || AVATAR_PRESETS.find((item) => item.id === DEFAULT_AVATAR_PRESET_ID);
  if (!preset) return null;
  return {
    type: "video-avatar",
    character: preset.character,
    style: preset.style,
    customized: false,
    output_protocol: "webrtc",
  };
}

export function isWebRtcAvatar(avatar) {
  if (!avatar) return false;
  const protocol = avatar.output_protocol || avatar.outputProtocol || "webrtc";
  return protocol === "webrtc";
}

export function toRtcIceServers(avatar) {
  const servers = avatar?.ice_servers || avatar?.iceServers || [];
  if (!Array.isArray(servers)) return [];
  return servers
    .filter((server) => server && server.urls)
    .map((server) => {
      const originalUrls = Array.isArray(server.urls) ? server.urls : [server.urls];
      const urls = [...originalUrls];
      // Some corporate/headless environments block TURN/UDP 3478. The Voice Live aiortc sample
      // uses the same relay credentials over TURN/TCP 443, so include that path as a fallback while
      // preserving every URL returned by Voice Live.
      for (const url of originalUrls) {
        if (typeof url !== "string" || !url.startsWith("turn:") || url.includes("transport=tcp")) continue;
        const base = url.split("?")[0];
        const tcp = `${base.replace(/:3478$/, ":443")}?transport=tcp`;
        if (tcp !== url && !urls.includes(tcp)) urls.push(tcp);
      }
      return {
        urls,
        ...(server.username ? { username: server.username } : {}),
        ...(server.credential ? { credential: server.credential } : {}),
      };
    });
}
