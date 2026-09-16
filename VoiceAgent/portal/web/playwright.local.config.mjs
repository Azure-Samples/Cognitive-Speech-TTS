// Copyright (c) Microsoft. All rights reserved.
import { defineConfig } from "@playwright/test";

const baseURL = "http://127.0.0.1:8097";
export default defineConfig({
  testDir: "./tests",
  testMatch: "local.spec.mjs",
  outputDir: "./test-results/local",
  workers: 1,
  timeout: 30_000,
  reporter: "list",
  use: {
    baseURL,
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
    command: "node tests/run-portal.mjs",
    url: `${baseURL}/healthz`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
