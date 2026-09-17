import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import i18n, { LANGUAGE_STORAGE_KEY, resolveStoredLanguage } from './index'
import { en } from './locales/en'
import { ptBR } from './locales/pt-BR'
import { SpoolStatusBadge } from '../components/spool/SpoolStatusBadge'
import { SettingsPage } from '../pages/SettingsPage'

describe('internationalization', () => {
  beforeEach(async () => {
    window.localStorage.clear()
    await i18n.changeLanguage('pt-BR')
  })

  it('uses Portuguese as the default application language and persists changes', async () => {
    render(<SettingsPage />)
    expect(screen.getByRole('heading', { name: 'Configurações' })).toBeVisible()
    const user = userEvent.setup()
    await user.selectOptions(screen.getByRole('combobox'), 'en')
    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeVisible()
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('en')
    expect(document.documentElement.lang).toBe('en')

    await user.selectOptions(screen.getByRole('combobox'), 'pt-BR')
    expect(await screen.findByRole('heading', { name: 'Configurações' })).toBeVisible()
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('pt-BR')
    expect(document.documentElement.lang).toBe('pt-BR')
  })

  it('falls back safely when the saved language is unknown', () => {
    expect(resolveStoredLanguage(null)).toBe('pt-BR')
    expect(resolveStoredLanguage('fr')).toBe('pt-BR')
    expect(resolveStoredLanguage('en')).toBe('en')
  })

  it('keeps the English and Portuguese translation key sets equivalent', () => {
    const paths = (value: unknown, prefix = ''): string[] => {
      if (!value || typeof value !== 'object') return [prefix]
      return Object.entries(value as Record<string, unknown>).flatMap(([key, nested]) => paths(nested, prefix ? `${prefix}.${key}` : key))
    }

    expect(paths(ptBR).sort()).toEqual(paths(en).sort())
  })

  it('translates persisted status values only in the interface', async () => {
    const { rerender } = render(<SpoolStatusBadge status="LOW" />)
    expect(screen.getByText('Baixo')).toBeVisible()

    await i18n.changeLanguage('en')
    rerender(<SpoolStatusBadge status="LOW" />)
    expect(screen.getByText('Low')).toBeVisible()
  })
})
