import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  use: { baseURL: process.env.ARCHTWIN_WEB ?? "http://localhost:3200", trace: "retain-on-failure", viewport: { width: 1600, height: 1000 }, contextOptions: { reducedMotion: "reduce" } },
  reporter: [["list"]],
});
