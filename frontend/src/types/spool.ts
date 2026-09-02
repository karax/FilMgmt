export type SpoolStatus =
  | 'SEALED'
  | 'OPEN'
  | 'IN_USE'
  | 'LOW'
  | 'EMPTY'
  | 'NEEDS_DRYING'
  | 'ARCHIVED'

export type ApiDecimal = number | string

export interface SpoolFilters {
  search?: string
  manufacturerId?: number
  materialId?: number
  status?: SpoolStatus
  needsDrying?: boolean
  minWeightG?: number
  maxWeightG?: number
  minRemainingPercent?: number
  maxRemainingPercent?: number
  includeArchived?: boolean
}

export interface Manufacturer {
  id: number
  name: string
  website: string | null
  created_at: string
  updated_at: string
}

export interface Material {
  id: number
  name: string
  category: string
  default_nozzle_temp_min: number | null
  default_nozzle_temp_max: number | null
  default_bed_temp_min: number | null
  default_bed_temp_max: number | null
  density_g_cm3: ApiDecimal | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface SpoolLocation {
  id?: number
  name: string
}

export interface Spool {
  id: number
  code: string
  manufacturer_id: number
  material_id: number
  manufacturer: Manufacturer
  material: Material
  /** Optional because current installations may not expose storage locations. */
  location?: SpoolLocation | null
  display_name: string | null
  product_name: string | null
  color_name: string
  color_hex: string | null
  diameter_mm: ApiDecimal
  initial_filament_weight_g: ApiDecimal
  current_filament_weight_g: ApiDecimal
  empty_spool_weight_g: ApiDecimal | null
  purchase_price: ApiDecimal | null
  store_name: string | null
  currency: string
  purchase_date: string | null
  opened_at: string | null
  last_used_at: string | null
  nozzle_temp_min: number | null
  nozzle_temp_max: number | null
  bed_temp_min: number | null
  bed_temp_max: number | null
  status: SpoolStatus
  needs_drying: boolean
  last_dried_at: string | null
  notes: string | null
  created_at: string
  updated_at: string
  archived_at: string | null
  remaining_percent: number
}

/** Editable fields accepted by POST /api/spools. */
export interface CreateSpoolPayload {
  manufacturer_id: number
  material_id: number
  display_name: string | null
  product_name: string | null
  color_name: string
  color_hex: string | null
  diameter_mm: number
  initial_filament_weight_g: number
  current_filament_weight_g: number | null
  empty_spool_weight_g: number | null
  purchase_price: number | null
  store_name: string | null
  currency: string
  purchase_date: string | null
  nozzle_temp_min: number | null
  nozzle_temp_max: number | null
  bed_temp_min: number | null
  bed_temp_max: number | null
  status: Extract<SpoolStatus, 'SEALED' | 'OPEN'>
  needs_drying: boolean
  last_dried_at: string | null
  notes: string | null
}

/** Fields editable through PATCH /api/spools/{code}; measurements stay on their dedicated endpoint. */
export interface UpdateSpoolPayload {
  manufacturer_id?: number
  material_id?: number
  display_name?: string | null
  product_name?: string | null
  color_name?: string
  color_hex?: string | null
  diameter_mm?: number
  initial_filament_weight_g?: number
  empty_spool_weight_g?: number | null
  purchase_price?: number | null
  store_name?: string | null
  currency?: string
  purchase_date?: string | null
  nozzle_temp_min?: number | null
  nozzle_temp_max?: number | null
  bed_temp_min?: number | null
  bed_temp_max?: number | null
  needs_drying?: boolean
  last_dried_at?: string | null
  notes?: string | null
}
