import { expect, test, type Page } from '@playwright/test'

const THEME_STORAGE_KEY = 'fcc-theme'
const INVENTORY_VIEW_STORAGE_KEY = 'fcc-inventory-view'

const dashboardSpools = [
  {
    id: 1,
    code: 'FIL-0001',
    manufacturer: { id: 1, name: 'eSUN' },
    material: { id: 1, name: 'PLA+', category: 'PLA' },
    product_name: 'PLA+ HS',
    color_name: 'Black',
    color_hex: '#111111',
    initial_filament_weight_g: '1000.000',
    current_filament_weight_g: '800.000',
    remaining_percent: 80,
    status: 'OPEN',
    needs_drying: false,
  },
  {
    id: 2,
    code: 'FIL-0002',
    manufacturer: { id: 1, name: 'eSUN' },
    material: { id: 1, name: 'PLA+', category: 'PLA' },
    product_name: null,
    color_name: 'Orange',
    color_hex: '#F97316',
    initial_filament_weight_g: '1000.000',
    current_filament_weight_g: '150.000',
    remaining_percent: 15,
    status: 'LOW',
    needs_drying: false,
  },
  {
    id: 3,
    code: 'FIL-0003',
    manufacturer: { id: 1, name: 'eSUN' },
    material: { id: 2, name: 'PETG', category: 'PETG' },
    product_name: null,
    color_name: 'Signal Blue',
    color_hex: '#2563EB',
    initial_filament_weight_g: '1000.000',
    current_filament_weight_g: '0.000',
    remaining_percent: 0,
    status: 'EMPTY',
    needs_drying: true,
  },
]

async function useTheme(page: Page, theme: 'light' | 'dark' | 'system') {
  await page.addInitScript(
    ([storageKey, selectedTheme]) => {
      window.localStorage.setItem(storageKey, selectedTheme)
    },
    [THEME_STORAGE_KEY, theme],
  )
}

async function mockDashboardSpools(page: Page) {
  await page.route('**/api/spools', async (route) => {
    await route.fulfill({ json: dashboardSpools })
  })
}

async function mockSpoolCatalogs(page: Page) {
  await page.route('**/api/manufacturers', (route) =>
    route.fulfill({ json: [{ id: 1, name: 'eSUN' }] }),
  )
  await page.route('**/api/materials', (route) =>
    route.fulfill({ json: [{ id: 2, name: 'PLA+', category: 'PLA' }] }),
  )
}

async function useInventoryView(page: Page, view: 'grid' | 'table') {
  await page.addInitScript(
    ([storageKey, selectedView]) => {
      window.localStorage.setItem(storageKey, selectedView)
    },
    [INVENTORY_VIEW_STORAGE_KEY, view],
  )
}

test('desktop dashboard in light mode', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await useTheme(page, 'light')
  await mockDashboardSpools(page)
  await page.goto('/dashboard')

  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Dashboard')
  await expect(page.getByRole('heading', { name: 'Total Spools' })).toBeVisible()
  await expect(page.getByText('FIL-0003')).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Dashboard' }),
  ).toHaveAttribute('aria-current', 'page')
  await expect(page).toHaveScreenshot('dashboard-desktop-light.png', {
    fullPage: true,
  })
})

test('mobile dashboard in dark mode without horizontal overflow', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await useTheme(page, 'dark')
  await mockDashboardSpools(page)
  await page.goto('/dashboard')

  await expect(page.locator('html')).toHaveClass(/dark/)
  await expect(page.getByRole('heading', { name: 'Inventory overview' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Needs Attention' })).toBeVisible()
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true)
  await expect(page).toHaveScreenshot('dashboard-mobile-dark.png', {
    fullPage: true,
  })
})

test('desktop inventory in dark mode with active navigation', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await useTheme(page, 'dark')
  await useInventoryView(page, 'table')
  await mockDashboardSpools(page)
  await page.goto('/inventory')

  await expect(page.locator('html')).toHaveClass(/dark/)
  await expect(page.getByRole('table', { name: 'Spool inventory' })).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Inventory' }),
  ).toHaveAttribute('aria-current', 'page')
  await expect(page).toHaveScreenshot('inventory-table-desktop-dark.png', {
    fullPage: true,
  })
})

test('mobile inventory and open navigation drawer', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await useTheme(page, 'light')
  await useInventoryView(page, 'grid')
  await mockDashboardSpools(page)
  await page.goto('/inventory')

  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Inventory')
  await expect(page.getByRole('list', { name: 'Spools in grid view' })).toBeVisible()
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true)
  await expect(page).toHaveScreenshot('inventory-mobile-light.png', {
    fullPage: true,
  })

  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  const drawer = page.getByRole('dialog', { name: 'Mobile navigation' })
  await expect(drawer).toBeVisible()
  await expect(
    drawer.getByRole('link', { name: 'Inventory' }),
  ).toHaveAttribute('aria-current', 'page')
  await expect(page).toHaveScreenshot('inventory-mobile-drawer.png', {
    fullPage: true,
  })
})

test('inventory preserves the selected view after refresh', async ({ page }) => {
  await mockDashboardSpools(page)
  await page.goto('/inventory')

  await page.getByRole('button', { name: 'Table view' }).click()
  await expect(page.getByRole('table', { name: 'Spool inventory' })).toBeVisible()
  await page.reload()

  await expect(page.getByRole('button', { name: 'Table view' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByRole('table', { name: 'Spool inventory' })).toBeVisible()
})

test('mobile new spool form in dark mode has no horizontal overflow', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await useTheme(page, 'dark')
  await mockSpoolCatalogs(page)
  await page.goto('/inventory/new')

  await expect(page.getByRole('heading', { level: 1 })).toHaveText('New Spool')
  await expect(page.getByRole('combobox', { name: 'Manufacturer' })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Material' })).toBeVisible()
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true)
  await expect(page).toHaveScreenshot('new-spool-mobile-dark.png', {
    fullPage: true,
  })
})
