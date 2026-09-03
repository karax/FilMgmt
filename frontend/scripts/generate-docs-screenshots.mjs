import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import { spawn, spawnSync } from 'node:child_process'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from 'playwright'

import { findChromiumExecutable } from './browser-support.mjs'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const projectRoot = path.resolve(frontendRoot, '..')
const backendRoot = path.join(projectRoot, 'backend')
const outputRoot = path.join(projectRoot, 'docs', 'user-guide', 'images')
const desktopRoot = path.join(outputRoot, 'desktop')
const mobileRoot = path.join(outputRoot, 'mobile')
const baseUrl = 'http://127.0.0.1:5173'
const apiUrl = 'http://127.0.0.1:8000/api'
const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'fcc-user-guide-'))
const databaseUrl = `sqlite+pysqlite:///${path.join(tempRoot, 'user-guide.db')}`
const uploadsRoot = path.join(tempRoot, 'gcode-uploads')
const screenshotScope = process.env.DOCS_SCREENSHOTS_ONLY?.trim()
const backendEnvironment = {
  ...process.env,
  DATABASE_URL: databaseUrl,
  GCODE_UPLOAD_DIRECTORY: uploadsRoot,
}
const childProcesses = []

await Promise.all([
  mkdir(desktopRoot, { recursive: true }),
  mkdir(mobileRoot, { recursive: true }),
])

const migration = spawnSync(
  path.join(backendRoot, '.venv', 'bin', 'python'),
  ['-m', 'alembic', 'upgrade', 'head'],
  { cwd: backendRoot, env: backendEnvironment, encoding: 'utf8' },
)
if (migration.status !== 0) {
  throw new Error(`Could not prepare the isolated documentation database.\n${migration.stderr}`)
}

const backend = spawn(
  path.join(backendRoot, '.venv', 'bin', 'uvicorn'),
  ['app.main:app', '--host', '127.0.0.1', '--port', '8000'],
  { cwd: backendRoot, env: backendEnvironment, stdio: 'ignore' },
)
childProcesses.push(backend)

const vite = spawn(
  process.execPath,
  [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', '127.0.0.1', '--port', '5173'],
  { cwd: frontendRoot, env: process.env, stdio: 'ignore' },
)
childProcesses.push(vite)

let browser
try {
  await Promise.all([
    waitForHttp(`${apiUrl}/health`),
    waitForHttp(baseUrl),
  ])
  const scenario = await seedScenario()
  const gcodePath = path.join(tempRoot, 'dragon-multicolor.gcode')
  await writeFile(gcodePath, demoGCode(), 'utf8')

  browser = await chromium.launch({
    headless: true,
    executablePath: findChromiumExecutable(),
  })

  const desktop = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: 'light',
    locale: 'pt-BR',
    acceptDownloads: true,
  })
  await prepareContext(desktop)
  if (screenshotScope === 'settings') await captureSettings(desktop, desktopRoot)
  else await captureDesktop(desktop, scenario, gcodePath)
  await desktop.close()

  const mobile = await browser.newContext({
    viewport: { width: 390, height: 844 },
    colorScheme: 'light',
    locale: 'pt-BR',
    acceptDownloads: true,
  })
  await prepareContext(mobile)
  if (screenshotScope === 'settings') await captureSettings(mobile, mobileRoot)
  else await captureMobile(mobile, scenario, gcodePath)
  await mobile.close()

  console.log(screenshotScope === 'settings'
    ? 'Regenerated the desktop and mobile Settings screenshots.'
    : `Generated 27 desktop screenshots in ${path.relative(projectRoot, desktopRoot)}`)
  if (screenshotScope !== 'settings') console.log(`Generated 6 mobile screenshots in ${path.relative(projectRoot, mobileRoot)}`)
  console.log(`Documentation database was isolated at ${tempRoot}`)
} finally {
  if (browser) await browser.close()
  for (const child of childProcesses.reverse()) {
    if (!child.killed) child.kill('SIGTERM')
  }
  await Promise.all(childProcesses.map((child) => waitForExit(child)))
  await rm(tempRoot, { recursive: true, force: true })
}

async function prepareContext(context) {
  await context.addInitScript(() => {
    window.localStorage.setItem('fcc-language', 'pt-BR')
    window.localStorage.setItem('fcc-theme', 'light')
    window.localStorage.setItem('fcc-inventory-view', 'table')
  })
}

async function captureDesktop(context, scenario, gcodePath) {
  let page = await context.newPage()
  reportPageProblems(page)
  await captureRoute(page, '/dashboard', desktop('01-dashboard.png'))
  await scrollToHeading(page, 'Precisam de Atenção')
  await capture(page, desktop('02-dashboard-attention.png'))

  await captureRoute(page, '/inventory', desktop('03-inventory-table.png'))
  await page.getByRole('button', { name: 'Visualização em grade' }).click()
  await settle(page)
  await capture(page, desktop('04-inventory-grid.png'))
  await page.getByRole('button', { name: /^Filtros/ }).click()
  await capture(page, desktop('05-inventory-filters.png'))
  await captureRoute(page, '/inventory?search=Orange', desktop('06-inventory-search.png'))

  page = await resetPage(page)
  await go(page, '/inventory/new')
  await page.locator('#spool-manufacturerId').selectOption({ label: 'Bambu Lab' })
  await page.locator('#spool-materialId').selectOption({ label: 'PLA' })
  await page.locator('#spool-colorName').fill('Verde Jade')
  await page.locator('#spool-productName').fill('PLA Basic')
  await page.locator('#spool-colorHex').fill('#3BA272')
  await settle(page)
  await capture(page, desktop('07-new-spool-basic.png'))
  await page.locator('#spool-storeName').fill('Loja 3D Central')
  await page.locator('#spool-purchasePrice').fill('21.90')
  await page.locator('#spool-purchaseDate').fill('2026-08-28')
  await scrollToHeading(page, 'Compra')
  await capture(page, desktop('08-new-spool-purchase.png'))

  page = await resetPage(page)
  await captureRoute(page, `/spools/${scenario.black.code}`, desktop('09-spool-details.png'))
  await captureLocator(page, page.locator('section[aria-labelledby="spool-qr-title"]'), desktop('10-spool-qr.png'))

  await go(page, `/spools/${scenario.low.code}`)
  await page.getByRole('button', { name: 'Archive Spool' }).click()
  await captureLocator(page, page.getByRole('dialog'), desktop('11-spool-archive-dialog.png'))

  await captureRoute(page, `/qr/spool/${scenario.black.code}`, desktop('12-qr-landing.png'))
  await captureRoute(page, '/scan', desktop('13-qr-scanner.png'))

  page = await resetPage(page)
  await captureRoute(page, '/prints', desktop('14-print-tracker.png'))

  await go(page, '/prints/new')
  await page.getByLabel('Nome da Impressão').fill('Dragon Miniature')
  await page.getByLabel('Spool').first().selectOption(String(scenario.black.id))
  await page.getByLabel('Peso Estimado').first().fill('120')
  await page.getByRole('button', { name: '+ Add Spool' }).click()
  await page.getByLabel('Spool').nth(1).selectOption(String(scenario.orange.id))
  await page.getByLabel('Peso Estimado').nth(1).fill('80')
  await page.getByText('Custo estimado da impressão').scrollIntoViewIfNeeded()
  await capture(page, desktop('15-new-print-multi-spool.png'))

  await captureRoute(page, `/prints/${scenario.planned.id}`, desktop('16-planned-print.png'))
  await page.getByRole('button', { name: 'Iniciar Impressão' }).click()
  await captureLocator(page, page.getByRole('dialog'), desktop('17-start-print-dialog.png'))

  await captureRoute(page, `/prints/${scenario.printing.id}`, desktop('18-printing.png'))
  await page.getByRole('button', { name: 'Finalizar Impressão' }).click()
  await page.locator('input[data-spool-id]').first().fill('86,4')
  await captureLocator(page, page.getByRole('dialog'), desktop('19-finish-print-dialog.png'))
  await captureRoute(page, `/prints/${scenario.finished.id}`, desktop('20-finished-print.png'))

  page = await resetPage(page)
  await captureRoute(page, '/gcode', desktop('21-gcode-upload.png'))
  await page.locator('input[type="file"]').setInputFiles(gcodePath)
  await capture(page, desktop('22-gcode-selected.png'))
  await page.getByRole('button', { name: 'Enviar G-code' }).click()
  await page.getByText('Upload concluído').waitFor()
  await page.getByRole('button', { name: 'Analisar G-code' }).click()
  await page.getByRole('heading', { name: 'Arquivo analisado' }).waitFor()
  await page.getByRole('region', { name: 'Resultado da detecção de material' }).waitFor()
  await page.getByRole('region', { name: 'Resultado do tempo estimado' }).waitFor()
  await scrollToHeading(page, 'Arquivo analisado')
  await capture(page, desktop('23-gcode-summary.png'))
  await scrollToHeading(page, 'Detecção de material')
  await capture(page, desktop('24-gcode-material-detection.png'))
  await scrollToHeading(page, 'Tempo estimado')
  await capture(page, desktop('25-gcode-time.png'))
  await page.getByRole('button', { name: 'Calcular peso' }).click()
  await page.getByRole('region', { name: 'Resultado do peso estimado' }).waitFor()
  await scrollToHeading(page, 'Peso estimado')
  await capture(page, desktop('26-gcode-weight.png'))

  page = await resetPage(page)
  await captureRoute(page, '/settings', desktop('27-settings.png'))
  await page.close()
}

async function captureMobile(context, scenario, gcodePath) {
  let page = await context.newPage()
  reportPageProblems(page)
  await captureRoute(page, '/inventory', mobile('01-inventory.png'))

  page = await resetPage(page)
  await go(page, '/inventory/new')
  await page.locator('#spool-manufacturerId').selectOption({ label: 'Bambu Lab' })
  await page.locator('#spool-materialId').selectOption({ label: 'PLA' })
  await page.locator('#spool-colorName').fill('Verde Jade')
  await capture(page, mobile('02-new-spool.png'))

  page = await resetPage(page)
  await go(page, '/prints/new')
  await page.getByLabel('Nome da Impressão').fill('Dragon Miniature')
  await page.getByLabel('Spool').first().selectOption(String(scenario.black.id))
  await page.getByLabel('Peso Estimado').first().fill('120')
  await page.getByRole('button', { name: '+ Add Spool' }).click()
  await page.getByLabel('Spool').nth(1).selectOption(String(scenario.orange.id))
  await page.getByLabel('Peso Estimado').nth(1).fill('80')
  await page.getByText('Custo estimado da impressão').scrollIntoViewIfNeeded()
  await capture(page, mobile('03-new-print.png'))

  page = await resetPage(page)
  await captureRoute(page, '/scan', mobile('04-qr-scanner.png'))
  page = await resetPage(page)
  await go(page, '/gcode')
  await page.locator('input[type="file"]').setInputFiles(gcodePath)
  await capture(page, mobile('05-gcode.png'))
  page = await resetPage(page)
  await captureRoute(page, '/settings', mobile('06-settings.png'))
  await page.close()
}

async function captureSettings(context, root) {
  const page = await context.newPage()
  reportPageProblems(page)
  const filename = root === desktopRoot ? '27-settings.png' : '06-settings.png'
  await captureRoute(page, '/settings', path.join(root, filename))
  await page.close()
}

async function captureRoute(page, route, output) {
  await go(page, route)
  await capture(page, output)
}

async function go(page, route) {
  let status = 'client navigation'
  if (page.url().startsWith(baseUrl)) {
    await page.evaluate((nextRoute) => {
      window.history.pushState(null, '', nextRoute)
      window.dispatchEvent(new PopStateEvent('popstate'))
    }, route)
    await page.waitForURL(`${baseUrl}${route}`)
  } else {
    const response = await page.goto(`${baseUrl}${route}`, { waitUntil: 'networkidle' })
    status = String(response?.status() ?? 'unknown')
  }
  try {
    await page.locator('#main-content').waitFor({ state: 'visible', timeout: 12_000 })
  } catch (error) {
    const body = (await page.locator('body').innerText().catch(() => '')).slice(0, 1_500)
    throw new Error(`Route ${route} did not render (${status}).\n${body}`, { cause: error })
  }
  await settle(page)
}

function reportPageProblems(page) {
  page.on('pageerror', (error) => console.error(`pageerror: ${error.message}`))
  page.on('console', (message) => {
    if (message.type() === 'error') console.error(`console.error: ${message.text()}`)
  })
}

async function resetPage(page) {
  const context = page.context()
  await page.close()
  const nextPage = await context.newPage()
  reportPageProblems(nextPage)
  return nextPage
}

async function settle(page) {
  await page.waitForLoadState('networkidle')
  await page.evaluate(async () => {
    await document.fonts.ready
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
  })
  await page.waitForTimeout(180)
}

async function scrollToHeading(page, name) {
  const heading = page.getByRole('heading', { name, exact: true }).first()
  await heading.waitFor({ state: 'visible' })
  await heading.evaluate((element) => element.scrollIntoView({ block: 'start' }))
  await page.evaluate(() => window.scrollBy(0, -96))
  await settle(page)
}

async function capture(page, output) {
  await settle(page)
  await page.screenshot({ path: output, fullPage: false })
  console.log(`Screenshot: ${path.relative(projectRoot, output)}`)
}

async function captureLocator(page, locator, output) {
  await locator.waitFor({ state: 'visible' })
  await settle(page)
  await locator.screenshot({ path: output })
  console.log(`Screenshot: ${path.relative(projectRoot, output)}`)
}

function desktop(name) {
  return path.join(desktopRoot, name)
}

function mobile(name) {
  return path.join(mobileRoot, name)
}

async function seedScenario() {
  const manufacturers = {}
  for (const name of ['Bambu Lab', 'Polymaker', 'eSUN', 'Prusament', 'Generic', 'Fiberlogy']) {
    manufacturers[name] = await post('/manufacturers', { name, website: null })
  }
  const materials = {}
  for (const item of [
    { name: 'PLA', category: 'PLA', density_g_cm3: 1.24, default_nozzle_temp_min: 190, default_nozzle_temp_max: 230, default_bed_temp_min: 35, default_bed_temp_max: 60 },
    { name: 'PETG', category: 'PETG', density_g_cm3: 1.27, default_nozzle_temp_min: 220, default_nozzle_temp_max: 260, default_bed_temp_min: 65, default_bed_temp_max: 85 },
    { name: 'TPU', category: 'TPU', density_g_cm3: 1.21, default_nozzle_temp_min: 210, default_nozzle_temp_max: 240, default_bed_temp_min: 30, default_bed_temp_max: 60 },
    { name: 'ABS', category: 'ABS', density_g_cm3: 1.04, default_nozzle_temp_min: 230, default_nozzle_temp_max: 260, default_bed_temp_min: 90, default_bed_temp_max: 110 },
    { name: 'PA', category: 'NYLON', density_g_cm3: 1.14, default_nozzle_temp_min: 245, default_nozzle_temp_max: 285, default_bed_temp_min: 70, default_bed_temp_max: 100 },
  ]) {
    materials[item.name] = await post('/materials', { ...item, notes: null })
  }

  const spool = (manufacturer, material, values) => post('/spools', {
    manufacturer_id: manufacturers[manufacturer].id,
    material_id: materials[material].id,
    display_name: values.name,
    product_name: values.product,
    color_name: values.color,
    color_hex: values.hex,
    diameter_mm: 1.75,
    initial_filament_weight_g: values.initial ?? 1000,
    current_filament_weight_g: values.current,
    empty_spool_weight_g: values.empty ?? 230,
    purchase_price: values.price,
    store_name: values.store ?? 'Loja 3D Central',
    currency: values.currency ?? 'EUR',
    purchase_date: values.purchaseDate ?? '2026-08-18',
    nozzle_temp_min: materials[material].default_nozzle_temp_min,
    nozzle_temp_max: materials[material].default_nozzle_temp_max,
    bed_temp_min: materials[material].default_bed_temp_min,
    bed_temp_max: materials[material].default_bed_temp_max,
    status: values.status ?? 'OPEN',
    needs_drying: values.needsDrying ?? false,
    last_dried_at: null,
    notes: values.notes ?? null,
  })

  const black = await spool('Bambu Lab', 'PLA', { name: 'Bambu Lab Black', product: 'PLA Basic', color: 'Preto', hex: '#111827', current: 740, price: 21 })
  const orange = await spool('Polymaker', 'PETG', { name: 'Polymaker Orange', product: 'PolyLite PETG', color: 'Laranja', hex: '#F97316', current: 520, price: 23 })
  const low = await spool('eSUN', 'TPU', { name: 'eSUN TPU Red', product: 'eTPU-95A', color: 'Vermelho', hex: '#DC2626', current: 180, price: 28 })
  const sealed = await spool('Prusament', 'PLA', { name: 'Prusament Galaxy Silver', product: 'Prusament PLA', color: 'Galaxy Silver', hex: '#9CA3AF', current: 1000, price: 31, status: 'SEALED' })
  const empty = await spool('Generic', 'ABS', { name: 'ABS Branco — vazio', product: 'ABS', color: 'Branco', hex: '#F8FAFC', current: 0, price: null })
  const blue = await spool('Bambu Lab', 'PLA', { name: 'Bambu Lab Blue', product: 'PLA Matte', color: 'Azul Marinho', hex: '#1D4ED8', current: 680, price: 22 })
  const green = await spool('Polymaker', 'PETG', { name: 'Polymaker Green', product: 'PolyLite PETG', color: 'Verde', hex: '#16A34A', current: 610, price: 24 })
  const nylon = await spool('Fiberlogy', 'PA', { name: 'Fiberlogy Nylon Natural', product: 'PA12+CF', color: 'Natural', hex: '#D6D3D1', initial: 750, current: 650, price: 42, needsDrying: true })
  const archived = await spool('Generic', 'PLA', { name: 'Spool antigo', product: 'PLA', color: 'Cinza', hex: '#6B7280', current: 100, price: 18 })
  await post(`/spools/${archived.code}/archive`, {})

  const finished = await post('/prints', {
    name: 'Suporte articulado',
    spools: [
      { spool_id: black.id, estimated_weight_g: 120 },
      { spool_id: orange.id, estimated_weight_g: 80 },
    ],
    estimated_time_minutes: 275,
    printer_name: 'CoreXY Oficina',
    notes: 'Perfil de qualidade 0,20 mm.',
  })
  await post(`/prints/${finished.id}/start`, null)
  const finishedResult = await post(`/prints/${finished.id}/finish`, {
    consumptions: [
      { spool_id: black.id, actual_weight_g: 114.6 },
      { spool_id: orange.id, actual_weight_g: 76.2 },
    ],
  })

  const planned = await post('/prints', {
    name: 'Dragon Miniature',
    spools: [
      { spool_id: black.id, estimated_weight_g: 120 },
      { spool_id: orange.id, estimated_weight_g: 80 },
    ],
    estimated_time_minutes: 370,
    printer_name: 'CoreXY Oficina',
    notes: 'Corpo preto e detalhes laranja.',
  })

  const printing = await post('/prints', {
    name: 'Organizador modular',
    spools: [
      { spool_id: blue.id, estimated_weight_g: 95 },
      { spool_id: green.id, estimated_weight_g: 40 },
    ],
    estimated_time_minutes: 215,
    printer_name: 'CoreXY Oficina',
    notes: 'Impressão em andamento para a bancada.',
  })
  const printingResult = await post(`/prints/${printing.id}/start`, null)

  const dryingPrint = await post('/prints', {
    name: 'Calibração Nylon',
    spools: [{ spool_id: nylon.id, estimated_weight_g: 12 }],
    estimated_time_minutes: 35,
    printer_name: 'CoreXY Oficina',
    notes: null,
  })
  await post(`/prints/${dryingPrint.id}/start`, null)
  await post(`/prints/${dryingPrint.id}/finish`, { consumptions: [] })

  return { black, orange, low, sealed, empty, blue, green, nylon, archived, planned, printing: printingResult, finished: finishedResult }
}

async function post(route, payload) {
  const response = await fetch(`${apiUrl}${route}`, {
    method: 'POST',
    headers: payload === null ? { Accept: 'application/json' } : { Accept: 'application/json', 'Content-Type': 'application/json' },
    ...(payload === null ? {} : { body: JSON.stringify(payload) }),
  })
  if (!response.ok) {
    throw new Error(`Seed request failed: POST ${route} -> ${response.status} ${await response.text()}`)
  }
  return response.status === 204 ? null : response.json()
}

async function waitForHttp(url) {
  const deadline = Date.now() + 30_000
  let lastError
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url)
      if (response.ok) return
      lastError = new Error(`${url} returned ${response.status}`)
    } catch (error) {
      lastError = error
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw lastError ?? new Error(`Timed out waiting for ${url}`)
}

function waitForExit(child) {
  if (child.exitCode !== null || child.signalCode !== null) return Promise.resolve()
  return new Promise((resolve) => {
    const timeout = setTimeout(() => {
      child.kill('SIGKILL')
      resolve()
    }, 5_000)
    child.once('exit', () => {
      clearTimeout(timeout)
      resolve()
    })
  })
}

function demoGCode() {
  return `; generated by Filament Command Center documentation fixture
; filament_type = PLA,PETG
; filament_diameter = 1.75,1.75
; estimated printing time = 1h 12m 30s
G21
G90
M82
M104 S215
M140 S60
T0
G92 E0
G1 X10 Y10 Z0.20 F3000
G1 X110 Y10 E48.0 F1200
G1 X110 Y110 E96.0
G1 X10 Y110 E144.0
G1 X10 Y10 E192.0
T1
M104 S240
G92 E0
G1 X30 Y30 F3000
G1 X90 Y30 E28.0 F1000
G1 X90 Y90 E56.0
G1 X30 Y90 E84.0
G1 X30 Y30 E112.0
G4 S5
`
}
