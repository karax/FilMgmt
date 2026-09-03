import { accessSync, constants } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const chromiumCommands = [
  'chromium',
  'chromium-browser',
  'google-chrome',
  'google-chrome-stable',
]

function isExecutable(path) {
  try {
    accessSync(path, constants.X_OK)
    return true
  } catch {
    return false
  }
}

function resolveCommand(command) {
  if (command.includes('/')) return isExecutable(command) ? command : null

  const result = spawnSync('which', [command], { encoding: 'utf8' })
  const path = result.status === 0 ? result.stdout.trim() : ''
  return path && isExecutable(path) ? path : null
}

export function findChromiumExecutable(environment = process.env) {
  const override = environment.CHROMIUM_PATH?.trim()
  if (override) {
    const executable = resolveCommand(override)
    if (!executable) {
      throw new Error(`CHROMIUM_PATH is not an executable Chromium path: ${override}`)
    }
    return executable
  }

  for (const command of chromiumCommands) {
    const executable = resolveCommand(command)
    if (executable) return executable
  }

  throw new Error(
    'Chromium was not found. Install a system Chromium package or set CHROMIUM_PATH.',
  )
}

export function chromiumVersion(executable) {
  const result = spawnSync(executable, ['--version'], { encoding: 'utf8' })
  if (result.status !== 0) {
    throw new Error(`Could not read Chromium version from ${executable}.`)
  }
  return result.stdout.trim()
}

export function architecture() {
  const result = spawnSync('uname', ['-m'], { encoding: 'utf8' })
  return result.status === 0 ? result.stdout.trim() : process.arch
}

export function playwrightVersion() {
  return require('@playwright/test/package.json').version
}

export function isLocalApiUrl(rawUrl) {
  try {
    const url = new URL(rawUrl)
    return ['127.0.0.1', 'localhost'].includes(url.hostname)
      && url.pathname.startsWith('/api/')
  } catch {
    return false
  }
}

export async function checkHttp(url) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 5_000)
  try {
    const response = await fetch(url, { signal: controller.signal })
    return { ok: response.ok, status: response.status }
  } catch (error) {
    return { ok: false, status: null, error: error instanceof Error ? error.message : String(error) }
  } finally {
    clearTimeout(timeout)
  }
}
