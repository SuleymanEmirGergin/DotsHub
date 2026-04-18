import { defineConfig, devices } from "@playwright/test";
import { config as loadEnv } from "dotenv";
import { resolve } from "node:path";

// Load staging credentials from .env.staging when E2E_MODE=staging.
// The file is gitignored; see .env.staging.example for the schema.
if (process.env.E2E_MODE === "staging") {
  loadEnv({ path: resolve(__dirname, ".env.staging") });
}

const isStaging = process.env.E2E_MODE === "staging";
const isCI = !!process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  // localhost tests run in parallel (pure smoke, no shared state).
  // staging tests serialize themselves via the `staging` project below.
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  // Staging hits one shared DB → force a single worker so seed/teardown
  // + parallel writes don't race.
  workers: isStaging ? 1 : isCI ? 1 : undefined,
  reporter: [["html", { open: "never" }], ["list"]],
  // Only attach setup/teardown for staging; localhost tests don't need them.
  globalSetup: isStaging ? require.resolve("./e2e/global-setup.ts") : undefined,
  globalTeardown: isStaging ? require.resolve("./e2e/global-teardown.ts") : undefined,
  use: {
    baseURL: isStaging
      ? process.env.PLAYWRIGHT_BASE_URL
      : (process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3002"),
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "localhost",
      testMatch: /localhost[\\/].*\.spec\.ts$/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "staging",
      testMatch: /staging[\\/].*\.spec\.ts$/,
      fullyParallel: false,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // Dev server only for localhost interactive runs — not CI, not staging.
  webServer: isStaging
    ? undefined
    : isCI
      ? undefined
      : {
          command: "pnpm run dev",
          url: "http://localhost:3002",
          reuseExistingServer: true,
          env: { PORT: "3002" },
        },
});
