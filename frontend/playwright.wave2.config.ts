import { defineConfig, devices } from '@playwright/test'
import { findChromiumExecutable } from './scripts/browser-support.mjs'

const useExistingServers = process.env.FCC_WAVE2_USE_EXISTING_SERVERS === '1'

export default defineConfig({
  testDir: './e2e', outputDir: './test-results/wave2', workers: 1,
  timeout: 120_000, expect: { timeout: 30_000 }, retries: 0,
  reporter: [['list']],
  use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:15173',
    launchOptions: {
      executablePath: findChromiumExecutable(),
      args: ['--disable-gpu', '--disable-dev-shm-usage'],
    },
    screenshot: 'only-on-failure', trace: 'off' },
  projects: [
    { name: 'wave2', testMatch: 'wave-2-onboarding.spec.ts' },
    { name: 'smoke', testIgnore: 'wave-2-onboarding.spec.ts', dependencies: ['wave2'] },
  ],
  webServer: useExistingServers ? undefined : [
    { command: 'node scripts/wave2-test-backend.mjs', url: 'http://127.0.0.1:18002/api/health', reuseExistingServer: false, timeout: 60_000 },
    { command: 'npx vite build && npm run preview -- --host 127.0.0.1 --port 15173 --strictPort', url: 'http://127.0.0.1:15173', reuseExistingServer: false,
      env: { FCC_TEST_API_TARGET: 'http://127.0.0.1:18002' }, timeout: 120_000 },
  ],
})
