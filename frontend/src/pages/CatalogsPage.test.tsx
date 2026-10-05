import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import { CatalogsPage } from './CatalogsPage'

function response(data: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(data) } as unknown as Response
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter><CatalogsPage /></MemoryRouter></QueryClientProvider>)
  return userEvent.setup()
}

describe('CatalogsPage', () => {
  beforeEach(async () => { vi.stubGlobal('fetch', vi.fn()); vi.stubGlobal('confirm', vi.fn(() => true)); await i18n.changeLanguage('en') })
  afterEach(() => vi.unstubAllGlobals())

  it('shows actionable empty states in both catalogs', async () => {
    vi.mocked(fetch).mockResolvedValue(response([]))
    renderPage()
    expect(await screen.findByText('No manufacturers yet.')).toBeVisible()
    expect(screen.getByText('No materials yet.')).toBeVisible()
    expect(screen.getByText(/no separate Location catalog/i)).toBeVisible()
  })

  it('creates a manufacturer and refreshes the list', async () => {
    let manufacturers: unknown[] = []
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = String(input)
      if (url.endsWith('/materials')) return Promise.resolve(response([]))
      if (url.endsWith('/manufacturers') && init?.method === 'POST') { manufacturers = [{ id: 1, name: 'Prusament', website: null, created_at: '', updated_at: '' }]; return Promise.resolve(response(manufacturers[0], 201)) }
      if (url.endsWith('/manufacturers')) return Promise.resolve(response(manufacturers))
      throw new Error(`Unexpected request ${url}`)
    })
    const user = renderPage()
    await user.click((await screen.findAllByRole('button', { name: 'Add manufacturer' }))[0])
    await user.type(screen.getByRole('textbox', { name: 'Name' }), 'Prusament')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Prusament')).toBeVisible()
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(expect.stringContaining('/manufacturers'), expect.objectContaining({ method: 'POST' }))
  })

  it('loads the selected record when switching between open manufacturer editors', async () => {
    vi.mocked(fetch).mockImplementation(input => Promise.resolve(response(String(input).endsWith('/materials') ? [] : [
      { id: 1, name: 'Brand One', website: null },
      { id: 2, name: 'Brand Two', website: null },
    ])))
    const user = renderPage()
    await screen.findByText('Brand One')
    await user.click(screen.getAllByRole('button', { name: 'Edit' })[0])
    expect(screen.getByRole('textbox', { name: 'Name' })).toHaveValue('Brand One')
    await user.click(screen.getAllByRole('button', { name: 'Edit' })[1])
    expect(screen.getByRole('textbox', { name: 'Name' })).toHaveValue('Brand Two')
  })

  it('edits a material and preserves technical fields', async () => {
    const material = { id: 2, name: 'PLA', category: 'PLA', density_g_cm3: '1.240', default_nozzle_temp_min: 190, default_nozzle_temp_max: 220, default_bed_temp_min: 45, default_bed_temp_max: 60, notes: null, created_at: '', updated_at: '' }
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = String(input)
      if (url.endsWith('/manufacturers')) return Promise.resolve(response([]))
      if (url.endsWith('/materials/2') && init?.method === 'PUT') return Promise.resolve(response({ ...material, name: 'PLA Pro' }))
      if (url.endsWith('/materials')) return Promise.resolve(response([material]))
      throw new Error(`Unexpected request ${url}`)
    })
    const user = renderPage()
    await screen.findByText('PLA')
    await user.click(screen.getAllByRole('button', { name: 'Edit' })[0])
    const name = screen.getByRole('textbox', { name: 'Name' })
    await user.clear(name); await user.type(name, 'PLA Pro'); await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalledWith(expect.stringContaining('/materials/2'), expect.objectContaining({ method: 'PUT', body: expect.stringContaining('"density_g_cm3":1.24') })))
  })

  it('explains protected delete conflicts in pt-BR', async () => {
    await i18n.changeLanguage('pt-BR')
    const manufacturer = { id: 1, name: 'eSUN', website: null, created_at: '', updated_at: '' }
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = String(input)
      if (url.endsWith('/materials')) return Promise.resolve(response([]))
      if (url.endsWith('/manufacturers/1') && init?.method === 'DELETE') return Promise.resolve(response({ detail: 'in use' }, 409))
      return Promise.resolve(response([manufacturer]))
    })
    const user = renderPage(); await screen.findByText('eSUN')
    await user.click(screen.getByRole('button', { name: 'Excluir' }))
    expect(await screen.findByText(/está sendo usado por um Spool/)).toBeVisible()
  })
})
