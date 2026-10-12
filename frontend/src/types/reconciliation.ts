import type { ApiDecimal, PrintJobStatus } from './printJob'

export type ReconciliationStatus =
  | 'PENDING'
  | 'PARTIALLY_RECONCILED'
  | 'RECONCILED'
  | 'NEEDS_REVIEW'
  | 'NOT_APPLICABLE'

export type CandidateConfidence = 'EXACT' | 'HIGH' | 'MEDIUM' | 'LOW' | 'AMBIGUOUS'

export interface ReconciliationCandidateReason {
  code: string
  detail: string
}

export interface ReconciliationSpoolCandidate {
  id: number
  code: string
  display_name: string | null
  product_name: string | null
  manufacturer_name: string
  material_name: string
  color_name: string
  color_hex: string | null
  current_filament_weight_g: ApiDecimal
  purchase_price: ApiDecimal | null
  currency: string
  confidence: CandidateConfidence
  reasons: ReconciliationCandidateReason[]
  sufficient_remaining: boolean
  latest_physical_calibration_at?: string | null
}

export interface ReconciliationSpoolOption {
  id: number
  code: string
  display_name: string | null
  manufacturer_name: string
  material_name: string
  color_name: string
  color_hex: string | null
  current_filament_weight_g: ApiDecimal
  latest_physical_calibration_at?: string | null
}

export interface ReconciliationResolution {
  id: number
  event_type: 'CONSUMPTION' | 'SKIP' | 'REVERSAL'
  spool_id: number | null
  spool_code: string | null
  amount_g: ApiDecimal
  sliced_estimated_g: ApiDecimal | null
  remaining_before_g: ApiDecimal | null
  remaining_after_g: ApiDecimal | null
  manual_override: boolean
  reason: string | null
  created_at: string
}

export interface ReconciliationUsage {
  id: number
  position: number
  material_type: string | null
  color: string | null
  used_g: ApiDecimal | null
  progress_estimated_g?: ApiDecimal | null
  used_m: ApiDecimal | null
  tray_info_idx: string | null
  ams_tray: string | null
  ams_brand: string | null
  candidates: ReconciliationSpoolCandidate[]
  recommended_spool_id: number | null
  unambiguous: boolean
  requires_manual_consumption: boolean
  resolution: ReconciliationResolution | null
}

export interface ReconciliationJob {
  id: number
  name: string | null
  gcode_file: string | null
  status: PrintJobStatus
  reconciliation_status: ReconciliationStatus
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  actual_time_minutes: number | null
  final_progress: number | null
  selected_plate_index: number | null
  selected_plate_name: string | null
  thumbnail_url: string | null
  filament_count: number
  estimated_filament_g: ApiDecimal | null
  filaments: ReconciliationUsage[]
}

export interface ReconciliationQueue {
  jobs: ReconciliationJob[]
  recently_reconciled_jobs: ReconciliationJob[]
  available_spools: ReconciliationSpoolOption[]
  pending_job_count: number
  ready_job_count: number
  needs_review_job_count: number
  estimated_pending_g: ApiDecimal
}

export type ReconciliationConfirmItem =
  | {
      filament_usage_id: number
      action: 'DEDUCT'
      spool_id: number
      consumption_g: number
      reason?: string
      checkpoint_acknowledged?: boolean
    }
  | {
      filament_usage_id: number
      action: 'SKIP'
      reason?: string
    }

export interface ReconciliationConfirmResult {
  reconciled_usage_ids: number[]
  print_jobs: ReconciliationJob[]
}
