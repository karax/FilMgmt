import { expect, test } from '@playwright/test'
import { makeSpool } from '../src/test/spoolFixture'

for (const mode of ['create', 'edit']) {
  test(`${mode}: nested failure, preserved data and successful retry at 390x844`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.addInitScript(() => localStorage.setItem('fcc-language', 'pt-BR'))
    const job = { id: 42, name: 'Case ESP32', status: 'PLANNED', printer_name: 'A1', notes: 'Preservar notas', estimated_time_minutes: 65,
      spools: [{ spool_id: 1, estimated_weight_g: '10' }, { spool_id: 2, estimated_weight_g: '20' }] }
    let saves = 0
    const pageErrors: string[] = []
    page.on('pageerror', error => pageErrors.push(error.message))
    await page.route(url => url.pathname === '/api/spools', route => route.fulfill({ json: [makeSpool({ id: 1, purchase_price: '20' }), makeSpool({ id: 2, purchase_price: '20' })] }))
    await page.route(url => url.pathname === '/api/prints' || url.pathname === '/api/prints/42', route => {
      if (['POST', 'PATCH'].includes(route.request().method())) {
        saves++
        return route.fulfill(saves === 1
          ? { status: 422, json: { detail: [{ loc: ['body', 'spools', 1, 'estimated_weight_g'], type: 'greater_than', msg: 'Input should be greater than 0' }] } }
          : { status: mode === 'create' ? 201 : 200, json: job })
      }
      return route.fulfill({ json: route.request().url().endsWith('/42') ? job : [] })
    })
    await page.goto(mode === 'create' ? '/prints/new' : '/prints/42/edit')
    if (mode === 'create') {
      await page.getByLabel('Nome da Impressão', { exact: true }).fill(job.name)
      await page.getByLabel('Spool', { exact: true }).selectOption('1')
      await page.getByLabel('Peso Estimado', { exact: true }).fill('10')
      await page.getByRole('button', { name: '+ Add Spool' }).click()
      await page.getByLabel('Spool', { exact: true }).nth(1).selectOption('2')
      await page.getByLabel('Peso Estimado', { exact: true }).nth(1).fill('20')
      await page.getByLabel('Impressora', { exact: true }).fill(job.printer_name)
      await page.getByLabel('Observações', { exact: true }).fill(job.notes)
    }
    const save = page.getByRole('button', { name: mode === 'create' ? 'Criar Impressão' : 'Salvar Alterações', exact: true })
    await save.click()
    await expect(page.getByRole('alert')).toContainText('Não foi possível salvar a impressão.')
    const weight = page.getByLabel('Peso Estimado', { exact: true }).nth(1)
    await expect(weight).toBeFocused()
    await expect(weight).toHaveAccessibleDescription('Informe um valor maior que zero.')
    await expect(page.getByLabel('Peso Estimado', { exact: true }).first()).toHaveAttribute('aria-invalid', 'false')
    await expect(page.getByLabel('Nome da Impressão', { exact: true })).toHaveValue(job.name)
    await expect(page.getByLabel('Impressora', { exact: true })).toHaveValue(job.printer_name)
    await expect(page.getByLabel('Observações', { exact: true })).toHaveValue(job.notes)
    await expect(page.getByLabel('Spool', { exact: true }).nth(1)).toHaveValue('2')
    await expect(weight).toHaveValue('20')
    expect(page.url()).toContain(mode === 'create' ? '/prints/new' : '/prints/42/edit')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    const error = page.locator('#print-spools\\.2\\.estimated_weight_g-error')
    const bounds = await error.boundingBox()
    expect(bounds!.x).toBeGreaterThanOrEqual(0)
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(390)
    await save.scrollIntoViewIfNeeded()
    await expect(save).toBeInViewport()
    await expect(page.getByRole('alert')).toBeInViewport()
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: testInfo.outputPath(`${mode}-save-error-mobile.png`), fullPage: true })
    await weight.fill('21')
    await expect(weight).toHaveAttribute('aria-invalid', 'false')
    await save.click()
    await expect(page).toHaveURL(/\/prints$/)
    expect(saves).toBe(2)
    expect(pageErrors).toEqual([])
  })
}
