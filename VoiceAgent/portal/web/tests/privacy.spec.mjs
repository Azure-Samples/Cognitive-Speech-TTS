// Copyright (c) Microsoft. All rights reserved.
// All service, socket, and WebRTC boundaries below are synthetic/local only.
import { test, expect } from "@playwright/test";
import { CONFIG, mountStudio, resource } from "./studio-fixtures.mjs";

async function generate(page, { store = false, draft = false } = {}) {
  const api = await mountStudio(page, { defaultStore: false });
  await page.getByRole("button", { name: "Generate", exact: true }).click();
  await page.getByLabel("Generated agent name").fill("generated-privacy-agent");
  await page.getByRole("checkbox", { name: /^Save generated conversations/ }).setChecked(store);
  if (draft) {
    await page.getByText("Generation options", { exact: true }).click();
    await page.getByRole("checkbox", { name: /^Create as a draft/ }).check();
  }
  await page.getByRole("button", { name: "Generate agent", exact: true }).click();
  await expect(page.getByLabel("Session agent", { exact: true })).toHaveValue("generated-privacy-agent");
  await expect.poll(() => api.generates.length).toBe(1);
  // Storage is a supported session override, not a new generation API field.
  expect(api.generates[0]).not.toHaveProperty("store");
  expect(api.generates[0].draft).toBe(draft);
  expect(api.versions).toEqual([]);
  return api;
}

test("generated storage defaults off even when the returned definition stores conversations", async ({ page }) => {
  const api = await generate(page);
  await page.locator(".session-settings > summary").click();
  await expect(page.getByRole("combobox", { name: "Conversation storage override", exact: true })).toHaveValue("false");
  await page.getByRole("button", { name: "Connect & start session" }).click();
  await expect.poll(() => api.sockets.length).toBe(1);
  expect(new URL(api.sockets[0].url()).searchParams.get("store")).toBe("false");
  await page.getByRole("button", { name: "Stop session" }).click();
});

test("generated storage opt-in and draft creation remain available without rewriting versions", async ({ page }) => {
  const api = await generate(page, { store: true, draft: true });
  await page.getByRole("button", { name: "Connect & start session" }).click();
  await expect.poll(() => api.sockets.length).toBe(1);
  expect(new URL(api.sockets[0].url()).searchParams.get("store")).toBe("true");
  expect(api.versions).toEqual([]);
  await page.getByRole("button", { name: "Stop session" }).click();
});

test("generated preference survives refresh and selection while existing-agent overrides remain editable", async ({ page }) => {
  await generate(page);
  await page.getByRole("button", { name: "Refresh agents", exact: true }).click();
  await expect(page.getByRole("button", { name: "Refresh agents", exact: true })).toBeEnabled();
  await page.getByLabel("Session agent", { exact: true }).selectOption("realtime-agent");
  await page.locator(".session-settings > summary").click();
  const storage = page.getByRole("combobox", { name: "Conversation storage override", exact: true });
  await expect(storage).toHaveValue("");
  await page.getByLabel("Session agent", { exact: true }).selectOption("generated-privacy-agent");
  if (await page.locator(".session-settings").getAttribute("open") === null) {
    await page.locator(".session-settings > summary").click();
  }
  await expect(storage).toHaveValue("false");
  await storage.selectOption("true");
  await expect(storage).toHaveValue("true");
  await storage.selectOption("");
  await expect(storage).toHaveValue("");
});

const agentName = "shared-privacy-agent";
const base = `/agents/${agentName}/endpoint/protocols/voice/conversations`;
const ownId = "synthetic-own-older";
const otherId = "synthetic-other-newer";

async function reviewFixture(page, { capturedId = null, failList = false } = {}) {
  const calls = [];
  const sockets = [];
  // A test-owned peer prevents STUN/TURN/media network traffic. The actual
  // production session hook, review components, HTML, and bundles still run.
  await page.addInitScript(() => {
    window.RTCPeerConnection = class extends EventTarget {
      iceGatheringState = "complete";
      connectionState = "new";
      signalingState = "stable";
      localDescription = null;
      addTrack() { return {}; }
      addTransceiver() { return {}; }
      getSenders() { return []; }
      createDataChannel() { return Object.assign(new EventTarget(), { readyState: "open", close() {} }); }
      async createOffer() { return { type: "offer", sdp: "synthetic-test-sdp" }; }
      async setLocalDescription(value) { this.localDescription = value; }
      async setRemoteDescription() {}
      async addIceCandidate() {}
      close() { this.connectionState = "closed"; }
    };
  });
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.hostname !== "127.0.0.1") return route.abort();
    const json = (data, status = 200) => route.fulfill({
      status, contentType: "application/json", body: JSON.stringify(data),
    });
    if (url.pathname === "/config") return json({ ...CONFIG, defaultStore: false });
    if (url.pathname === "/agents") return json({ data: [resource(agentName, {
      kind: "voice", model: "gpt-realtime", store: true,
      audio: { output: { voice: "en-US-AvaNeural", voice_type: "azure-standard" } },
    })], has_more: false });
    if (url.pathname.startsWith(base)) {
      calls.push(url.pathname);
      if (url.pathname === base) {
        if (failList) return json({ error: "Synthetic list unavailable" }, 503);
        return json({ data: [
          { id: ownId, created_at: "2026-09-15T00:00:00Z" },
          { id: otherId, created_at: "2026-09-16T00:00:00Z" },
        ], has_more: false });
      }
      const id = url.pathname.slice(base.length + 1).split("/")[0];
      if (url.pathname.endsWith("/items")) return json({ data: [
        { id: "user-item", type: "message", role: "user",
          content: [{ type: "input_text", text: `SYNTHETIC_TRANSCRIPT_${id}` }] },
        { id: "agent-item", type: "message", role: "assistant",
          content: [{ type: "output_text", text: "Synthetic response" }] },
      ], has_more: false });
      if (url.pathname.endsWith("/audio")) return json({
        duration_ms: 1000, format: "wav", channels: 2, channel_layout: { left: "user", right: "agent" },
      });
      if (url.pathname.endsWith("/audio/content")) return route.fulfill({
        contentType: "audio/wav", body: Buffer.from("RIFF-synthetic-review-audio"),
      });
      return json({ id, status: "completed" });
    }
    return route.continue();
  });
  await page.routeWebSocket("**/agents/**/endpoint/protocols/voice?*", (socket) => {
    sockets.push(socket);
    if (capturedId) socket.send(JSON.stringify({
      type: "session.created", conversation_id: capturedId, session: { id: "synthetic-session" },
    }));
  });
  return { calls, sockets };
}

test("persisted HTML requires an explicit ID selection and keeps audio downloads available", async ({ page }) => {
  const api = await reviewFixture(page);
  await page.goto(`/static/demo/persisted.html?agent=${agentName}`);
  await expect(page.locator("#conversationChoiceStatus")).toContainText("Choose a recent ID");
  expect(api.calls).toEqual([base]);
  await expect(page.locator("#turns")).toBeEmpty();
  await expect(page.getByRole("button", { name: /Merged recording/ })).toBeDisabled();
  await page.getByRole("combobox", { name: "Conversation ID", exact: true }).fill(ownId);
  await page.getByRole("button", { name: "Open conversation", exact: true }).click();
  await expect(page.locator("#turns")).toContainText(`SYNTHETIC_TRANSCRIPT_${ownId}`);
  expect(api.calls).not.toContain(`${base}/${otherId}/items`);
  await page.getByRole("button", { name: /Merged recording/ }).click();
  await expect(page.getByRole("link", { name: /Download WAV/ })).toHaveAttribute("href", `${base}/${ownId}/audio/content?api-version=v1`);
  await page.getByRole("button", { name: "Choose conversation", exact: true }).click();
  await expect(page.locator("#turns")).toBeEmpty();
  await expect(page.locator("#recording")).toBeHidden();
});

test("persisted HTML opens a captured ID directly without listing other sessions", async ({ page }) => {
  const api = await reviewFixture(page);
  await page.goto(`/static/demo/persisted.html?agent=${agentName}&conversation=${ownId}`);
  await expect(page.locator("#turns")).toContainText(`SYNTHETIC_TRANSCRIPT_${ownId}`);
  expect(api.calls).toEqual([`${base}/${ownId}/items`]);
  await expect(page.getByRole("region", { name: "Choose a saved conversation" })).toBeHidden();
});

test("known historical IDs can still be opened when listing is unavailable", async ({ page }) => {
  await reviewFixture(page, { failList: true });
  await page.goto(`/static/demo/persisted.html?agent=${agentName}`);
  await expect(page.locator("#conversationChoiceStatus")).toContainText("still paste a known ID");
  await page.getByRole("combobox", { name: "Conversation ID", exact: true }).fill(ownId);
  await page.getByRole("button", { name: "Open conversation", exact: true }).click();
  await expect(page.locator("#turns")).toContainText(`SYNTHETIC_TRANSCRIPT_${ownId}`);
});

async function endWebRtc(page, api, capturedId = null) {
  await page.goto("/static/demo/webrtc.html");
  await page.getByRole("combobox", { name: "Agent", exact: true }).selectOption(agentName);
  await page.getByRole("button", { name: "Start WebRTC session" }).click();
  await expect.poll(() => api.sockets.length).toBe(1);
  if (capturedId) await expect(page.locator(".wrtc-stage")).toContainText(capturedId);
  await page.getByRole("button", { name: "End & review" }).click();
}

test("WebRTC review requires selection when no live conversation ID was captured", async ({ page }) => {
  const api = await reviewFixture(page);
  await endWebRtc(page, api);
  const picker = page.getByRole("region", { name: "Choose a saved conversation" });
  await expect(picker).toBeVisible();
  await expect(picker.getByRole("status")).toContainText("Choose a recent ID");
  expect(api.calls).toEqual([base]);
  await picker.getByRole("combobox", { name: "Conversation ID", exact: true }).fill(ownId);
  await picker.getByRole("button", { name: "Open conversation", exact: true }).click();
  await expect(page.locator(".mp-conv")).toHaveText(ownId);
  await page.getByRole("button", { name: "User view", exact: true }).click();
  await expect(page.locator(".mp")).toContainText(`SYNTHETIC_TRANSCRIPT_${ownId}`);
  expect(api.calls).not.toContain(`${base}/${otherId}/items`);
  await page.getByRole("button", { name: "Choose conversation", exact: true }).click();
  await expect(picker).toBeVisible();
  await expect(page.locator(".mp")).toHaveCount(0);
  await page.getByRole("button", { name: "New session", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Start a voice session" })).toBeVisible();
});

test("WebRTC captured conversation and recording controls still work directly", async ({ page }) => {
  const api = await reviewFixture(page, { capturedId: ownId });
  await endWebRtc(page, api, ownId);
  await expect(page.locator(".mp-conv")).toHaveText(ownId);
  expect(api.calls).not.toContain(base);
  await page.getByRole("button", { name: "Load recording", exact: true }).click();
  await expect(page.locator(".wrtc-recording audio")).toHaveAttribute("src", `${base}/${ownId}/audio/content?api-version=v1`);
});
