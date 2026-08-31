import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import { formatPrintDateTime } from '../lib/printJobs'
import { makeSpool } from '../test/spoolFixture'
import type { PrintJob, PrintJobSpool } from '../types/printJob'
import type { Spool } from '../types/spool'
import { PrintJobDetailsPage } from './PrintJobDetailsPage'

const timestamp = '2026-08-30T18:10:00Z'

function link(id: number, overrides: Partial<PrintJobSpool> = {}): PrintJobSpool {
  return { id, spool_id: id, position: id - 1, estimated_weight_g: '10', actual_weight_g: null, filament_cost_per_g: null, material_cost: null, material_cost_currency: null, created_at: timestamp, updated_at: timestamp, ...overrides }
}

function job(overrides: Partial<PrintJob> = {}): PrintJob {
  return { id: 42, name: 'Boneco Multicolor', status: 'PLANNED', spools: [link(1)], total_estimated_weight_g: '10', total_actual_weight_g: null, estimated_time_minutes: 240, actual_time_minutes: null, printer_name: 'Bambu Lab A1', started_at: null, finished_at: null, notes: 'Primeira linha\nSegunda linha', created_at: timestamp, updated_at: timestamp, ...overrides }
}

function response(data: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(data) } as unknown as Response
}

function mockApi(printJob: PrintJob, spools: Spool[] = [makeSpool()]) {
  vi.mocked(fetch).mockImplementation((input) => Promise.resolve(response(String(input).startsWith('/api/prints/') ? printJob : spools)))
}

function renderPage(path = '/prints/42') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return { client, ...render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes><Route path="/prints/:id" element={<PrintJobDetailsPage />} /><Route path="/prints" element={<p>Prints destination</p>} /><Route path="/spools/:code" element={<p>Spool destination</p>} /></Routes></MemoryRouter></QueryClientProvider>) }
}

describe('PrintJobDetailsPage', () => {
  beforeEach(async () => { await i18n.changeLanguage('pt-BR'); vi.stubGlobal('fetch', vi.fn()) })
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

  it('shows a stable loading skeleton while the detail is loading', () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => undefined))
    renderPage()
    expect(screen.getByRole('status', { name: 'Carregando detalhes da impressão' })).toBeVisible()
  })

  it('handles invalid IDs and API 404 with a back action', async () => {
    vi.mocked(fetch).mockResolvedValue(response([], 404))
    const first = renderPage('/prints/999')
    expect(await screen.findByText('Impressão não encontrada.')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Voltar para Impressões' })).toHaveAttribute('href', '/prints')
    first.unmount()
    renderPage('/prints/not-a-number')
    expect(screen.getByText('Impressão não encontrada.')).toBeVisible()
  })

  it('retries a network/server failure without breaking the route', async () => {
    let detailCalls = 0
    vi.mocked(fetch).mockImplementation((input) => {
      if (String(input).startsWith('/api/prints/')) return Promise.resolve(++detailCalls === 1 ? response(null, 503) : response(job()))
      return Promise.resolve(response([makeSpool()]))
    })
    renderPage()
    expect(await screen.findByText('Não foi possível carregar esta impressão.')).toBeVisible()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Tentar novamente' }))
    expect(await screen.findByRole('heading', { name: 'Boneco Multicolor' })).toBeVisible()
  })

  it('renders the planned overview, fallbacks, notes, timeline, and valid actions', async () => {
    mockApi(job({ printer_name: null, started_at: null, finished_at: null, actual_time_minutes: null }))
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Boneco Multicolor' })).toBeVisible()
    expect(screen.getByText('Impressão #42')).toBeVisible()
    expect(screen.getAllByText('Planejada').length).toBeGreaterThan(0)
    expect(screen.getByText('4h')).toBeVisible()
    expect(screen.getAllByText('—').length).toBeGreaterThan(2)
    expect(screen.getByRole('link', { name: 'Editar' })).toHaveAttribute('href', '/prints/42/edit')
    expect(screen.getByRole('button', { name: 'Iniciar Impressão' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Finalizar Impressão' })).not.toBeInTheDocument()
    expect(screen.getByText(/Primeira linha/)).toHaveClass('whitespace-pre-wrap')
    const timeline = screen.getByRole('region', { name: 'Linha do tempo' })
    expect(timeline).toHaveTextContent('Criada')
    expect(timeline).not.toHaveTextContent('Iniciada')
    expect(timeline).not.toHaveTextContent('Concluída')
  })

  it('shows every one of ten spools, including archived history and code-based links', async () => {
    const links = Array.from({ length: 10 }, (_, index) => link(index + 1, { estimated_weight_g: String(index + 1) }))
    const spools = links.map(({ spool_id }) => makeSpool({ id: spool_id, code: `FIL-${String(spool_id).padStart(4, '0')}`, display_name: `Spool Histórico ${spool_id}`, ...(spool_id === 10 ? { status: 'ARCHIVED' as const, archived_at: timestamp } : {}) }))
    mockApi(job({ spools: links, total_estimated_weight_g: '55' }), spools)
    renderPage()
    const section = await screen.findByRole('region', { name: 'Spools e consumo' })
    for (let id = 1; id <= 10; id += 1) {
      expect(within(section).getByText(`Spool Histórico ${id}`)).toBeVisible()
      expect(within(section).getByText(`FIL-${String(id).padStart(4, '0')}`)).toBeVisible()
    }
    expect(within(section).getAllByText(/eSUN · PLA · Black/)).toHaveLength(10)
    expect(within(section).getByText('Arquivado')).toBeVisible()
    expect(within(section).getAllByRole('link', { name: 'Ver Spool' })[9]).toHaveAttribute('href', '/spools/FIL-0010')
    expect(within(section).getByText('55 g')).toBeVisible()
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('renders a three-spool breakdown with association-specific estimates and actuals', async () => {
    const links = [
      link(1, { estimated_weight_g: '80', actual_weight_g: '76.4' }),
      link(2, { estimated_weight_g: '35', actual_weight_g: '31.2' }),
      link(3, { estimated_weight_g: '15', actual_weight_g: '0' }),
    ]
    mockApi(job({ status: 'SUCCESS', spools: links, total_estimated_weight_g: '130', total_actual_weight_g: '107.6' }), [makeSpool({ id: 1, display_name: 'PLA Preto' }), makeSpool({ id: 2, display_name: 'PLA Branco' }), makeSpool({ id: 3, display_name: 'PVA Support' })])
    renderPage()
    const section = await screen.findByRole('region', { name: 'Spools e consumo' })
    for (const name of ['PLA Preto', 'PLA Branco', 'PVA Support']) expect(within(section).getByText(name)).toBeVisible()
    for (const weight of ['80 g', '76,4 g', '35 g', '31,2 g', '15 g', '0 g']) expect(within(section).getByText(weight)).toBeVisible()
  })

  it('preserves null versus zero and never presents partial totals as complete', async () => {
    const links = [
      link(1, { estimated_weight_g: '10', actual_weight_g: '0', material_cost: '0', filament_cost_per_g: '0', material_cost_currency: 'EUR' }),
      link(2, { estimated_weight_g: null, actual_weight_g: null, material_cost: null, material_cost_currency: null }),
    ]
    mockApi(job({ status: 'SUCCESS', spools: links, total_estimated_weight_g: null, total_actual_weight_g: null, actual_time_minutes: 17, started_at: '2026-08-30T18:30:00Z', finished_at: '2026-08-30T18:47:00Z' }), [makeSpool({ id: 1 }), makeSpool({ id: 2 })])
    renderPage()
    const spools = await screen.findByRole('region', { name: 'Spools e consumo' })
    expect(within(spools).getByText('Estimativa incompleta')).toBeVisible()
    expect(within(spools).getByText('Consumo parcial')).toBeVisible()
    expect(within(spools).getAllByText('0 g')).toHaveLength(1)
    expect(within(spools).getByText('Não informado')).toBeVisible()
    expect(within(spools).getAllByText(/0,00/).length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('Alguns custos não estão disponíveis.')).toBeVisible()
    expect(screen.getByText('Custo conhecido')).toBeVisible()
  })

  it('shows complete actual totals and same-currency snapshot totals', async () => {
    const links = [link(1, { actual_weight_g: '7.25', filament_cost_per_g: '0.024', material_cost: '1.84', material_cost_currency: 'EUR' }), link(2, { actual_weight_g: '2.75', filament_cost_per_g: '0.02', material_cost: '0.66', material_cost_currency: 'EUR' })]
    mockApi(job({ status: 'SUCCESS', spools: links, total_estimated_weight_g: '20', total_actual_weight_g: '10', actual_time_minutes: 257, started_at: '2026-08-30T18:30:00Z', finished_at: '2026-08-30T22:47:00Z' }), [makeSpool({ id: 1 }), makeSpool({ id: 2 })])
    renderPage()
    expect((await screen.findAllByText('10 g')).length).toBeGreaterThan(0)
    expect(screen.getByText('4h 17min')).toBeVisible()
    expect(screen.getByText('Custo total do material')).toBeVisible()
    expect(screen.getByText(/2,50/)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Iniciar Impressão' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Finalizar Impressão' })).not.toBeInTheDocument()
    const timeline = screen.getByRole('region', { name: 'Linha do tempo' })
    expect(timeline).toHaveTextContent('Criada')
    expect(timeline).toHaveTextContent('Iniciada')
    expect(timeline).toHaveTextContent('Concluída')
  })

  it('keeps different snapshot currencies separate', async () => {
    const links = [link(1, { actual_weight_g: '1', material_cost: '2.40', material_cost_currency: 'EUR' }), link(2, { actual_weight_g: '1', material_cost: '1.10', material_cost_currency: 'USD' })]
    mockApi(job({ status: 'SUCCESS', spools: links, total_actual_weight_g: '2' }), [makeSpool({ id: 1 }), makeSpool({ id: 2 })])
    renderPage()
    expect(await screen.findByText('Custos do material')).toBeVisible()
    expect(screen.getAllByText(/2,40/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/1,10/).length).toBeGreaterThan(0)
    expect(screen.queryByText(/3,50/)).not.toBeInTheDocument()
  })

  it('renders PRINTING elapsed time and only proven timeline events, then cleans its timer', async () => {
    const clearInterval = vi.spyOn(window, 'clearInterval')
    mockApi(job({ status: 'PRINTING', started_at: new Date(Date.now() - 90 * 60_000).toISOString(), finished_at: null }))
    const view = renderPage()
    expect(await screen.findByText('1h 30min')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Finalizar Impressão' })).toBeVisible()
    const timeline = screen.getByRole('region', { name: 'Linha do tempo' })
    expect(timeline).toHaveTextContent('Criada')
    expect(timeline).toHaveTextContent('Iniciada')
    expect(timeline).toHaveTextContent('Em andamento')
    expect(timeline).not.toHaveTextContent('Concluída')
    view.unmount()
    expect(clearInterval).toHaveBeenCalled()
    clearInterval.mockRestore()
  })

  it('does not fabricate completion events or render invalid dates for FAILED/CANCELLED', async () => {
    mockApi(job({ status: 'FAILED', created_at: 'invalid', started_at: null, finished_at: null }))
    renderPage()
    expect(await screen.findByText('Status atual:')).toBeVisible()
    expect(screen.getAllByText('Falhou').length).toBeGreaterThan(0)
    expect(screen.queryByText(/Invalid Date|NaN/)).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Linha do tempo' })).not.toHaveTextContent('Concluída')
  })

  it('supports CANCELLED without creating an unsupported operational action or event', async () => {
    mockApi(job({ status: 'CANCELLED', started_at: null, finished_at: null }))
    renderPage()
    expect((await screen.findAllByText('Cancelada')).length).toBeGreaterThan(0)
    expect(screen.getByText('Status atual:')).toBeVisible()
    expect(screen.queryByRole('button', { name: /Iniciar|Finalizar/ })).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Linha do tempo' })).toHaveTextContent('Criada')
  })

  it('uses English locale labels and preserves the real snapshot currency', async () => {
    await i18n.changeLanguage('en')
    mockApi(job({ status: 'SUCCESS', spools: [link(1, { actual_weight_g: '1', material_cost: '1.84', material_cost_currency: 'EUR' })], total_actual_weight_g: '1', started_at: timestamp, finished_at: '2026-08-30T22:47:00Z' }))
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Boneco Multicolor' })).toBeVisible()
    expect(screen.getByText('Overview')).toBeVisible()
    expect(screen.getAllByText(formatPrintDateTime('2026-08-30T22:47:00Z')).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/€1\.84/).length).toBeGreaterThan(0)
    expect(screen.queryByText(/BRL|R\$/)).not.toBeInTheDocument()
  })

  it('reuses Start and refreshes the detail in place', async () => {
    let current = job()
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = String(input)
      if (url.endsWith('/start') && init?.method === 'POST') { current = job({ status: 'PRINTING', started_at: new Date().toISOString() }); return Promise.resolve(response(current)) }
      return Promise.resolve(response(url.startsWith('/api/prints/') ? current : [makeSpool()]))
    })
    renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Iniciar Impressão' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Iniciar Impressão' }))
    expect(await screen.findByText('Impressão iniciada.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Finalizar Impressão' })).toBeVisible()
  })

  it('reuses Finish and immediately presents final consumption and cost snapshots', async () => {
    let current = job({ status: 'PRINTING', started_at: new Date(Date.now() - 60_000).toISOString() })
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = String(input)
      if (url.endsWith('/finish') && init?.method === 'POST') { current = job({ status: 'SUCCESS', started_at: current.started_at, finished_at: new Date().toISOString(), actual_time_minutes: 1, total_actual_weight_g: '2.5', spools: [link(1, { actual_weight_g: '2.5', material_cost: '0.05', filament_cost_per_g: '0.02', material_cost_currency: 'EUR' })] }); return Promise.resolve(response(current)) }
      return Promise.resolve(response(url.startsWith('/api/prints/') ? current : [makeSpool()]))
    })
    renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Finalizar Impressão' }))
    await user.type(screen.getByLabelText(/Filamento Consumido/), '2,5')
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Finalizar Impressão' }))
    expect(await screen.findByText('Impressão finalizada com sucesso.')).toBeVisible()
    expect(screen.getAllByText('2,5 g').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: 'Finalizar Impressão' })).not.toBeInTheDocument()
  })
})
