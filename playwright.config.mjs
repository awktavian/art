import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:4173",
    reducedMotion: "reduce",
    trace: "retain-on-failure",
  },
  webServer: {
<<<<<<< HEAD
    command:
      "python3 -m http.server 4173 --bind 127.0.0.1 --directory ..",
||||||| a04dee5
=======
    command: "node scripts/pages-server.mjs",
>>>>>>> origin/main
    url: "http://127.0.0.1:4173/art/",
    reuseExistingServer: !process.env.CI,
    timeout: 15_000,
  },
});
