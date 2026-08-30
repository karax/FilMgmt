import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import {
  THEME_STORAGE_KEY,
  ThemeProvider,
} from './components/theme/ThemeProvider'
import { spoolsQueryKey } from './hooks/useSpools'
import { routes } from './router'

function renderRoute(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const user = userEvent.setup()
  const queryClient = new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity } },
  })
  queryClient.setQueryData(spoolsQueryKey, [])

  render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <RouterProvider router={router} />
      </ThemeProvider>
    </QueryClientProvider>,
  )

  return { router, user }
}

describe('application layout', () => {
  it('renders the product identity and primary navigation', () => {
    renderRoute('/')

    expect(
      screen.getByRole('link', { name: 'Filament Command Center home' }),
    ).toBeInTheDocument()
    for (const label of [
      'Dashboard',
      'Inventory',
      'Prints',
      'Advisor',
      'Analytics',
      'Settings',
    ]) {
      expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
    }
  })

  it('renders the functional dashboard at the root route', () => {
    renderRoute('/')

    expect(
      screen.getByRole('heading', { level: 2, name: 'Inventory overview' }),
    ).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Total Spools' })).toBeVisible()
  })

  it('renders the functional inventory at /inventory', () => {
    renderRoute('/inventory')

    expect(
      screen.getByRole('heading', { level: 2, name: 'Inventory' }),
    ).toBeVisible()
    expect(screen.getByText('Manage and track your filament spools.')).toBeVisible()
    expect(screen.getByText('Your filament inventory is empty.')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Add Spool' })).toHaveAttribute(
      'href',
      '/inventory/new',
    )
  })

  it('renders the new spool route inside the main layout', () => {
    renderRoute('/inventory/new')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('New Spool')
    expect(screen.getByRole('heading', { level: 2, name: 'New Spool' })).toBeVisible()
  })

  it.each([
    ['/prints', 'Prints', 'Track your print jobs.'],
    ['/advisor', 'Filament Advisor', 'Find the best spool for your next print.'],
    [
      '/analytics',
      'Analytics',
      'Review filament usage and printing statistics.',
    ],
    ['/settings', 'Settings', 'Configure Filament Command Center.'],
  ])('renders the placeholder for %s', (path, title, description) => {
    renderRoute(path)

    expect(screen.getByRole('heading', { level: 2, name: title })).toBeVisible()
    expect(screen.getByText(description)).toBeVisible()
  })

  it('marks the current navigation item as active', () => {
    renderRoute('/inventory')

    expect(screen.getByRole('link', { name: 'Inventory' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('shows the route title in the header', () => {
    renderRoute('/analytics')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Analytics',
    )
  })
})

describe('theme preferences', () => {
  it('defaults to the system theme preference', () => {
    renderRoute('/')

    expect(
      screen.getByRole('combobox', { name: 'Theme preference' }),
    ).toHaveValue('system')
  })

  it('applies and persists a manual dark theme', async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light')
    const { user } = renderRoute('/')

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Theme preference' }),
      'dark',
    )

    await waitFor(() =>
      expect(document.documentElement).toHaveClass('dark'),
    )
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('loads a persisted theme preference', async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    renderRoute('/')

    await waitFor(() =>
      expect(document.documentElement).toHaveClass('dark'),
    )
    expect(
      screen.getByRole('combobox', { name: 'Theme preference' }),
    ).toHaveValue('dark')
  })
})

describe('mobile navigation', () => {
  it('opens and closes the navigation drawer', async () => {
    const { user } = renderRoute('/')

    await user.click(
      screen.getByRole('button', { name: 'Open navigation menu' }),
    )
    const drawer = screen.getByRole('dialog', { name: 'Mobile navigation' })
    expect(drawer).toBeVisible()

    await user.click(
      within(drawer).getByRole('button', { name: 'Close navigation menu' }),
    )
    expect(
      screen.queryByRole('dialog', { name: 'Mobile navigation' }),
    ).not.toBeInTheDocument()
  })

  it('closes the drawer with Escape and returns focus to the menu button', async () => {
    const { user } = renderRoute('/')
    const menuButton = screen.getByRole('button', {
      name: 'Open navigation menu',
    })

    await user.click(menuButton)
    expect(screen.getByRole('dialog', { name: 'Mobile navigation' })).toBeVisible()

    await user.keyboard('{Escape}')

    expect(
      screen.queryByRole('dialog', { name: 'Mobile navigation' }),
    ).not.toBeInTheDocument()
    expect(menuButton).toHaveFocus()
  })

  it('closes after mobile navigation and updates the page', async () => {
    const { user } = renderRoute('/')

    await user.click(
      screen.getByRole('button', { name: 'Open navigation menu' }),
    )
    const drawer = screen.getByRole('dialog', { name: 'Mobile navigation' })
    await user.click(within(drawer).getByRole('link', { name: 'Inventory' }))

    expect(
      screen.queryByRole('dialog', { name: 'Mobile navigation' }),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: 'Inventory' }),
    ).toBeVisible()
  })
})
