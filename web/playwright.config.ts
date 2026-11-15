import { defineConfig, devices } from "@playwright/test";

// Each test starts its own `kiripix serve` on a temporary Project (e2e/harness.ts). `npm run test:e2e` builds first.
export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  // Each test starts a server and builds its room with several `uv run` calls, 20 to 25 s alone. At the default workers (half the cores)
  // they share the CPU and the slowest took 50 to 60 s, so 60 s timed out at random (ticket 0202). A test that is really stuck still
  // fails on its own 20 s `expect`, so the longer limit only costs time when something is already broken.
  timeout: 120_000,
  expect: { timeout: 20_000 },
  forbidOnly: !!process.env.CI,
  reporter: "list",
  use: { ...devices["Desktop Chrome"], screenshot: "only-on-failure", trace: "retain-on-failure" },
});
