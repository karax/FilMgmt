import { defineConfig, devices } from '@playwright/test'

import { findChromiumExecutable } from './scripts/browser-support.mjs'

export default defineConfig({
  testDir: './e2e',
  testMatch: 'smoke.spec.ts',
  outputDir: './test-results/e2e-production',
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  retries: 0,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report/e2e-production', open: 'never' }]],
  use: {
    baseURL: process.env.FCC_PRODUCTION_URL ?? 'http://127.0.0.1:8080',
    launchOptions: {
      executablePath: findChromiumExecutable(),
    },
    colorScheme: 'light',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'off',
  },
  projects: [
    {
      name: 'chromium-system-production',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
