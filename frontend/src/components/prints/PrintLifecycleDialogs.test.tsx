import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../../i18n'
import { makeSpool } from '../../test/spoolFixture'
import type { PrintJob, PrintJobSpool } from '../../types/printJob'
import type { Spool } from '../../types/spool'
import { FinishPrintDialog, StartPrintDialog, type ResolvedPrintJobSpool } from './PrintLifecycleDialogs'

function link(spoolId: number, estimated: string | null = '10'): PrintJobSpool {
  return { id: spoolId, spool_id: spoolId, position: spoolId - 1, estimated_weight_g: estimated, actual_weight_g: null, filament_cost_per_g: null, material_cost: null, material_cost_currency: null, created_at: '2026-08-30T10:00:00Z', updated_at: '2026-08-30T10:00:00Z' }
}

function job(status: PrintJob['status'] = 'PLANNED', links = [link(1)]): PrintJob {
  return { id: 42, name: 'Boneco Multicolor', status, spools: links, total_estimated_weight_g: '10', total_actual_weight_g: null, estimated_time_minutes: 90, actual_time_minutes: null, printer_name: null, started_at: status === 'PRINTING' ? '2026-08-30T10:00:00Z' : null, finished_at: null, notes: null, created_at: '2026-08-30T09:00:00Z', updated_at: '2026-08-30T10:00:00Z' }
}

function entry(id: number, overrides: Partial<Spool> = {}, estimated: string | null = '10'): ResolvedPrintJobSpool {
  return { link: link(id, estimated), spool: makeSpool({ id, code: `FIL-${String(id).padStart(4, '0')}`, display_name: `Spool ${id}`, current_filament_weight_g: '100', ...overrides }) }
}

function response(data: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(data) } as unknown as Response
}

function renderWithClient(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const invalidation = vi.spyOn(client, 'invalidateQueries')
  const result = render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
  return { ...result, client, invalidation }
}

describe('StartPrintDialog', () => {
  beforeEach(async () => { await i18n.changeLanguage('pt-BR'); vi.stubGlobal('fetch', vi.fn()) })
  afterEach(() => vi.unstubAllGlobals())

  it('shows every associated spool, its identity and warnings without truncating ten entries', () => {
    const entries = Array.from({ length: 10 }, (_, index) => entry(index + 1, index === 0 ? { status: 'LOW' } : {}, index === 1 ? '120' : '10'))
    renderWithClient(<StartPrintDialog entries={entries} onCancel={vi.fn()} onSuccess={vi.fn()} printJob={job('PLANNED', entries.map((item) => item.link))} />)
    const dialog = screen.getByRole('dialog', { name: 'Iniciar “Boneco Multicolor”?' })
    expect(within(dialog).getByText('Esta impressão utilizará 10 spools.')).toBeVisible()
    expect(within(dialog).getByText('Spool 10')).toBeVisible()
    expect(within(dialog).getByText('FIL-0010')).toBeVisible()
    expect(within(dialog).getByText(/Este spool está com pouco filamento/)).toBeVisible()
    expect(within(dialog).getByText(/O peso estimado excede o filamento disponível/)).toBeVisible()
  })

  it.each([
    ['EMPTY', 'Este spool está vazio.'],
    ['ARCHIVED', 'Este spool está arquivado.'],
    ['IN_USE', 'Este spool já está em uso.'],
  ] as const)('blocks confirmation for a known %s spool', (status, warning) => {
    renderWithClient(<StartPrintDialog entries={[entry(1, { status })]} onCancel={vi.fn()} onSuccess={vi.fn()} printJob={job()} />)
    expect(screen.getByText(new RegExp(warning.replace('.', '\\.')))).toBeVisible()
    expect(screen.getByRole('button', { name: 'Iniciar Impressão' })).toBeDisabled()
  })

  it('cancels without a request and starts with a bodyless POST', async () => {
    const onCancel = vi.fn()
    const onSuccess = vi.fn()
    const entries = [entry(1), entry(2)]
    vi.mocked(fetch).mockResolvedValue(response(job('PRINTING', entries.map((item) => item.link))))
    const { invalidation } = renderWithClient(<StartPrintDialog entries={entries} onCancel={onCancel} onSuccess={onSuccess} printJob={job('PLANNED', entries.map((item) => item.link))} />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(onCancel).toHaveBeenCalledOnce()
    expect(fetch).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Iniciar Impressão' }))
    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce())
    const [url, init] = vi.mocked(fetch).mock.calls[0]
    expect(url).toBe('/api/prints/42/start')
    expect(init).toMatchObject({ method: 'POST' })
    expect(init).not.toHaveProperty('body')
    expect(JSON.stringify(init)).not.toContain('spool_id')
    expect(JSON.stringify(init)).not.toContain('status')
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['prints'] })
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['spools'] })
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['spool', 'FIL-0001'] })
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['spool', 'FIL-0002'] })
  })

  it('prevents double submit and refetches caches after a 409 conflict', async () => {
    let resolveRequest!: (value: Response) => void
    vi.mocked(fetch).mockImplementation(() => new Promise((resolve) => { resolveRequest = resolve }))
    const { invalidation } = renderWithClient(<StartPrintDialog entries={[entry(1)]} onCancel={vi.fn()} onSuccess={vi.fn()} printJob={job()} />)
    const button = screen.getByRole('button', { name: 'Iniciar Impressão' })
    fireEvent.click(button)
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
    fireEvent.click(button)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(await screen.findByRole('button', { name: 'Iniciando…' })).toBeDisabled()
    resolveRequest(response({ detail: 'Spool is already in use.' }, 409))
    expect(await screen.findByRole('alert')).toHaveTextContent('Um dos spools já está sendo utilizado')
    await waitFor(() => expect(invalidation).toHaveBeenCalledWith({ queryKey: ['prints'] }))
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['spools'] })
  })
})

describe('FinishPrintDialog', () => {
  beforeEach(async () => { await i18n.changeLanguage('pt-BR'); vi.stubGlobal('fetch', vi.fn()) })
  afterEach(() => vi.unstubAllGlobals())

  it('renders one spool-id-bound input for each of ten spools', () => {
    const entries = Array.from({ length: 10 }, (_, index) => entry(index + 1))
    renderWithClient(<FinishPrintDialog entries={entries} onCancel={vi.fn()} onSuccess={vi.fn()} printJob={job('PRINTING', entries.map((item) => item.link))} />)
    const inputs = screen.getAllByLabelText(/Filamento Consumido/)
    expect(inputs).toHaveLength(10)
    expect(inputs.map((input) => input.getAttribute('data-spool-id'))).toEqual(entries.map((item) => String(item.link.spool_id)))
    expect(screen.getByText('Spool 10')).toBeVisible()
  })

  it('omits empty inputs, preserves zero, normalizes decimal commas, and uses only the atomic finish endpoint', async () => {
    const entries = [entry(1), entry(2), entry(3)]
    const onSuccess = vi.fn()
    vi.mocked(fetch).mockResolvedValue(response(job('SUCCESS', entries.map((item) => item.link))))
    const { invalidation } = renderWithClient(<FinishPrintDialog entries={entries} onCancel={vi.fn()} onSuccess={onSuccess} printJob={job('PRINTING', entries.map((item) => item.link))} />)
    const user = userEvent.setup()
    const inputs = screen.getAllByLabelText(/Filamento Consumido/)
    await user.type(inputs[0], '0')
    await user.type(inputs[1], '3,5')
    expect(screen.getByText('Alguns spools estão sem consumo informado.')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Finalizar Impressão' }))
    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce())
    expect(fetch).toHaveBeenCalledTimes(1)
    const [url, init] = vi.mocked(fetch).mock.calls[0]
    expect(url).toBe('/api/prints/42/finish')
    expect(JSON.parse(String(init?.body))).toEqual({ consumptions: [{ spool_id: 1, actual_weight_g: 0 }, { spool_id: 2, actual_weight_g: 3.5 }] })
    expect(String(url)).not.toContain('/weight')
    expect(init?.body).not.toContain('status')
    expect(init?.body).not.toContain('actual_time')
    expect(init?.body).not.toContain('finished_at')
    expect(init?.body).not.toContain('material_cost')
    expect(init?.body).not.toContain('new_weight')
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['prints'] })
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['print', 42] })
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['spools'] })
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['spool', 'FIL-0001'] })
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['spool', 'FIL-0002'] })
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['spool', 'FIL-0003'] })
  })

  it('rejects negative, malformed, and excessive consumption in the correct spool block', async () => {
    renderWithClient(<FinishPrintDialog entries={[entry(1), entry(2, { current_filament_weight_g: '5' })]} onCancel={vi.fn()} onSuccess={vi.fn()} printJob={job('PRINTING', [link(1), link(2)])} />)
    const user = userEvent.setup()
    const inputs = screen.getAllByLabelText(/Filamento Consumido/)
    await user.type(inputs[0], '-1')
    await user.type(inputs[1], '5.1')
    await user.click(screen.getByRole('button', { name: 'Finalizar Impressão' }))
    expect(screen.getByText('Informe um consumo válido, igual ou maior que zero.')).toBeVisible()
    expect(screen.getByText('O consumo informado é maior que o filamento disponível.')).toBeVisible()
    expect(inputs[0]).toHaveAttribute('aria-invalid', 'true')
    expect(inputs[1]).toHaveAttribute('aria-invalid', 'true')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('maps a nested FastAPI 422 array index to the corresponding spool input', async () => {
    vi.mocked(fetch).mockResolvedValue(response({ detail: [{ loc: ['body', 'consumptions', 1, 'actual_weight_g'], msg: 'Server rejected second consumption', type: 'value_error' }] }, 422))
    renderWithClient(<FinishPrintDialog entries={[entry(7), entry(11)]} onCancel={vi.fn()} onSuccess={vi.fn()} printJob={job('PRINTING', [link(7), link(11)])} />)
    const user = userEvent.setup()
    const inputs = screen.getAllByLabelText(/Filamento Consumido/)
    await user.type(inputs[0], '1')
    await user.type(inputs[1], '2')
    await user.click(screen.getByRole('button', { name: 'Finalizar Impressão' }))
    expect(await screen.findByText('Informe um consumo válido, igual ou maior que zero.')).toBeVisible()
    expect(inputs[0]).toHaveAttribute('aria-invalid', 'false')
    expect(inputs[1]).toHaveAttribute('aria-invalid', 'true')
  })

  it('preserves inputs after a network failure and prevents double finish', async () => {
    let rejectRequest!: (reason: unknown) => void
    vi.mocked(fetch).mockImplementation(() => new Promise((_resolve, reject) => { rejectRequest = reject }))
    const { invalidation } = renderWithClient(<FinishPrintDialog entries={[entry(1)]} onCancel={vi.fn()} onSuccess={vi.fn()} printJob={job('PRINTING')} />)
    const user = userEvent.setup()
    const input = screen.getByLabelText(/Filamento Consumido/)
    await user.type(input, '4.25')
    const button = screen.getByRole('button', { name: 'Finalizar Impressão' })
    fireEvent.click(button)
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
    fireEvent.click(button)
    expect(fetch).toHaveBeenCalledTimes(1)
    rejectRequest(new TypeError('network failed'))
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível finalizar a impressão. Verifique a conexão')
    expect(input).toHaveValue('4.25')
    expect(invalidation).not.toHaveBeenCalled()
  })
})
