import { defineConfig } from "@playwright/test";

const servicePort = process.env.PORT ?? "8000";

export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  retries: 1,
  use: {
    baseURL: `http://127.0.0.1:${servicePort}`,
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
