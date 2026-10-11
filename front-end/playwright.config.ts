import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: true,
  workers: 3,
  timeout: 60000,
  use: {
    baseURL: process.env.TEST_BASE_URL ?? "http://localhost:3001",
    trace: "retain-on-failure",
  },
  reporter: "list",
});
