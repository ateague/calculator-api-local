import { defineConfig } from "@playwright/test";
import { applicationOrigin } from "./application-origin";

export default defineConfig({
  testDir: ".",
  timeout: 30_000,
  retries: 1,
  workers: 1,
  use: {
    baseURL: applicationOrigin,
    headless: true,
    screenshot: "on",
    video: "retain-on-failure",
    trace: "retain-on-failure",
  },
  reporter: [
    ["list"],
    [
      "json",
      {
        outputFile: `${process.env.MCODE_DIR}/fe_testing/playwright-results.json`,
      },
    ],
  ],
});
