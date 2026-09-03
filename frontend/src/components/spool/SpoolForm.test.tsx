import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { Manufacturer, Material } from '../../types/spool'
import { SpoolForm, type SpoolFormProps } from './SpoolForm'

const manufacturer = {
  id: 1,
  name: 'eSUN',
  website: null,
  created_at: '2026-08-01T12:00:00Z',
  updated_at: '2026-08-01T12:00:00Z',
}

const material: Material = {
  id: 2,
  name: 'PLA',
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

const bambuLab: Manufacturer = { ...manufacturer, id: 10, name: 'Bambu Lab' }
const polymaker: Manufacturer = { ...manufacturer, id: 11, name: 'Polymaker' }

function renderForm(props: Partial<SpoolFormProps> = {}) {
  const onSubmit = vi.fn()
  render(
    <SpoolForm
      isSubmitting={false}
      manufacturers={[bambuLab, polymaker]}
      materials={[material]}
      onCancel={vi.fn()}
      onSubmit={onSubmit}
      submitError={null}
      {...props}
    />,
  )
  return { onSubmit, user: userEvent.setup() }
}

describe('SpoolForm display name prefill', () => {
  it('prefills after selecting manufacturer and then entering color', async () => {
    const { user } = renderForm()
    const displayName = screen.getByRole('textbox', { name: /Spool Name/ })

    expect(displayName).toHaveValue('')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Manufacturer' }), '10')
    expect(displayName).toHaveValue('')
    await user.type(screen.getByRole('textbox', { name: /Color Name/ }), 'Preto')

    expect(displayName).toHaveValue('Bambu Lab Preto')
  })

  it('prefills when color is entered before the manufacturer is selected', async () => {
    const { user } = renderForm()
    const displayName = screen.getByRole('textbox', { name: /Spool Name/ })

    await user.type(screen.getByRole('textbox', { name: /Color Name/ }), 'Azul')
    expect(displayName).toHaveValue('')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Manufacturer' }), '11')

    expect(displayName).toHaveValue('Polymaker Azul')
  })

  it('tracks manufacturer and color changes until the name is edited manually', async () => {
    const { user } = renderForm()
    const manufacturerSelect = screen.getByRole('combobox', { name: 'Manufacturer' })
    const colorName = screen.getByRole('textbox', { name: /Color Name/ })
    const displayName = screen.getByRole('textbox', { name: /Spool Name/ })

    await user.selectOptions(manufacturerSelect, '10')
    await user.type(colorName, 'Preto')
    expect(displayName).toHaveValue('Bambu Lab Preto')

    await user.clear(colorName)
    await user.type(colorName, 'Branco')
    expect(displayName).toHaveValue('Bambu Lab Branco')

    await user.selectOptions(manufacturerSelect, '11')
    expect(displayName).toHaveValue('Polymaker Branco')
  })

  it('preserves a custom name through later color and manufacturer changes', async () => {
    const { user } = renderForm()
    const manufacturerSelect = screen.getByRole('combobox', { name: 'Manufacturer' })
    const colorName = screen.getByRole('textbox', { name: /Color Name/ })
    const displayName = screen.getByRole('textbox', { name: /Spool Name/ })

    await user.selectOptions(manufacturerSelect, '10')
    await user.type(colorName, 'Preto')
    await user.clear(displayName)
    await user.type(displayName, 'PLA Preto Principal')

    await user.clear(colorName)
    await user.type(colorName, 'Galaxy Black')
    await user.selectOptions(manufacturerSelect, '11')

    expect(displayName).toHaveValue('PLA Preto Principal')
  })

  it('treats manually clearing the name as a persistent override', async () => {
    const { user } = renderForm()
    const manufacturerSelect = screen.getByRole('combobox', { name: 'Manufacturer' })
    const colorName = screen.getByRole('textbox', { name: /Color Name/ })
    const displayName = screen.getByRole('textbox', { name: /Spool Name/ })

    await user.selectOptions(manufacturerSelect, '10')
    await user.type(colorName, 'Preto')
    await user.clear(displayName)
    await user.clear(colorName)
    await user.type(colorName, 'Branco')
    await user.selectOptions(manufacturerSelect, '11')

    expect(displayName).toHaveValue('')
  })

  it('keeps the name empty until both manufacturer and color exist', async () => {
    const { user } = renderForm()
    const colorName = screen.getByRole('textbox', { name: /Color Name/ })
    const displayName = screen.getByRole('textbox', { name: /Spool Name/ })

    await user.type(colorName, 'Preto')
    expect(displayName).toHaveValue('')
    await user.clear(colorName)
    await user.selectOptions(screen.getByRole('combobox', { name: 'Manufacturer' }), '10')

    expect(displayName).toHaveValue('')
  })

  it('normalizes spaces and excludes material and product name', async () => {
    const spacedManufacturer = { ...bambuLab, name: '  Bambu   Lab  ' }
    const { user } = renderForm({ manufacturers: [spacedManufacturer] })
    const displayName = screen.getByRole('textbox', { name: /Spool Name/ })

    await user.selectOptions(screen.getByRole('combobox', { name: 'Manufacturer' }), '10')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Material' }), '2')
    await user.type(screen.getByRole('textbox', { name: /Product Name/ }), 'PLA Basic')
    await user.type(screen.getByRole('textbox', { name: /Color Name/ }), '  Galaxy   Black  ')

    expect(displayName).toHaveValue('Bambu Lab Galaxy Black')
  })
})

describe('SpoolForm edit validation', () => {
  it('preserves an existing custom display name when edit opens and fields change', async () => {
    const { user } = renderForm({
      initialValues: {
        manufacturerId: '10',
        materialId: '2',
        displayName: 'PLA Preto Principal',
        colorName: 'Preto',
      },
      mode: 'edit',
    })
    const displayName = screen.getByRole('textbox', { name: /Spool Name/ })

    expect(displayName).toHaveValue('PLA Preto Principal')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Manufacturer' }), '11')
    await user.clear(screen.getByRole('textbox', { name: /Color Name/ }))
    await user.type(screen.getByRole('textbox', { name: /Color Name/ }), 'Branco')

    expect(displayName).toHaveValue('PLA Preto Principal')
  })

  it('does not generate a display name for an existing null value on edit', () => {
    renderForm({
      initialValues: {
        manufacturerId: '10',
        materialId: '2',
        displayName: '',
        colorName: 'Preto',
      },
      mode: 'edit',
    })

    expect(screen.getByRole('textbox', { name: /Spool Name/ })).toHaveValue('')
  })

  it('rejects an initial filament weight above 2,000 g before update', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(
      <SpoolForm
        initialValues={{
          manufacturerId: '1',
          materialId: '2',
          colorName: 'Black',
          initialWeight: '1000',
          currentWeight: '800',
        }}
        isSubmitting={false}
        manufacturers={[manufacturer]}
        materials={[material]}
        mode="edit"
        onCancel={vi.fn()}
        onSubmit={onSubmit}
        submitError={null}
      />,
    )
    const initialWeight = screen.getByRole('spinbutton', {
      name: /Initial Filament Weight/,
    })
    await user.clear(initialWeight)
    await user.type(initialWeight, '2000.01')
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))

    expect(screen.getByText('Maximum filament weight per spool is 2,000 g.')).toBeVisible()
    expect(initialWeight).toHaveValue(2000.01)
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits a trimmed optional store name while editing', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(
      <SpoolForm
        initialValues={{
          manufacturerId: '1',
          materialId: '2',
          colorName: 'Black',
          initialWeight: '1000',
          currentWeight: '800',
        }}
        isSubmitting={false}
        manufacturers={[manufacturer]}
        materials={[material]}
        mode="edit"
        onCancel={vi.fn()}
        onSubmit={onSubmit}
        submitError={null}
      />,
    )

    await user.type(screen.getByRole('textbox', { name: /Store Name/ }), '  Filament World  ')
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ store_name: 'Filament World' }),
    )
  })
})
