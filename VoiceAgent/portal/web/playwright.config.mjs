// Copyright (c) Microsoft. All rights reserved.
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: ["studio.spec.mjs", "privacy.spec.mjs"],
  outputDir: "./test-results/studio",
  fullyParallel: true,
  workers: 4,
  timeout: 30_000,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:8098",
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    permissions: ["microphone"],
    launchOptions: {
      args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
    },
  },
  webServer: {
    command: "node tests/serve.mjs",
    url: "http://127.0.0.1:8098/demo/",
    reuseExistingServer: false,
  },
});
