import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { makeSpool } from '../../test/spoolFixture'
import { SpoolCard } from './SpoolCard'

const rackLocation = {
  id: 1,
  name: 'Rack A / Slot 3',
  description: null,
  created_at: '2026-08-01T12:00:00Z',
  updated_at: '2026-08-01T12:00:00Z',
}

function completeSpool() {
  return makeSpool({
    code: 'FIL-0042',
    material: { ...makeSpool().material, name: 'PLA+' },
    product_name: 'PLA+ HS',
    current_filament_weight_g: '742.000',
    initial_filament_weight_g: '1000.000',
    remaining_percent: 74.2,
    location_id: 1,
    location: rackLocation,
  })
}

describe('SpoolCard', () => {
  it('renders the primary spool information with the full weight comparison', () => {
    const spool = completeSpool()
    render(<SpoolCard spool={spool} />)

    const card = screen.getByRole('article')
    expect(within(card).getByRole('heading', { name: 'FIL-0042' })).toBeVisible()
    expect(within(card).getByText('eSUN')).toBeVisible()
    expect(within(card).getByText('PLA+')).toBeVisible()
    expect(within(card).getByText('Black')).toBeVisible()
    expect(within(card).getByText('PLA+ HS')).toBeVisible()
    expect(within(card).getByText('74.2%')).toBeVisible()
    expect(within(card).getByText('Open')).toBeVisible()
    expect(within(card).getByText('Rack A / Slot 3')).toBeVisible()
    expect(within(card).getByText(/742 g/)).toHaveTextContent('742 g / 1.00 kg')
  })

  it('does not leave a product line when product_name is null', () => {
    render(<SpoolCard spool={makeSpool({ product_name: null })} />)

    expect(screen.queryByText('PLA+ HS')).not.toBeInTheDocument()
  })

  it('shows a custom spool name while keeping the code visible', () => {
    render(<SpoolCard spool={makeSpool({ code: 'FIL-0042', display_name: 'PLA Preto Principal' })} />)

    expect(screen.getByText('PLA Preto Principal')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'FIL-0042' })).toBeVisible()
  })

  it('uses a safe fallback for missing location and color', () => {
    render(<SpoolCard spool={makeSpool({ color_hex: null, location: null })} />)

    expect(screen.getByText('Unassigned')).toBeVisible()
    expect(screen.getByLabelText('Color: Black')).toBeVisible()
  })

  it.each([['LOW', 'Low'], ['EMPTY', 'Empty']] as const)(
    'renders the %s badge as text',
    (status, label) => {
      render(<SpoolCard spool={makeSpool({ status })} />)

      expect(screen.getByText(label)).toBeVisible()
    },
  )

  it('shows an additional drying warning independently from status', () => {
    render(
      <SpoolCard
        spool={makeSpool({ status: 'OPEN', needs_drying: true })}
      />,
    )

    expect(screen.getByText('Open')).toBeVisible()
    expect(screen.getByText('Needs drying')).toBeVisible()
  })

  it('exposes the reported percentage through an accessible progress bar', () => {
    render(<SpoolCard spool={completeSpool()} />)

    expect(
      screen.getByRole('progressbar', { name: 'FIL-0042 remaining filament' }),
    ).toHaveAttribute('aria-valuenow', '74.2')
  })

  it.each([
    [0, 0],
    [100, 100],
    [110, 100],
    [-10, 0],
  ])('clamps a %s%% progress bar to %s%%', (remainingPercent, expectedValue) => {
    const spool = makeSpool({ remaining_percent: remainingPercent })
    render(<SpoolCard spool={spool} />)

    expect(
      screen.getByRole('progressbar', { name: `${spool.code} remaining filament` }),
    ).toHaveAttribute('aria-valuenow', String(expectedValue))
  })

  it('uses a semantic, keyboard-focusable button when onClick is supplied', () => {
    render(<SpoolCard onClick={() => undefined} spool={completeSpool()} />)

    expect(
      screen.getByRole('button', { name: 'View spool FIL-0042' }),
    ).toBeVisible()
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
  })

  it('renders inside a dark ancestor without depending on light mode', () => {
    const { container } = render(
      <div className="dark">
        <SpoolCard spool={completeSpool()} />
      </div>,
    )

    expect(container.querySelector('article')).toBeVisible()
  })
})
