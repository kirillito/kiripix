import { defineConfig, devices } from "@playwright/test";

// Each test starts its own `kiripix serve` on a temporary Project (e2e/harness.ts). `npm run test:e2e` builds first.
export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  timeout: 60_000,
  expect: { timeout: 20_000 },
  forbidOnly: !!process.env.CI,
  reporter: "list",
  use: { ...devices["Desktop Chrome"], screenshot: "only-on-failure", trace: "retain-on-failure" },
});
