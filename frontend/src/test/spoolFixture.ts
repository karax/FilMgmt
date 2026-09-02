import type { Spool } from '../types/spool'

export function makeSpool(overrides: Partial<Spool> = {}): Spool {
  const id = overrides.id ?? 1
  const materialId = overrides.material?.id ?? overrides.material_id ?? 1
  const manufacturerId =
    overrides.manufacturer?.id ?? overrides.manufacturer_id ?? 1

  return {
    id,
    code: `FIL-${String(id).padStart(4, '0')}`,
    manufacturer_id: manufacturerId,
    material_id: materialId,
    manufacturer: {
      id: manufacturerId,
      name: 'eSUN',
      website: null,
      created_at: '2026-08-01T12:00:00Z',
      updated_at: '2026-08-01T12:00:00Z',
    },
    material: {
      id: materialId,
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
    },
    display_name: null,
    product_name: null,
    color_name: 'Black',
    color_hex: '#000000',
    diameter_mm: '1.75',
    initial_filament_weight_g: '1000.000',
    current_filament_weight_g: '800.000',
    empty_spool_weight_g: null,
    purchase_price: null,
    store_name: null,
    currency: 'EUR',
    purchase_date: null,
    opened_at: null,
    last_used_at: null,
    nozzle_temp_min: null,
    nozzle_temp_max: null,
    bed_temp_min: null,
    bed_temp_max: null,
    status: 'OPEN',
    needs_drying: false,
    last_dried_at: null,
    notes: null,
    created_at: '2026-08-01T12:00:00Z',
    updated_at: '2026-08-01T12:00:00Z',
    archived_at: null,
    remaining_percent: 80,
    ...overrides,
  }
}
