// Copyright (c) Microsoft. All rights reserved.

import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_AVATAR_PRESET_ID,
  buildAvatarDefinition,
  isWebRtcAvatar,
  toRtcIceServers,
} from "./avatar.mjs";

test("builds the persisted Agents video-avatar contract", () => {
  assert.deepEqual(buildAvatarDefinition(true, DEFAULT_AVATAR_PRESET_ID), {
    type: "video-avatar",
    character: "lisa",
    style: "casual-sitting",
    customized: false,
    output_protocol: "webrtc",
  });
  assert.equal(buildAvatarDefinition(false), null);
});

test("falls back to the default avatar for an unknown preset", () => {
  assert.deepEqual(
    buildAvatarDefinition(true, "unknown"),
    buildAvatarDefinition(true, DEFAULT_AVATAR_PRESET_ID),
  );
});

test("recognizes raw and SDK-shaped WebRTC avatar fields", () => {
  assert.equal(isWebRtcAvatar({ character: "lisa" }), true);
  assert.equal(isWebRtcAvatar({ output_protocol: "webrtc" }), true);
  assert.equal(isWebRtcAvatar({ outputProtocol: "websocket" }), false);
  assert.equal(isWebRtcAvatar(null), false);
});

test("normalizes Voice Live ICE servers without exposing unrelated avatar fields", () => {
  assert.deepEqual(toRtcIceServers({
    ice_servers: [
      {
        urls: ["turn:relay.example:3478"],
        username: "user",
        credential: "secret",
        ignored: "value",
      },
      { urls: "stun:stun.example:3478" },
      { username: "missing-urls" },
    ],
  }), [
    {
      urls: [
        "turn:relay.example:3478",
        "turn:relay.example:443?transport=tcp",
      ],
      username: "user",
      credential: "secret",
    },
    { urls: ["stun:stun.example:3478"] },
  ]);
});
