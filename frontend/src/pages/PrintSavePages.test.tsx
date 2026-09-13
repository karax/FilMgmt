import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import { makeSpool } from '../test/spoolFixture'
import { NewPrintJobPage } from './NewPrintJobPage'
import { EditPrintJobPage } from './EditPrintJobPage'

const job = { id: 42, status: 'PLANNED', name: 'Case', printer_name: 'A1', notes: 'Keep notes', estimated_time_minutes: 65,
  spools: [{ spool_id: 1, estimated_weight_g: '10' }, { spool_id: 2, estimated_weight_g: '20' }] }
const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body }) as Response
const issue = (loc: unknown[], type = 'greater_than') => ({ detail: [{ loc: ['body', ...loc], type, msg: 'INTERNAL SQL trace must never appear' }] })

async function setup(mode: 'create' | 'edit', save: () => Promise<Response>, failRefresh = false) {
  let spoolReads = 0
  const mutation = vi.fn(save)
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST' || init?.method === 'PATCH') return mutation()
    if (url.includes('/api/spools')) {
      spoolReads++
      return spoolReads > 1 && failRefresh ? response({}, 503) : response([
        makeSpool({ id: 1, code: 'FIL-0001', purchase_price: '20' }),
        makeSpool({ id: 2, code: 'FIL-0002', purchase_price: '20', status: spoolReads > 1 ? 'ARCHIVED' : 'OPEN' }),
      ])
    }
    return response(job)
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[mode === 'create' ? '/prints/new' : '/prints/42/edit']}><Routes>
    <Route path="/prints/new" element={<NewPrintJobPage />} /><Route path="/prints/:id/edit" element={<EditPrintJobPage />} />
    <Route path="/prints" element={<p>Saved destination</p>} />
  </Routes></MemoryRouter></QueryClientProvider>)
  await screen.findByLabelText('Print Name')
  if (mode === 'create') {
    fireEvent.change(screen.getByLabelText('Print Name'), { target: { value: job.name } })
    fireEvent.change(screen.getByLabelText('Spool'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Estimated Weight'), { target: { value: '10' } })
    fireEvent.click(screen.getByRole('button', { name: '+ Add Spool' }))
    fireEvent.change(screen.getAllByLabelText('Spool')[1], { target: { value: '2' } })
    fireEvent.change(screen.getAllByLabelText('Estimated Weight')[1], { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Printer'), { target: { value: job.printer_name } })
    fireEvent.change(screen.getByLabelText('Notes'), { target: { value: job.notes } })
    fireEvent.change(screen.getByLabelText('Hours'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Minutes'), { target: { value: '5' } })
  }
  const button = () => screen.getByRole('button', { name: mode === 'create' ? 'Create Print' : 'Save Changes' })
  return { mutation, button, spoolReads: () => spoolReads, client }
}

function expectPreserved() {
  expect(screen.getByLabelText('Print Name')).toHaveValue('Case')
  expect(screen.getByLabelText('Printer')).toHaveValue('A1')
  expect(screen.getByLabelText('Notes')).toHaveValue('Keep notes')
  expect(screen.getByLabelText('Hours')).toHaveValue(1)
  expect(screen.getByLabelText('Minutes')).toHaveValue(5)
  expect(screen.getAllByLabelText(/^Spool$/)[0]).toHaveValue('1')
  expect(screen.getAllByLabelText(/^Spool$/)[1]).toHaveValue('2')
  expect(screen.getAllByLabelText(/^Estimated Weight/)[0]).toHaveValue(10)
  expect(screen.getAllByLabelText(/^Estimated Weight/)[1]).toHaveValue(20)
  expect(screen.getByTestId('estimated-print-cost-EUR')).toHaveTextContent('0.60')
  expect(screen.queryByText('Saved destination')).not.toBeInTheDocument()
  expect(screen.queryByText(/INTERNAL SQL/)).not.toBeInTheDocument()
}

beforeEach(async () => { await i18n.changeLanguage('en') })
afterEach(() => vi.unstubAllGlobals())

describe.each(['create', 'edit'] as const)('%s Print save', mode => {
  it('navigates only after confirmed success', async () => {
    const { button, mutation } = await setup(mode, async () => response(job))
    fireEvent.click(button())
    expect(await screen.findByText('Saved destination')).toBeVisible()
    expect(mutation).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['name', ['name'], 'Print Name', 0, 'string_too_short', 'Enter a value for this field.'],
    ['duration', ['estimated_time_minutes'], 'Hours', 0, 'greater_than', 'Enter a value greater than zero.'],
    ['first spool weight', ['spools', 0, 'estimated_weight_g'], 'Estimated Weight', 0, 'greater_than', 'Enter a value greater than zero.'],
    ['second spool weight', ['spools', 1, 'estimated_weight_g'], 'Estimated Weight', 1, 'decimal_max_places', 'Use at most 3 decimal places.'],
    ['second spool selection', ['spools', 1, 'spool_id'], 'Spool', 1, 'int_parsing', 'Select a valid spool.'],
  ] as const)('maps %s, focuses, preserves values and clears only the corrected field', async (_name, loc, label, index, type, message) => {
    const { button, mutation } = await setup(mode, async () => response(issue([...loc], type), 422))
    fireEvent.click(button())
    expect(await screen.findByRole('alert')).toHaveTextContent('Correct the highlighted fields')
    const fields = screen.getAllByLabelText(new RegExp(`^${label}`))
    const field = fields[index]
    expect(field).toHaveAttribute('aria-invalid', 'true')
    expect(field).toHaveAccessibleDescription(message)
    await waitFor(() => expect(field).toHaveFocus())
    if (index === 1) expect(fields[0]).toHaveAttribute('aria-invalid', 'false')
    expectPreserved()
    fireEvent.change(field, { target: { value: label === 'Print Name' ? 'Corrected' : label === 'Spool' ? '1' : '30' } })
    expect(field).toHaveAttribute('aria-invalid', 'false')
    expect(field).not.toHaveAttribute('aria-describedby')
    if (label !== 'Spool') {
      mutation.mockResolvedValueOnce(response(job))
      fireEvent.click(button())
      expect(await screen.findByText('Saved destination')).toBeVisible()
    }
  })

  it.each([
    ['unknown validation', () => response(issue(['unknown', 'name']), 422), 'Some values were rejected'],
    ['malformed validation', () => response({ detail: [null, 7, {}] }, 422), 'Some values were rejected'],
    ['400', () => response({ detail: 'INTERNAL SQL' }, 400), 'Some values were rejected'],
    ['404', () => response({ detail: { code: 'print_not_found' } }, 404), 'This print no longer exists'],
    ['409', () => response({ detail: 'INTERNAL SQL' }, 409), 'Review your selections and try again'],
    ['network', () => { throw new TypeError('Failed to fetch') }, 'Could not connect to the server'],
    ['500', () => response({ detail: 'INTERNAL SQL stack trace' }, 500), 'An error occurred while saving'],
    ['malformed success', () => response({}), 'The server did not confirm the save'],
    ['invalid JSON', () => ({ ok: true, status: 200, json: () => Promise.reject(new SyntaxError('JSON')) }) as Response, 'The server did not confirm the save'],
  ])('handles %s safely and supports retry', async (_name, result, message) => {
    const { button, mutation } = await setup(mode, async () => result())
    fireEvent.click(button())
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(message)
    await waitFor(() => expect(alert).toHaveFocus())
    expect(document.querySelector('[aria-invalid="true"]')).toBeNull()
    expectPreserved()
    mutation.mockResolvedValueOnce(response(job))
    fireEvent.click(button())
    expect(await screen.findByText('Saved destination')).toBeVisible()
  })

  it.each([false, true])('refreshes conflict availability without losing input (refresh failure: %s)', async failRefresh => {
    const { button, spoolReads } = await setup(mode, async () => response({ detail: { code: 'spool_archived', spool_id: 2 } }, 409), failRefresh)
    fireEvent.click(button())
    expect(await screen.findByRole('alert')).toHaveTextContent('This spool is archived')
    await waitFor(() => expect(spoolReads()).toBe(2))
    expect(screen.getAllByLabelText(/^Spool$/)[1]).toHaveAccessibleDescription('This spool is archived. Select another spool and try again.')
    expectPreserved()
    if (!failRefresh) expect(screen.getByText(/ARCHIVED/)).toBeVisible()
  })

  it('blocks rapid repeated submits and disables fields while saving', async () => {
    let resolve!: (r: Response) => void
    const { button, mutation } = await setup(mode, () => new Promise(r => { resolve = r }))
    const form = button().closest('form')!
    fireEvent.submit(form)
    fireEvent.submit(form)
    await waitFor(() => expect(mutation).toHaveBeenCalledTimes(1))
    expect(screen.getByRole('button', { name: 'Saving...' })).toBeDisabled()
    expect(screen.getByLabelText('Minutes')).toBeDisabled()
    expect(screen.getByLabelText('Notes')).toBeDisabled()
    expect(screen.getAllByRole('button', { name: 'Remove' })[0]).toBeDisabled()
    resolve(response(job))
    expect(await screen.findByText('Saved destination')).toBeVisible()
  })
})

it('keeps nested errors on their stable row when another spool is removed', async () => {
  const { button } = await setup('create', async () => response(issue(['spools', 1, 'estimated_weight_g']), 422))
  fireEvent.click(button())
  await screen.findByRole('alert')
  fireEvent.click(screen.getAllByRole('button', { name: 'Remove' })[0])
  expect(screen.getByLabelText(/^Estimated Weight/)).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByLabelText(/^Spool$/)).toHaveValue('2')
})

it('keeps the selected spool ID visible when it disappears during conflict refresh', async () => {
  const { button, client } = await setup('create', async () => response({ detail: { code: 'spool_not_found', spool_id: 2 } }, 404))
  fireEvent.click(button())
  await screen.findByRole('alert')
  act(() => { client.setQueryData(['spools'], [makeSpool({ id: 1 })]) })
  expect(screen.getAllByLabelText(/^Spool$/)[1]).toHaveValue('2')
  expect(await screen.findByRole('option', { name: 'Spool #2' })).toBeVisible()
  expect(screen.getAllByLabelText(/^Spool$/)[1]).toHaveAttribute('aria-invalid', 'true')
})

it('renders Portuguese errors and loading without translating entity values', async () => {
  const { button } = await setup('create', async () => response(issue(['name']), 422))
  fireEvent.click(button())
  await screen.findByRole('alert')
  await act(() => i18n.changeLanguage('pt-BR'))
  expect(screen.getByRole('alert')).toHaveTextContent('Não foi possível salvar a impressão.')
  expect(screen.getByRole('alert')).toHaveTextContent('Corrija os campos destacados')
  expect(screen.getByLabelText(/^Nome da Impressão/)).toHaveValue('Case')
  const user = userEvent.setup()
  await user.type(screen.getByLabelText(/^Nome da Impressão/), ' corrigido')
  expect(screen.getByLabelText(/^Nome da Impressão/)).toHaveAttribute('aria-invalid', 'false')
})
