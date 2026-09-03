import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import manual from '../config/manual.json'
import i18n from '../i18n'
import { SettingsPage } from './SettingsPage'

describe('SettingsPage user manual', () => {
  beforeEach(async () => {
    window.localStorage.clear()
    await i18n.changeLanguage('pt-BR')
  })

  it('renders the Portuguese manual card with a real download link', () => {
    render(<SettingsPage />)

    expect(screen.getByRole('heading', { name: 'Manual do usuário' })).toBeVisible()
    expect(screen.getByText('Consulte o guia completo de utilização do Filament Command Center.')).toBeVisible()
    const link = screen.getByRole('link', { name: 'Baixar manual (PDF)' })
    expect(link).toHaveAttribute('href', manual.url)
    expect(link).toHaveAttribute('download', manual.filename)
  })

  it('renders the manual card in English', async () => {
    await i18n.changeLanguage('en')
    render(<SettingsPage />)

    expect(screen.getByRole('heading', { name: 'User manual' })).toBeVisible()
    expect(screen.getByText('View the complete Filament Command Center user guide.')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Download manual (PDF)' })).toBeVisible()
  })

  it('uses an origin-relative URL without local network addresses', () => {
    expect(manual.url).toMatch(/^\/docs\//)
    expect(manual.url).not.toMatch(/https?:|localhost|127\.0\.0\.1|192\.168\.|100\./i)
    expect(manual.filename).toBe('filament-command-center-user-guide.pdf')
  })
})
