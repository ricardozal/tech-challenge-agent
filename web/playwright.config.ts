import { defineConfig, devices } from '@playwright/test'

// Runs against the compose stack (`make up`, LLM_MODE=fake); see specs/002-demo-web/quickstart.md.
export default defineConfig({
  testDir: 'e2e',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1,
  reporter: 'list',
  use: { baseURL: process.env.WEB_URL ?? 'http://localhost:8080' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
