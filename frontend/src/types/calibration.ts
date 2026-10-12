import type { ApiDecimal } from './spool'

export type TareSource = 'MEASURED' | 'KNOWN' | 'ESTIMATED' | 'MANUAL'
export type TareConfidence = 'HIGH' | 'MEDIUM' | 'LOW'

export interface TareProfile {
  id: number
  name: string
  manufacturer: string | null
  spool_type: string | null
  description: string | null
  tare_g: ApiDecimal
  source: TareSource
  confidence: TareConfidence
  measured_sample_count: number
  measured_min_g: ApiDecimal | null
  measured_max_g: ApiDecimal | null
  created_at: string
  updated_at: string
  archived_at: string | null
}

export interface TareProfileCreate {
  name: string
  manufacturer?: string
  spool_type?: string
  description?: string
  tare_g: string
  source: TareSource
  confidence?: TareConfidence
}

export interface PendingPrintWarning {
  print_job_id: number
  name: string | null
  printed_at: string | null
}

export interface CalibrationInput {
  measured_total_g: string
  tare_profile_id?: number
  tare_g?: string
  tare_source?: TareSource
  tare_confidence?: TareConfidence
  note?: string
}

export interface CalibrationPreview {
  measured_total_g: ApiDecimal
  tare_g: ApiDecimal
  calculated_filament_g: ApiDecimal
  current_remaining_g: ApiDecimal
  adjustment_g: ApiDecimal
  tare_source: TareSource
  tare_confidence: TareConfidence
  tare_profile_id: number | null
  is_estimated: boolean
  unreconciled_prints: PendingPrintWarning[]
}

export interface CalibrationEvent {
  id: number
  spool_id: number
  event_type: 'PHYSICAL_CALIBRATION' | 'REVERSAL'
  measured_total_g: ApiDecimal | null
  tare_g_used: ApiDecimal | null
  calculated_filament_g: ApiDecimal | null
  previous_remaining_g: ApiDecimal
  adjustment_g: ApiDecimal
  new_remaining_g: ApiDecimal
  tare_source_used: TareSource | null
  tare_confidence_used: TareConfidence | null
  tare_profile_id: number | null
  tare_profile_name: string | null
  note: string | null
  reversed_calibration_id: number | null
  reversed_at: string | null
  effective_at: string
  created_at: string
}
