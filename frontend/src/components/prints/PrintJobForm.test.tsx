import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../../i18n'
import { makeSpool } from '../../test/spoolFixture'
import { PrintJobForm } from './PrintJobForm'

describe('PrintJobForm', () => {
  beforeEach(async () => { await i18n.changeLanguage('pt-BR') })

  it('submits a spool-link payload without operational fields', async () => {
    const submit = vi.fn()
    const spool = makeSpool({ id: 2, display_name: 'PLA Preto Principal', code: 'FIL-0042', status: 'LOW', current_filament_weight_g: '50', remaining_percent: 5 })
    render(<PrintJobForm isSubmitting={false} mode="create" onCancel={vi.fn()} onSubmit={submit} spools={[spool]} submitError={null} />)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Nome da Impressão'), 'Case ESP32')
    await user.selectOptions(screen.getByLabelText('Spool'), '2')
    await user.type(screen.getByLabelText(/^Peso Estimado/), '124')
    await user.type(screen.getByLabelText('Hours'), '4')
    await user.type(screen.getByLabelText('Minutes'), '30')
    await user.click(screen.getByRole('button', { name: 'Criar Impressão' }))
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({ name: 'Case ESP32', spools: [{ spool_id: 2, estimated_weight_g: 124 }], estimated_time_minutes: 270 }))
    expect(submit.mock.calls[0][0]).not.toHaveProperty('status')
    expect(submit.mock.calls[0][0]).not.toHaveProperty('actual_weight_g')
  })

  it('allows durations over one day and keeps optional numeric fields null', async () => {
    const submit = vi.fn()
    const spool = makeSpool({ id: 3, code: 'FIL-0003', display_name: null })
    render(<PrintJobForm isSubmitting={false} mode="create" onCancel={vi.fn()} onSubmit={submit} spools={[spool]} submitError={null} />)
    const user = userEvent.setup()
    expect(screen.getByRole('option', { name: /FIL-0003/ })).toBeVisible()
    await user.type(screen.getByLabelText('Nome da Impressão'), 'Long print')
    await user.selectOptions(screen.getByLabelText('Spool'), '3')
    await user.type(screen.getByLabelText('Hours'), '26')
    await user.type(screen.getByLabelText('Minutes'), '30')
    await user.click(screen.getByRole('button', { name: 'Criar Impressão' }))
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({ estimated_time_minutes: 1590, spools: [{ spool_id: 3, estimated_weight_g: null }] }))
  })

  it('does not offer archived spools for a new job', () => {
    const archived = makeSpool({ id: 4, code: 'FIL-ARCHIVED', status: 'ARCHIVED' })
    render(<PrintJobForm isSubmitting={false} mode="create" onCancel={vi.fn()} onSubmit={vi.fn()} spools={[archived]} submitError={null} />)
    expect(screen.queryByRole('option', { name: /FIL-ARCHIVED/ })).not.toBeInTheDocument()
  })
})
