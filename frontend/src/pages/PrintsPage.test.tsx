import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import { makeSpool } from '../test/spoolFixture'
import type { PrintJob } from '../types/printJob'
import type { Spool } from '../types/spool'
import { PrintsPage } from './PrintsPage'

const baseJob = (overrides: Partial<PrintJob> = {}): PrintJob => ({
  id: 1, name: 'Raspberry Pi Case', status: 'PLANNED', spools: [{ id: 1, spool_id: 1, position: 0, estimated_weight_g: '183', actual_weight_g: null, filament_cost_per_g: null, material_cost: null, material_cost_currency: null, created_at: '2026-08-30T10:00:00Z', updated_at: '2026-08-30T10:00:00Z' }], total_estimated_weight_g: '183', total_actual_weight_g: null, estimated_time_minutes: 260, actual_time_minutes: null,
  printer_name: 'Bambu Lab A1', started_at: null, finished_at: null, notes: null,
  created_at: '2026-08-30T10:00:00Z', updated_at: '2026-08-30T10:00:00Z', ...overrides,
})

function apiResponse(data: unknown, ok = true): Response {
  return { ok, status: ok ? 200 : 503, json: vi.fn().mockResolvedValue(data) } as unknown as Response
}

function renderPrints() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return { client, ...render(<QueryClientProvider client={client}><PrintsPage /></QueryClientProvider>) }
}

describe('PrintsPage', () => {
  beforeEach(async () => { await i18n.changeLanguage('pt-BR'); vi.stubGlobal('fetch', vi.fn()) })
  afterEach(() => vi.unstubAllGlobals())

  it('shows a useful empty state when no print jobs exist', async () => {
    vi.mocked(fetch).mockImplementation((input) => Promise.resolve(apiResponse(String(input).includes('/api/prints') ? [] : [])))
    renderPrints()
    expect(await screen.findByText('Nenhuma impressão registrada ainda.')).toBeVisible()
  })

  it('groups jobs and resolves an archived spool once from the shared list', async () => {
    const spool: Spool = makeSpool({ id: 1, code: 'FIL-0042', display_name: 'PLA Preto Principal', status: 'ARCHIVED' })
    const jobs = [
      baseJob({ id: 1, status: 'PRINTING', started_at: '2026-08-30T13:42:00Z' }),
      baseJob({ id: 2, status: 'PLANNED', name: 'ESP32 Case' }),
      baseJob({ id: 3, status: 'SUCCESS', spools: [{ id: 3, spool_id: 1, position: 0, estimated_weight_g: null, actual_weight_g: '249', filament_cost_per_g: '0.022', material_cost: '5.4755', material_cost_currency: 'EUR', created_at: '2026-08-30T10:00:00Z', updated_at: '2026-08-30T10:00:00Z' }], total_actual_weight_g: '249', actual_time_minutes: 1500, finished_at: '2026-08-30T20:00:00Z' }),
      baseJob({ id: 4, status: 'FAILED', name: 'Failed part' }),
      baseJob({ id: 5, status: 'CANCELLED', name: 'Cancelled part' }),
    ]
    vi.mocked(fetch).mockImplementation((input) => Promise.resolve(apiResponse(String(input).includes('/api/prints') ? jobs : [spool])))
    renderPrints()

    const printing = await screen.findByRole('region', { name: 'Em andamento' })
    expect(within(printing).getByText(/PLA Preto Principal.*FIL-0042/)).toBeVisible()
    expect(screen.getByRole('region', { name: 'Planejadas' })).toHaveTextContent('ESP32 Case')
    const completed = screen.getByRole('region', { name: 'Concluídas' })
    expect(within(completed).getAllByText('249 g')).toHaveLength(2)
    expect(within(completed).getByText('25h')).toBeVisible()
    expect(within(completed).getByText(/5,48/)).toBeVisible()
    expect(screen.getByRole('region', { name: 'Outras' })).toHaveTextContent('Cancelled part')
  })

  it('renders associated spool information and does not render null cost values', async () => {
    const spool = makeSpool({ id: 1, code: 'FIL-0001', display_name: 'Associated spool' })
    vi.mocked(fetch).mockImplementation((input) => Promise.resolve(apiResponse(String(input).includes('/api/prints') ? [baseJob()] : [spool])))
    renderPrints()
    expect(await screen.findByText(/Associated spool.*FIL-0001/)).toBeVisible()
    expect(screen.queryByText('null')).not.toBeInTheDocument()
  })

  it('shows an error and retries the print request', async () => {
    vi.mocked(fetch).mockImplementationOnce(() => Promise.resolve(apiResponse([], false))).mockImplementation(() => Promise.resolve(apiResponse([])))
    renderPrints()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Tentar novamente' }))
    expect(await screen.findByText('Nenhuma impressão registrada ainda.')).toBeVisible()
  })

  it('uses English labels without changing internal statuses', async () => {
    await i18n.changeLanguage('en')
    vi.mocked(fetch).mockImplementation((input) => Promise.resolve(apiResponse(String(input).includes('/api/prints') ? [baseJob({ status: 'PRINTING' })] : [])))
    renderPrints()
    expect(await screen.findByRole('heading', { name: 'Print Jobs' })).toBeVisible()
    expect((await screen.findAllByText('Printing')).length).toBeGreaterThan(1)
    expect(screen.getByRole('button', { name: 'Finish Print' })).toBeVisible()
  })

  it('shows lifecycle actions only for their valid statuses', async () => {
    const spool = makeSpool({ id: 1 })
    const jobs = [baseJob(), baseJob({ id: 2, status: 'PRINTING', started_at: new Date(Date.now() - 90 * 60_000).toISOString() }), baseJob({ id: 3, status: 'SUCCESS', finished_at: '2026-08-30T12:00:00Z' })]
    vi.mocked(fetch).mockImplementation((input) => Promise.resolve(apiResponse(String(input).includes('/api/prints') ? jobs : [spool])))
    renderPrints()
    const planned = await screen.findByRole('region', { name: 'Planejadas' })
    expect(within(planned).getByRole('link', { name: 'Editar' })).toBeVisible()
    expect(within(planned).getByRole('link', { name: 'Ver detalhes' })).toHaveAttribute('href', '/prints/1')
    expect(within(planned).getByRole('button', { name: 'Iniciar Impressão' })).toBeVisible()
    expect(within(planned).queryByRole('button', { name: 'Finalizar Impressão' })).not.toBeInTheDocument()
    const printing = screen.getByRole('region', { name: 'Em andamento' })
    expect(within(printing).getByRole('button', { name: 'Finalizar Impressão' })).toBeVisible()
    expect(within(printing).queryByRole('button', { name: 'Iniciar Impressão' })).not.toBeInTheDocument()
    expect(within(printing).queryByRole('link', { name: 'Editar' })).not.toBeInTheDocument()
    const success = screen.getByRole('region', { name: 'Concluídas' })
    expect(within(success).queryByRole('button')).not.toBeInTheDocument()
    expect(within(success).getByRole('link', { name: 'Ver detalhes' })).toHaveAttribute('href', '/prints/3')
  })

  it('moves a planned job to Printing after the server confirms Start', async () => {
    const spool = makeSpool({ id: 1, display_name: 'PLA Principal' })
    let current = baseJob()
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = String(input)
      if (url.endsWith('/start') && init?.method === 'POST') {
        current = baseJob({ status: 'PRINTING', started_at: new Date().toISOString() })
        return Promise.resolve(apiResponse(current))
      }
      return Promise.resolve(apiResponse(url.includes('/api/prints') ? [current] : [spool]))
    })
    renderPrints()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Iniciar Impressão' }))
    const dialog = screen.getByRole('dialog', { name: 'Iniciar “Raspberry Pi Case”?' })
    expect(dialog).toHaveTextContent('PLA Principal')
    await user.click(within(dialog).getByRole('button', { name: 'Iniciar Impressão' }))
    expect(await screen.findByText('Impressão iniciada.')).toBeVisible()
    expect(await screen.findByRole('region', { name: 'Em andamento' })).toHaveTextContent('Raspberry Pi Case')
    expect(screen.getByRole('button', { name: 'Finalizar Impressão' })).toBeVisible()
  })

  it('moves a printing job to Success and presents actual consumption and grouped currencies', async () => {
    const first = makeSpool({ id: 1, display_name: 'PLA Preto' })
    const second = makeSpool({ id: 2, code: 'FIL-0002', display_name: 'PVA' })
    const links = [
      { ...baseJob().spools[0], spool_id: 1, actual_weight_g: null },
      { ...baseJob().spools[0], id: 2, spool_id: 2, position: 1, actual_weight_g: null },
    ]
    let current = baseJob({ status: 'PRINTING', spools: links, started_at: new Date(Date.now() - 15 * 60_000).toISOString() })
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = String(input)
      if (url.endsWith('/finish') && init?.method === 'POST') {
        current = baseJob({ status: 'SUCCESS', started_at: current.started_at, finished_at: new Date().toISOString(), actual_time_minutes: 15, total_actual_weight_g: '3.5', spools: [
          { ...links[0], actual_weight_g: '2', material_cost: '2.40', material_cost_currency: 'EUR' },
          { ...links[1], actual_weight_g: '1.5', material_cost: '1.10', material_cost_currency: 'USD' },
        ] })
        return Promise.resolve(apiResponse(current))
      }
      return Promise.resolve(apiResponse(url.includes('/api/prints') ? [current] : [first, second]))
    })
    renderPrints()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Finalizar Impressão' }))
    const inputs = screen.getAllByLabelText(/Filamento Consumido/)
    await user.type(inputs[0], '2')
    await user.type(inputs[1], '1,5')
    await user.click(within(screen.getByRole('dialog', { name: 'Finalizar Impressão' })).getByRole('button', { name: 'Finalizar Impressão' }))
    expect(await screen.findByText('Impressão finalizada com sucesso.')).toBeVisible()
    const completed = await screen.findByRole('region', { name: 'Concluídas' })
    expect(completed).toHaveTextContent('PLA Preto: 2 g')
    expect(completed).toHaveTextContent('PVA: 1,5 g')
    expect(completed).toHaveTextContent(/2,40/)
    expect(completed).toHaveTextContent(/1,10/)
    expect(completed).not.toHaveTextContent(/3,50\s*€/)
  })

  it('cleans up the running timer when the card unmounts', async () => {
    const clearInterval = vi.spyOn(window, 'clearInterval')
    vi.mocked(fetch).mockImplementation((input) => Promise.resolve(apiResponse(String(input).includes('/api/prints') ? [baseJob({ status: 'PRINTING', started_at: new Date().toISOString() })] : [makeSpool()])))
    const view = renderPrints()
    expect(await screen.findByText(/Em andamento há/)).toBeVisible()
    view.unmount()
    expect(clearInterval).toHaveBeenCalled()
    clearInterval.mockRestore()
  })

  it('synchronizes a double-finished job after a 409 without repeating consumption', async () => {
    const spool = makeSpool({ id: 1, display_name: 'Shared spool' })
    let current = baseJob({ status: 'PRINTING', started_at: new Date(Date.now() - 60_000).toISOString() })
    let finishRequests = 0
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = String(input)
      if (url.endsWith('/finish') && init?.method === 'POST') {
        finishRequests += 1
        current = baseJob({ status: 'SUCCESS', started_at: current.started_at, finished_at: new Date().toISOString(), actual_time_minutes: 1, total_actual_weight_g: '1', spools: [{ ...current.spools[0], actual_weight_g: '1' }] })
        return Promise.resolve({ ok: false, status: 409, json: vi.fn().mockResolvedValue({ detail: 'Only printing jobs can be finished.' }) } as unknown as Response)
      }
      return Promise.resolve(apiResponse(url.includes('/api/prints') ? [current] : [spool]))
    })
    renderPrints()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Finalizar Impressão' }))
    await user.type(screen.getByLabelText(/Filamento Consumido/), '1')
    await user.click(within(screen.getByRole('dialog', { name: 'Finalizar Impressão' })).getByRole('button', { name: 'Finalizar Impressão' }))
    expect(await screen.findByRole('region', { name: 'Concluídas' })).toHaveTextContent('Raspberry Pi Case')
    expect(screen.queryByRole('dialog', { name: 'Finalizar Impressão' })).not.toBeInTheDocument()
    expect(finishRequests).toBe(1)
  })
})
