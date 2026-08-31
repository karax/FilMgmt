import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import i18n, { LANGUAGE_STORAGE_KEY } from './index'
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
  })

  it('translates persisted status values only in the interface', async () => {
    const { rerender } = render(<SpoolStatusBadge status="LOW" />)
    expect(screen.getByText('Baixo')).toBeVisible()

    await i18n.changeLanguage('en')
    rerender(<SpoolStatusBadge status="LOW" />)
    expect(screen.getByText('Low')).toBeVisible()
  })
})
