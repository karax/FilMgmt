import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import { makeSpool } from '../test/spoolFixture'
import type { Material } from '../types/spool'
import { NewSpoolPage } from './NewSpoolPage'

const manufacturer = {
  id: 1,
  name: 'eSUN',
  website: null,
  created_at: '2026-08-01T12:00:00Z',
  updated_at: '2026-08-01T12:00:00Z',
}
const material: Material = {
  id: 2,
  name: 'PLA+',
  category: 'PLA',
  default_nozzle_temp_min: null,
  default_nozzle_temp_max: null,
  default_bed_temp_min: null,
  default_bed_temp_max: null,
  density_g_cm3: null,
  notes: null,
  created_at: '2026-08-01T12:00:00Z',
  updated_at: '2026-08-01T12:00:00Z',
}
const petgMaterial: Material = {
  ...material,
  id: 4,
  name: 'PETG',
  category: 'PETG',
  default_nozzle_temp_min: 220,
  default_nozzle_temp_max: 250,
  default_bed_temp_min: 70,
  default_bed_temp_max: 85,
}
const plaMaterial: Material = {
  ...material,
  id: 2,
  name: 'PLA',
  default_nozzle_temp_min: 190,
  default_nozzle_temp_max: 220,
  default_bed_temp_min: 45,
  default_bed_temp_max: 60,
}
function response(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(data),
  } as unknown as Response
}

function mockCatalogs({
  manufacturers = [manufacturer],
  materials = [material],
  post = response(makeSpool({ code: 'FIL-0042' }), 201),
}: {
  manufacturers?: typeof manufacturer[]
  materials?: Material[]
  post?: Response
} = {}) {
  vi.mocked(fetch).mockImplementation((input, init) => {
    const url = String(input)
    if (url.endsWith('/manufacturers')) return Promise.resolve(response(manufacturers))
    if (url.endsWith('/materials')) return Promise.resolve(response(materials))
    if (url.endsWith('/spools') && init?.method === 'POST') return Promise.resolve(post)
    throw new Error(`Unexpected request: ${url}`)
  })
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [
      { path: '/inventory/new', element: <NewSpoolPage /> },
      { path: '/inventory', element: <p>Inventory destination</p> },
    ],
    { initialEntries: ['/inventory/new'] },
  )
  render(<QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider>)
  return { queryClient, router, user: userEvent.setup() }
}

async function fillRequired(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(screen.getByRole('combobox', { name: /Manufacturer/ }), '1')
  await user.selectOptions(screen.getByRole('combobox', { name: /Material/ }), '2')
  await user.type(screen.getByRole('textbox', { name: /Color Name/ }), 'Black')
}

describe('NewSpoolPage', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn()))
  afterEach(() => vi.unstubAllGlobals())

  it('shows a skeleton while catalog dependencies are loading', () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => undefined))
    renderPage()
    expect(screen.getByRole('status', { name: 'Loading spool form' })).toBeVisible()
    expect(screen.queryByLabelText('Manufacturer')).not.toBeInTheDocument()
  })

  it('loads manufacturer and material options from the API', async () => {
    mockCatalogs()
    renderPage()
    expect(await screen.findByRole('option', { name: 'eSUN' })).toBeVisible()
    expect(screen.getByRole('option', { name: 'PLA+' })).toBeVisible()
  })

  it('links to Catalogs when required catalog data is empty', async () => {
    mockCatalogs({ manufacturers: [], materials: [] })
    renderPage()
    expect(await screen.findByText('No manufacturers available. Create a manufacturer first.')).toBeVisible()
    expect(screen.getByText('No materials available. Create a material first.')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Open Catalogs' })).toHaveAttribute('href', '/settings/catalogs')
    expect(screen.getByRole('button', { name: 'Create Spool' })).toBeDisabled()
  })

  it('applies selected material defaults while keeping print-setting inputs editable', async () => {
    mockCatalogs({ materials: [plaMaterial] })
    const { user } = renderPage()
    await screen.findByLabelText('Material')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Material' }), '2')

    expect(screen.getByRole('spinbutton', { name: /^Nozzle Temp Min/ })).toHaveValue(190)
    expect(screen.getByRole('spinbutton', { name: /^Nozzle Temp Max/ })).toHaveValue(220)
    expect(screen.getByRole('spinbutton', { name: /^Bed Temp Min/ })).toHaveValue(45)
    expect(screen.getByRole('spinbutton', { name: /^Bed Temp Max/ })).toHaveValue(60)
    expect(screen.getByText('Defaults from PLA')).toBeVisible()

    const nozzleMin = screen.getByRole('spinbutton', { name: /^Nozzle Temp Min/ })
    await user.clear(nozzleMin)
    await user.type(nozzleMin, '205')
    expect(nozzleMin).toHaveValue(205)
  })

  it('replaces unchanged defaults when the material changes', async () => {
    mockCatalogs({ materials: [plaMaterial, petgMaterial] })
    const { user } = renderPage()
    await screen.findByLabelText('Material')
    const selector = screen.getByRole('combobox', { name: 'Material' })
    await user.selectOptions(selector, '2')
    await user.selectOptions(selector, '4')

    expect(screen.getByRole('spinbutton', { name: /^Nozzle Temp Min/ })).toHaveValue(220)
    expect(screen.getByRole('spinbutton', { name: /^Bed Temp Max/ })).toHaveValue(85)
    expect(screen.getByText('Defaults from PETG')).toBeVisible()
  })

  it('preserves custom print settings after a material change until defaults are explicitly applied', async () => {
    mockCatalogs({ materials: [plaMaterial, petgMaterial] })
    const { user } = renderPage()
    await screen.findByLabelText('Material')
    const selector = screen.getByRole('combobox', { name: 'Material' })
    await user.selectOptions(selector, '2')
    const nozzleMin = screen.getByRole('spinbutton', { name: /^Nozzle Temp Min/ })
    await user.clear(nozzleMin)
    await user.type(nozzleMin, '205')
    await user.selectOptions(selector, '4')

    expect(nozzleMin).toHaveValue(205)
    expect(screen.getByText('Material changed. Existing custom print settings were preserved.')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Apply Material Defaults' }))
    expect(nozzleMin).toHaveValue(220)
    expect(screen.getByRole('spinbutton', { name: /^Bed Temp Max/ })).toHaveValue(85)
  })

  it('applies partial defaults without creating zero or invalid temperatures', async () => {
    mockCatalogs({ materials: [{ ...petgMaterial, default_bed_temp_min: null, default_bed_temp_max: null }] })
    const { user } = renderPage()
    await screen.findByLabelText('Material')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Material' }), '4')

    expect(screen.getByRole('spinbutton', { name: /^Nozzle Temp Min/ })).toHaveValue(220)
    expect(screen.getByRole('spinbutton', { name: /^Bed Temp Min/ })).toHaveValue(null)
    expect(screen.getByRole('spinbutton', { name: /^Bed Temp Max/ })).toHaveValue(null)
  })

  it('blocks required fields and invalid weight ranges before posting', async () => {
    mockCatalogs()
    const { user } = renderPage()
    await screen.findByLabelText('Manufacturer')
    await user.click(screen.getByRole('button', { name: 'Create Spool' }))
    expect(screen.getByText('Select a manufacturer.')).toBeVisible()
    expect(screen.getByText('Select a material.')).toBeVisible()
    expect(screen.getByText('Color name is required.')).toBeVisible()

    await fillRequired(user)
    const currentWeight = screen.getByRole('spinbutton', { name: /Current Filament Weight/ })
    await user.clear(currentWeight)
    await user.type(currentWeight, '1200')
    await user.click(screen.getByRole('button', { name: 'Create Spool' }))
    expect(screen.getByText('Current weight cannot exceed initial weight.')).toBeVisible()
    expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
  }, 10_000)

  it('rejects filament weights above 2,000 g and preserves the entered values', async () => {
    mockCatalogs()
    const { user } = renderPage()
    await screen.findByLabelText('Manufacturer')
    await fillRequired(user)
    const initialWeight = screen.getByRole('spinbutton', { name: /Initial Filament Weight/ })
    const currentWeight = screen.getByRole('spinbutton', { name: /Current Filament Weight/ })
    await user.clear(initialWeight)
    await user.type(initialWeight, '2500')
    await user.clear(currentWeight)
    await user.type(currentWeight, '2000.01')
    await user.click(screen.getByRole('button', { name: 'Create Spool' }))

    expect(screen.getAllByText('Maximum filament weight per spool is 2,000 g.')).toHaveLength(2)
    expect(initialWeight).toHaveValue(2500)
    expect(currentWeight).toHaveValue(2000.01)
    expect(initialWeight).toHaveAttribute('max', '2000')
    expect(currentWeight).toHaveAttribute('max', '2000')
    expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
  })

  it('accepts the exact weight and price limits', async () => {
    mockCatalogs()
    const { user } = renderPage()
    await screen.findByLabelText('Manufacturer')
    await fillRequired(user)
    const initialWeight = screen.getByRole('spinbutton', { name: /Initial Filament Weight/ })
    const currentWeight = screen.getByRole('spinbutton', { name: /Current Filament Weight/ })
    const purchasePrice = screen.getByRole('spinbutton', { name: /Purchase Price/ })
    await user.clear(initialWeight)
    await user.type(initialWeight, '2000')
    await user.clear(currentWeight)
    await user.type(currentWeight, '2000')
    await user.type(purchasePrice, '100')
    await user.click(screen.getByRole('button', { name: 'Create Spool' }))

    await waitFor(() => expect(screen.getByText('Inventory destination')).toBeVisible())
    const postCall = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'POST')
    const payload = JSON.parse(String(postCall?.[1]?.body)) as Record<string, unknown>
    expect(payload).toMatchObject({
      initial_filament_weight_g: 2000,
      current_filament_weight_g: 2000,
      purchase_price: 100,
      store_name: null,
    })
    expect(purchasePrice).toHaveAttribute('max', '100')
  })

  it('posts the automatically generated display name', async () => {
    mockCatalogs()
    const { user } = renderPage()
    await screen.findByLabelText('Manufacturer')
    await fillRequired(user)
    expect(screen.getByRole('textbox', { name: /Spool Name/ })).toHaveValue('eSUN Black')

    await user.click(screen.getByRole('button', { name: 'Create Spool' }))

    await waitFor(() => expect(screen.getByText('Inventory destination')).toBeVisible())
    const postCall = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'POST')
    const payload = JSON.parse(String(postCall?.[1]?.body)) as Record<string, unknown>
    expect(payload.display_name).toBe('eSUN Black')
  })

  it('rejects a price above 100 without sending or truncating it', async () => {
    mockCatalogs()
    const { user } = renderPage()
    await screen.findByLabelText('Manufacturer')
    await fillRequired(user)
    const purchasePrice = screen.getByRole('spinbutton', { name: /Purchase Price/ })
    await user.type(purchasePrice, '150')
    await user.click(screen.getByRole('button', { name: 'Create Spool' }))

    expect(screen.getByText('Maximum allowed price is €100.')).toBeVisible()
    expect(purchasePrice).toHaveValue(150)
    expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
  })

  it('posts only writable fields, invalidates spools, and redirects after success', async () => {
    mockCatalogs()
    const { queryClient, user } = renderPage()
    await screen.findByLabelText('Manufacturer')
    await fillRequired(user)
    const displayName = screen.getByRole('textbox', { name: /Spool Name/ })
    await user.clear(displayName)
    await user.type(displayName, 'PLA Preto Principal')
    await user.type(screen.getByRole('textbox', { name: /Product Name/ }), 'PLA+ HS')
    await user.type(screen.getByRole('textbox', { name: /Store Name/ }), '  Filament World  ')
    await user.click(screen.getByRole('button', { name: 'Create Spool' }))

    await waitFor(() => expect(screen.getByText('Inventory destination')).toBeVisible())
    const postCall = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'POST')
    expect(postCall).toBeDefined()
    const payload = JSON.parse(String(postCall?.[1]?.body)) as Record<string, unknown>
    expect(payload).toMatchObject({ manufacturer_id: 1, material_id: 2, store_name: 'Filament World', display_name: 'PLA Preto Principal', product_name: 'PLA+ HS', color_name: 'Black', status: 'SEALED' })
    expect(payload).not.toHaveProperty('location_id')
    expect(payload).not.toHaveProperty('code')
    expect(payload).not.toHaveProperty('remaining_percent')
    expect(queryClient.isFetching({ queryKey: ['spools'] })).toBe(0)
  })

  it('maps FastAPI 422 field errors, focuses the first field, and preserves values', async () => {
    let resolvePost: ((value: Response) => void) | undefined
    const pendingPost = new Promise<Response>((resolve) => { resolvePost = resolve })
    mockCatalogs({ post: pendingPost as unknown as Response })
    const { user } = renderPage()
    await screen.findByLabelText('Manufacturer')
    await fillRequired(user)
    await user.click(screen.getByRole('button', { name: 'Create Spool' }))
    expect(screen.getByRole('button', { name: 'Creating…' })).toBeDisabled()
    resolvePost?.(response({ detail: [
      { loc: ['body', 'initial_filament_weight_g'], msg: 'Input should be greater than 0' },
      { loc: ['body', 'color_hex'], msg: 'String should match pattern' },
      { loc: ['body', 'purchase_price'], msg: 'Value error, Purchase price cannot exceed 100.' },
    ] }, 422))
    expect(await screen.findByText('Some fields need to be corrected. Review the highlighted fields.')).toBeVisible()
    const initialWeight = screen.getByRole('spinbutton', { name: /Initial Filament Weight/ })
    expect(initialWeight).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getAllByText('Check this value and try again.')[0]).toBeVisible()
    expect(screen.getByLabelText('Color Hex')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('spinbutton', { name: /Purchase Price/ })).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText('Maximum allowed price is €100.')).toBeVisible()
    await waitFor(() => expect(initialWeight).toHaveFocus())
    expect(screen.getByRole('textbox', { name: /Color Name/ })).toHaveValue('Black')
  })

  it('blocks submission when manufacturers are unavailable', async () => {
    mockCatalogs({ manufacturers: [] })
    renderPage()
    expect(await screen.findByText('No manufacturers available. Create a manufacturer first.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Create Spool' })).toBeDisabled()
  })

  it('returns to inventory when Cancel is selected', async () => {
    mockCatalogs()
    const { user } = renderPage()
    await screen.findByLabelText('Manufacturer')
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(await screen.findByText('Inventory destination')).toBeVisible()
  })

  it('shows maximum errors in pt-BR', async () => {
    await i18n.changeLanguage('pt-BR')
    mockCatalogs()
    const { user } = renderPage()
    await screen.findByLabelText('Fabricante')
    const initialWeight = screen.getByRole('spinbutton', { name: /Peso Inicial do Filamento/ })
    const purchasePrice = screen.getByRole('spinbutton', { name: /Preço de Compra/ })
    await user.clear(initialWeight)
    await user.type(initialWeight, '2500')
    await user.type(purchasePrice, '150')
    await user.click(screen.getByRole('button', { name: 'Criar Spool' }))

    expect(screen.getByText('O peso máximo de filamento por spool é 2.000 g.')).toBeVisible()
    expect(screen.getByText('O preço máximo permitido é €100.')).toBeVisible()
    expect(screen.getByRole('textbox', { name: /Nome da Loja/ })).toBeVisible()
  })
})
