import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

import { chromium } from 'playwright'

import { findChromiumExecutable, isLocalApiUrl } from './browser-support.mjs'

const baseUrl = 'http://127.0.0.1:5173'
const requestedRoute = process.argv[2] ?? '/'

function normalizeRoute(route) {
  if (!route.startsWith('/') || route.startsWith('//')) {
    throw new Error('The screenshot route must be a local path beginning with a single /.')
  }
  const url = new URL(route, baseUrl)
  if (url.origin !== baseUrl || url.pathname.split('/').includes('..')) {
    throw new Error('The screenshot route must stay inside the local frontend.')
  }
  return `${url.pathname}${url.search}`
}

function screenshotName(route) {
  const safe = route === '/'
    ? 'home'
    : route.replace(/^\/+/, '').replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-|-$/g, '')
  return safe || 'page'
}

function collectPageProblems(page) {
  const problems = []
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
  return problems
}

const route = normalizeRoute(requestedRoute)
const outputDirectory = resolve('artifacts/browser')
const basename = screenshotName(route)
await mkdir(outputDirectory, { recursive: true })

const browser = await chromium.launch({
  headless: true,
  executablePath: findChromiumExecutable(),
})

try {
  const outputs = []
  const problems = []
  for (const [label, viewport] of [
    ['desktop', { width: 1440, height: 900 }],
    ['mobile', { width: 390, height: 844 }],
  ]) {
    const page = await browser.newPage({ viewport })
    problems.push(...collectPageProblems(page))
    await page.goto(`${baseUrl}${route}`, { waitUntil: 'networkidle' })
    if (route === '/') {
      await page.waitForURL(`${baseUrl}/inventory`)
      await page.locator('#inventory-title').waitFor({ state: 'visible' })
    } else {
      await page.locator('#main-content > *').first().waitFor({ state: 'visible' })
    }
    const output = resolve(outputDirectory, `${basename}-${label}.png`)
    await page.screenshot({ path: output, fullPage: true })
    outputs.push(output)
    await page.close()
  }

  for (const output of outputs) console.log(`Screenshot: ${output}`)
  if (problems.length > 0) {
    console.error(problems.join('\n'))
    process.exitCode = 1
  }
} finally {
  await browser.close()
}
