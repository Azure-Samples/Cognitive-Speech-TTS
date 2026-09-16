// Copyright (c) Microsoft. All rights reserved.

import test from "node:test";
import assert from "node:assert/strict";
import {
  WEBRTC_DATA_CHANNEL,
  defaultIceServers,
  isTerminalRtcError,
  withTurnTcpFallback,
} from "./webrtcPeer.mjs";

test("data channel label matches the Voice Live media contract", () => {
  assert.equal(WEBRTC_DATA_CHANNEL, "voice-live-events");
});

test("default ICE servers provide a public STUN", () => {
  const servers = defaultIceServers();
  assert.ok(Array.isArray(servers) && servers.length >= 1);
  assert.ok(servers.some((s) => String(s.urls).includes("stun:")));
});

test("adds a TURN/TCP:443 fallback for turn:3478 URLs, preserving credentials", () => {
  const out = withTurnTcpFallback([
    { urls: "turn:relay.example.com:3478", username: "u", credential: "c" },
  ]);
  assert.equal(out.length, 1);
  assert.deepEqual(out[0].urls, [
    "turn:relay.example.com:3478",
    "turn:relay.example.com:443?transport=tcp",
  ]);
  assert.equal(out[0].username, "u");
  assert.equal(out[0].credential, "c");
});

test("leaves stun-only and already-tcp turn urls unchanged", () => {
  const stun = withTurnTcpFallback([{ urls: ["stun:stun.example.com:3478"] }]);
  assert.deepEqual(stun[0].urls, ["stun:stun.example.com:3478"]);
  const tcp = withTurnTcpFallback([{ urls: ["turn:relay.example.com:443?transport=tcp"] }]);
  assert.deepEqual(tcp[0].urls, ["turn:relay.example.com:443?transport=tcp"]);
});

test("ignores non-array input and servers without urls", () => {
  assert.deepEqual(withTurnTcpFallback(null), []);
  assert.deepEqual(withTurnTcpFallback([{ username: "x" }]), []);
});

test("classifies terminal vs recoverable rtc.call.error codes (design §4.4)", () => {
  for (const code of ["missing_sdp", "session_timeout", "message_too_large"]) {
    assert.equal(isTerminalRtcError(code), true, code);
  }
  for (const code of ["session_not_ready", "session_already_exists", "invalid_message", "missing_type", "", undefined, null]) {
    assert.equal(isTerminalRtcError(code), false, String(code));
  }
});
