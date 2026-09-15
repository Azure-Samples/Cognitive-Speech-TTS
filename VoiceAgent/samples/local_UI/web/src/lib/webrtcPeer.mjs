// Copyright (c) Microsoft. All rights reserved.
// WebRTC media transport helpers for the voice demo. The browser peers directly with Voice Live —
// mic + agent audio (Opus/SRTP) and the voice-live-events data channel are peer-to-peer; the Agents
// service is only a signaling relay for the rtc.call.sdp.* frames over the bridged WebSocket.
// (features/webrtc_voice_first_agent_demo/design.md §4.) Mirrors avatar.mjs in spirit, for the media path.

// Voice Live's WebRTC media data-channel label. It must be created BEFORE createOffer so the
// m=application line is negotiated into the offer.
export const WEBRTC_DATA_CHANNEL = "voice-live-events";

// The media leg is not given service-supplied ICE servers (unlike the avatar path), so the browser
// configures a public STUN server; MediaEdge returns its own candidates inside the SDP answer.
export function defaultIceServers() {
  return [{ urls: "stun:stun.l.google.com:19302" }];
}

// Some corporate/headless networks block TURN/UDP 3478. When a caller supplies TURN servers WITH
// credentials, add a TURN/TCP:443 variant as a fallback (same rewrite as the avatar path), preserving
// every original URL + credential. A public STUN has no relay credentials, so nothing is added for it.
export function withTurnTcpFallback(iceServers) {
  if (!Array.isArray(iceServers)) return [];
  return iceServers
    .filter((server) => server && server.urls)
    .map((server) => {
      const originalUrls = Array.isArray(server.urls) ? server.urls : [server.urls];
      const urls = [...originalUrls];
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

// Per design §4.4: rtc.call.error codes that KILL the call (a fresh connect is required) vs codes the
// control WS can recover from. Terminal ones tear down the media peer; the rest are surfaced as warnings.
const TERMINAL_RTC_ERROR_CODES = new Set(["missing_sdp", "session_timeout", "message_too_large"]);
export function isTerminalRtcError(code) {
  return TERMINAL_RTC_ERROR_CODES.has(String(code || ""));
}

// Resolve after ICE gathering completes (non-trickle): the whole offer, candidates included, is sent
// in one rtc.call.sdp.create frame. Shared by the avatar and media peers.
export function waitForIceGatheringComplete(peer, timeoutMs = 3000) {
  if (peer.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const timeout = setTimeout(done, timeoutMs);
    function done() {
      clearTimeout(timeout);
      peer.removeEventListener("icegatheringstatechange", onStateChange);
      resolve();
    }
    function onStateChange() {
      if (peer.iceGatheringState === "complete") done();
    }
    peer.addEventListener("icegatheringstatechange", onStateChange);
  });
}
