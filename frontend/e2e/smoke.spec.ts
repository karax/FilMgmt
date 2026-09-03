import { expect, test as base } from '@playwright/test'

type Spool = { code: string }

function isLocalApiUrl(rawUrl: string) {
  try {
    const url = new URL(rawUrl)
    return ['127.0.0.1', 'localhost'].includes(url.hostname)
      && url.pathname.startsWith('/api/')
  } catch {
    return false
  }
}

const test = base.extend({
  page: async ({ page }, use) => {
    const problems: string[] = []
    page.on('pageerror', (error) => problems.push(`pageerror: ${error.message}`))
    page.on('console', (message) => {
      if (message.type() === 'error') problems.push(`console.error: ${message.text()}`)
    })
    page.on('requestfailed', (request) => {
      const errorText = request.failure()?.errorText
      if (isLocalApiUrl(request.url()) && errorText !== 'net::ERR_ABORTED') {
        problems.push(`requestfailed: ${request.method()} ${request.url()} (${errorText ?? 'unknown'})`)
      }
    })
    page.on('response', (response) => {
      if (isLocalApiUrl(response.url()) && response.status() >= 500) {
        problems.push(`api ${response.status()}: ${response.url()}`)
      }
    })
    await page.addInitScript(() => window.localStorage.setItem('fcc-language', 'en'))

    await use(page)
    expect(problems, problems.join('\n')).toEqual([])
  },
})

test('inventory loads at the home route and can show the table', async ({ page }) => {
  const health = await page.request.get('/api/health')
  expect(health.ok()).toBe(true)

  await page.goto('/')
  await expect(page.locator('#main-content')).toBeVisible()
  await expect(page.locator('#inventory-title')).toBeVisible()
  await expect(page.locator('nav').first()).toBeVisible()

  await page.getByRole('button', { name: 'Table view' }).click()
  await expect(page.getByRole('table', { name: 'Spool inventory' })).toBeVisible()
})

test('G-code analysis renders the accessible file selector', async ({ page }) => {
  await page.goto('/gcode')

  await expect(page.locator('#gcode-title')).toBeVisible()
  await expect(page.getByLabel('Select file')).toHaveAttribute('accept', '.gcode')
  await expect(page.locator('#main-content')).toBeVisible()
})

test('QR scanner keeps the manual fallback available without a camera', async ({ page }) => {
  await page.goto('/scan')

  await expect(page.locator('#scan-title')).toBeVisible()
  await expect(page.getByLabel('Spool code')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open spool' })).toBeVisible()
})

test('Settings downloads the complete user manual with the configured filename', async ({ page }) => {
  await page.goto('/settings')

  const link = page.getByRole('link', { name: 'Download manual (PDF)' })
  await expect(link).toHaveAttribute('href', '/docs/filament-command-center-user-guide.pdf')
  await expect(link).toHaveAttribute('download', 'filament-command-center-user-guide.pdf')

  const response = await page.request.get('/docs/filament-command-center-user-guide.pdf')
  expect(response.ok()).toBe(true)
  expect(response.headers()['content-type']).toContain('application/pdf')
  expect((await response.body()).subarray(0, 5).toString()).toBe('%PDF-')

  const downloadPromise = page.waitForEvent('download')
  await link.click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('filament-command-center-user-guide.pdf')
})

test('an existing spool details page renders from a dynamically discovered code', async ({ page }) => {
  const response = await page.request.get('/api/spools')
  expect(response.ok()).toBe(true)
  const spools = await response.json() as Spool[]
  test.skip(spools.length === 0, 'No spool exists in the current local inventory.')

  await page.goto(`/spools/${encodeURIComponent(spools[0].code)}`)
  await expect(page.locator('#spool-details-title')).toBeVisible()
})

test.describe('mobile viewport', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  for (const route of ['/', '/gcode', '/scan']) {
    test(`${route} is visible without horizontal overflow`, async ({ page }) => {
      await page.goto(route)
      await expect(page.locator('#main-content')).toBeVisible()
      await expect.poll(() => page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      )).toBe(true)
    })
  }
})
