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
    await user.type(screen.getByLabelText('Horas'), '4')
    await user.type(screen.getByLabelText('Minutos'), '30')
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
    await user.type(screen.getByLabelText('Horas'), '26')
    await user.type(screen.getByLabelText('Minutos'), '30')
    await user.click(screen.getByRole('button', { name: 'Criar Impressão' }))
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({ estimated_time_minutes: 1590, spools: [{ spool_id: 3, estimated_weight_g: null }] }))
  })

  it('does not offer archived spools for a new job', () => {
    const archived = makeSpool({ id: 4, code: 'FIL-ARCHIVED', status: 'ARCHIVED' })
    render(<PrintJobForm isSubmitting={false} mode="create" onCancel={vi.fn()} onSubmit={vi.fn()} spools={[archived]} submitError={null} />)
    expect(screen.queryByRole('option', { name: /FIL-ARCHIVED/ })).not.toBeInTheDocument()
  })

  it('previews a spool cost live and recalculates for weight and spool changes', async () => {
    const first = makeSpool({ id: 10, code: 'FIL-0010', purchase_price: '20.00', initial_filament_weight_g: '1000', currency: 'EUR' })
    const second = makeSpool({ id: 11, code: 'FIL-0011', purchase_price: '40.00', initial_filament_weight_g: '1000', currency: 'EUR' })
    const unavailable = makeSpool({ id: 12, code: 'FIL-0012', purchase_price: null, currency: 'EUR' })
    render(<PrintJobForm isSubmitting={false} mode="create" onCancel={vi.fn()} onSubmit={vi.fn()} spools={[first, second, unavailable]} submitError={null} />)
    const user = userEvent.setup()
    const cost = screen.getByTestId('estimated-cost-1')
    const weight = screen.getByLabelText(/^Peso Estimado/)

    expect(cost).toHaveTextContent('—')
    await user.selectOptions(screen.getByLabelText('Spool'), '10')
    await user.type(weight, '100')
    expect(cost).toHaveTextContent(/€\s*2,00/)

    await user.clear(weight)
    await user.type(weight, '200')
    expect(cost).toHaveTextContent(/€\s*4,00/)

    await user.selectOptions(screen.getByLabelText('Spool'), '11')
    expect(cost).toHaveTextContent(/€\s*8,00/)

    await user.clear(weight)
    await user.type(weight, '0')
    expect(cost).toHaveTextContent(/€\s*0,00/)

    await user.selectOptions(screen.getByLabelText('Spool'), '12')
    expect(cost).toHaveTextContent('Custo indisponível')
  })

  it('adds and removes same-currency spool costs in the live print total', async () => {
    const first = makeSpool({ id: 20, code: 'FIL-0020', purchase_price: '21', currency: 'EUR' })
    const second = makeSpool({ id: 21, code: 'FIL-0021', purchase_price: '23', currency: 'EUR' })
    render(<PrintJobForm isSubmitting={false} mode="create" onCancel={vi.fn()} onSubmit={vi.fn()} spools={[first, second]} submitError={null} />)
    const user = userEvent.setup()

    await user.selectOptions(screen.getByLabelText('Spool'), '20')
    await user.type(screen.getByLabelText(/^Peso Estimado/), '120')
    await user.click(screen.getByRole('button', { name: '+ Adicionar Spool' }))
    const spoolInputs = screen.getAllByLabelText('Spool')
    const weightInputs = screen.getAllByLabelText(/^Peso Estimado/)
    await user.selectOptions(spoolInputs[1], '21')
    await user.type(weightInputs[1], '80')

    expect(screen.getByTestId('estimated-cost-1')).toHaveTextContent(/€\s*2,52/)
    expect(screen.getByTestId('estimated-cost-2')).toHaveTextContent(/€\s*1,84/)
    expect(screen.getByTestId('estimated-print-cost-EUR')).toHaveTextContent(/€\s*4,36/)

    await user.click(screen.getAllByRole('button', { name: 'Remover' })[1])
    expect(screen.queryByTestId('estimated-cost-2')).not.toBeInTheDocument()
    expect(screen.getByTestId('estimated-print-cost-EUR')).toHaveTextContent(/€\s*2,52/)
  })

  it('keeps currency totals separate and flags partial unavailable costs', async () => {
    const eur = makeSpool({ id: 30, code: 'FIL-0030', purchase_price: '21', currency: 'EUR' })
    const usd = makeSpool({ id: 31, code: 'FIL-0031', purchase_price: '23', currency: 'USD' })
    const unknown = makeSpool({ id: 32, code: 'FIL-0032', purchase_price: null, currency: 'EUR' })
    render(<PrintJobForm isSubmitting={false} mode="create" onCancel={vi.fn()} onSubmit={vi.fn()} spools={[eur, usd, unknown]} submitError={null} />)
    const user = userEvent.setup()

    await user.selectOptions(screen.getByLabelText('Spool'), '30')
    await user.type(screen.getByLabelText(/^Peso Estimado/), '120')
    await user.click(screen.getByRole('button', { name: '+ Adicionar Spool' }))
    await user.click(screen.getByRole('button', { name: '+ Adicionar Spool' }))
    const spoolInputs = screen.getAllByLabelText('Spool')
    const weightInputs = screen.getAllByLabelText(/^Peso Estimado/)
    await user.selectOptions(spoolInputs[1], '31')
    await user.type(weightInputs[1], '80')
    await user.selectOptions(spoolInputs[2], '32')
    await user.type(weightInputs[2], '100')

    expect(screen.getByTestId('estimated-print-cost-EUR')).toHaveTextContent(/€\s*2,52/)
    expect(screen.getByTestId('estimated-print-cost-USD')).toHaveTextContent(/US\$\s*1,84/)
    expect(screen.getByTestId('estimated-print-cost-summary')).toHaveTextContent('+ 1 spool com custo indisponível')
    expect(screen.getByTestId('estimated-print-cost-summary')).not.toHaveTextContent('4,36')
  })

  it('shows an existing planned estimate immediately in edit mode and localizes the preview', async () => {
    await i18n.changeLanguage('en')
    const spool = makeSpool({ id: 40, code: 'FIL-0040', purchase_price: '20', currency: 'USD' })
    render(<PrintJobForm initialValues={{ name: 'Existing plan', spools: [{ spool_id: 40, estimated_weight_g: '100' }], estimated_time_minutes: null, printer_name: null, notes: null }} isSubmitting={false} mode="edit" onCancel={vi.fn()} onSubmit={vi.fn()} spools={[spool]} submitError={null} />)

    expect(screen.getByText('Estimated cost')).toBeVisible()
    expect(screen.getByText('Estimated print cost')).toBeVisible()
    expect(screen.getByTestId('estimated-cost-1')).toHaveTextContent(/\$2\.00/)
    expect(screen.getByTestId('estimated-print-cost-USD')).toHaveTextContent(/\$2\.00/)
  })
})
