import { expect, test } from '@playwright/test'

const timestamp = '2026-09-01T12:00:00Z'
const manufacturer = { id: 1, name: 'eSUN', website: null, created_at: timestamp, updated_at: timestamp }
const material = { id: 1, name: 'PLA', category: 'PLA', default_nozzle_temp_min: 190, default_nozzle_temp_max: 220, default_bed_temp_min: 50, default_bed_temp_max: 60, density_g_cm3: '1.24', notes: null, created_at: timestamp, updated_at: timestamp }
const spool = {
  id: 7, code: 'FIL-0007', manufacturer_id: 1, material_id: 1, manufacturer, material,
  location: { id: 1, name: 'Workshop' }, display_name: 'PLA Night Black', product_name: 'PLA+',
  color_name: 'Night Black', color_hex: '#111111', diameter_mm: '1.75', initial_filament_weight_g: '1000',
  current_filament_weight_g: '742.5', empty_spool_weight_g: '210', purchase_price: '24.90', store_name: 'Local Shop',
  currency: 'EUR', purchase_date: '2026-08-15', opened_at: timestamp, last_used_at: timestamp,
  nozzle_temp_min: 190, nozzle_temp_max: 220, bed_temp_min: 50, bed_temp_max: 60,
  status: 'OPEN', needs_drying: false, last_dried_at: null, notes: 'Entity text stays unchanged.',
  created_at: timestamp, updated_at: timestamp, archived_at: null, remaining_percent: 74.25,
}
const printJob = {
  id: 7, name: 'Calibration Tower', status: 'PRINTING',
  spools: [{ id: 1, spool_id: 7, position: 0, estimated_weight_g: '12.5', actual_weight_g: null, filament_cost_per_g: '0.0249', material_cost: null, material_cost_currency: 'EUR', created_at: timestamp, updated_at: timestamp }],
  total_estimated_weight_g: '12.5', total_actual_weight_g: null, estimated_time_minutes: 90, actual_time_minutes: null,
  printer_name: 'A1 Mini', started_at: timestamp, finished_at: null, notes: null, created_at: timestamp, updated_at: timestamp,
}

test.beforeEach(async ({ page }) => {
  await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/manufacturers') return route.fulfill({ json: [manufacturer] })
    if (path === '/api/materials') return route.fulfill({ json: [material] })
    if (path === '/api/spools/FIL-0007') return route.fulfill({ json: spool })
    if (path === '/api/spools') return route.fulfill({ json: [spool] })
    if (path === '/api/prints/7') return route.fulfill({ json: printJob })
    if (path === '/api/prints') return route.fulfill({ json: [printJob] })
    return route.fulfill({ status: 404, json: { detail: 'Not found in i18n browser fixture.' } })
  })
})

const matrix = {
  'pt-BR': [
    ['/', 'Inventário', 'Adicionar Spool'],
    ['/inventory/new', 'Novo Spool', 'Criar Spool'],
    ['/spools/FIL-0007', 'PLA Night Black', 'Editar Spool'],
    ['/prints/new', 'Nova Impressão', 'Criar Impressão'],
    ['/prints/7', 'Calibration Tower', 'Finalizar Impressão'],
    ['/scan', 'Escanear QR', 'Iniciar câmera'],
    ['/gcode', 'Analisar G-code', 'Selecionar arquivo'],
    ['/settings', 'Configurações', 'Baixar manual (PDF)'],
  ],
  en: [
    ['/', 'Inventory', 'Add Spool'],
    ['/inventory/new', 'New Spool', 'Create Spool'],
    ['/spools/FIL-0007', 'PLA Night Black', 'Edit Spool'],
    ['/prints/new', 'New Print', 'Create Print'],
    ['/prints/7', 'Calibration Tower', 'Finish Print'],
    ['/scan', 'Scan QR', 'Start camera'],
    ['/gcode', 'G-code Analysis', 'Select file'],
    ['/settings', 'Settings', 'Download manual (PDF)'],
  ],
} as const

for (const [locale, routes] of Object.entries(matrix)) {
  test(`${locale} keeps representative routes coherent`, async ({ page }) => {
    test.setTimeout(180_000)
    await page.addInitScript((selected) => window.localStorage.setItem('fcc-language', selected), locale)
    for (const [route, heading, action] of routes) {
      await page.goto(route)
      await expect(page.getByRole('heading', { name: heading, exact: true }).first()).toBeVisible()
      await expect(page.getByText(action, { exact: true }).first()).toBeVisible()
      await expect(page.locator('html')).toHaveAttribute('lang', locale)
    }
  })
}

test('language switch is immediate and survives reload', async ({ page }) => {
  test.setTimeout(60_000)
  await page.goto('/settings')
  await page.getByRole('combobox', { name: 'Idioma' }).selectOption('en')
  await expect(page.getByRole('heading', { name: 'Settings' }).first()).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Settings' }).first()).toBeVisible()
  expect(await page.evaluate(() => window.localStorage.getItem('fcc-language'))).toBe('en')
})

test.describe('mobile translation length spot check', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  for (const locale of ['pt-BR', 'en'] as const) {
    for (const route of ['/', '/prints/new', '/gcode', '/settings']) {
      test(`${locale} ${route} has no translation-caused horizontal overflow`, async ({ page }) => {
        await page.addInitScript((selected) => window.localStorage.setItem('fcc-language', selected), locale)
        await page.goto(route)
        await expect(page.locator('#main-content')).toBeVisible()
        await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
      })
    }
  }
})
