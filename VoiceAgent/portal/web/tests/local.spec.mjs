// Copyright (c) Microsoft. All rights reserved.
// Browser -> production Foundry-only portal -> test-only Azure service fixture.
import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  // Exercise normal microphone startup with Playwright's synthetic device.
  await page.addInitScript(() => {
    window.microphoneCalls = 0;
    const getUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async (...args) => {
      window.microphoneCalls += 1;
      return getUserMedia(...args);
    };
  });
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    return url.hostname === "127.0.0.1" ? route.continue() : route.abort();
  });
});

test("Foundry-only portal creates, edits, connects and reads persisted data through the proxy", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Voice agent studio" })).toBeVisible();
  await expect(page.locator(".portal-notice")).toContainText("Azure Foundry project");
  const config = await (await page.request.get("/config")).json();
  expect(config.host).toBe("https://sample.services.ai.azure.com/api/projects/sample-project");
  expect(config).not.toHaveProperty("mode");
  await expect(page.getByRole("checkbox", { name: /^Save conversations/ })).not.toBeChecked();
  await page.getByRole("textbox", { name: /^Agent name/ }).fill("local-browser-agent");
  await page.getByRole("checkbox", { name: /^Save conversations/ }).check();
  await page.getByRole("button", { name: "Create agent", exact: true }).click();
  await expect(page.getByLabel("Session agent", { exact: true })).toHaveValue("local-browser-agent");
  await page.getByRole("button", { name: "Edit definition" }).click();
  const editor = page.getByLabel("Agent definition YAML");
  await expect(editor).toHaveValue(/Respond naturally and concisely\./);
  const yaml = await editor.inputValue();
  await editor.fill(yaml.replace("Respond naturally and concisely.", "Browser-tested local instructions."));
  await page.getByRole("button", { name: "Save as new version" }).click();
  await expect(page.locator(".definition-save-state")).toContainText("Version 2 created");
  await page.getByRole("button", { name: "Close definition editor" }).click();
  await expect(page.locator(".selected-agent-meta")).toContainText("v2");
  await expect(page.getByRole("button", { name: "View trace" })).toBeDisabled();
  await page.getByRole("button", { name: "Connect & start session" }).click();
  await expect(page.locator(".connection-status")).toContainText("ready - listening");
  await page.getByRole("textbox", { name: "Message your agent" }).fill("Hello from the real local browser");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("Fixture response from the simulated Foundry service.", { exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.microphoneCalls)).toBeGreaterThan(0);
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "View persisted" }).click();
  const popup = await popupPromise;
  await expect(popup.getByRole("heading", { name: "Persisted conversation" })).toBeVisible();
  await expect(popup.getByText("Fixture response from the simulated Foundry service.", { exact: true })).toBeVisible();
  await popup.close();
  await page.screenshot({ path: "../.run/portal-local.png", fullPage: true });
  await page.getByRole("button", { name: "Stop session" }).click();
  await expect(page.getByRole("button", { name: "Connect & start session" })).toBeEnabled();
  expect(errors).toEqual([]);
});

test("guided authoring uses the configured Foundry service response", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Generate", exact: true }).click();
  await page.getByRole("textbox", { name: /^Generated agent name/ }).fill("local-template-agent");
  await page.getByRole("textbox", { name: /^Goal/ }).fill("Answer questions about this sample.");
  await page.getByRole("button", { name: "Generate agent", exact: true }).click();
  await expect(page.locator(".review-definition")).toContainText("Generated definition from the test fixture.");
});

test("WebRTC uses the Foundry project directly and session logs remain opt-in", async ({ page }) => {
  await page.goto("/webrtc");
  await expect(page.getByRole("heading", { name: "Start a voice session" })).toBeVisible();
  await page.getByRole("combobox", { name: "Agent", exact: true }).selectOption("fixture-agent");
  await expect(page.getByRole("button", { name: "Start WebRTC session" })).toBeEnabled();
  expect(await page.evaluate(() => window.microphoneCalls)).toBe(0);
  await page.getByRole("link", { name: "Return to studio" }).click();
  await page.getByRole("link", { name: "Local session logs" }).click();
  await expect(page.getByRole("heading", { name: "Demo session log" })).toBeVisible();
  await expect(page.getByText("session recording is disabled", { exact: true })).toBeVisible();
  const response = await page.request.get("/api/demo/sessions");
  expect(response.ok()).toBe(true);
  expect((await response.json()).sessions).toEqual([]);
});

test("actual HTTP server rejects cross-origin requests and never serves configuration files", async ({ request }) => {
  const crossOrigin = await request.get("/config", { headers: { Origin: "https://example.invalid" } });
  expect(crossOrigin.status()).toBe(403);
  const secrets = await request.get("/static/demo/.env");
  expect(secrets.status()).toBe(404);
});

test("legacy autostart URLs only select an agent; Connect remains an explicit action", async ({ page }) => {
  const sockets = [];
  page.on("websocket", (socket) => sockets.push(socket.url()));
  await page.goto("/?agent=fixture-agent&autostart=1");
  await expect(page.getByLabel("Session agent", { exact: true })).toHaveValue("fixture-agent");
  await page.waitForLoadState("networkidle");
  expect(sockets).toEqual([]);
  expect(await page.evaluate(() => window.microphoneCalls)).toBe(0);
  await expect(page.getByRole("button", { name: "Connect & start session" })).toBeEnabled();
});
