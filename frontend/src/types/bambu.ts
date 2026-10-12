export type BambuConnectionState =
  | 'DISABLED'
  | 'CONNECTING'
  | 'CONNECTED'
  | 'DISCONNECTED'

export type BambuPrintState =
  | 'UNKNOWN'
  | 'IDLE'
  | 'PREPARING'
  | 'PRINTING'
  | 'PAUSED'
  | 'FINISHED'
  | 'FAILED'
  | 'CANCELLED'

export interface BambuAmsTray {
  tray_id: string
  material_type: string | null
  color: string | null
  profile_id: string | null
  setting_id: string | null
  brand: string | null
  tag_uid: string | null
  tray_uuid: string | null
  remaining_percent: number | null
  nozzle_temp_min: number | null
  nozzle_temp_max: number | null
}

export interface BambuAmsUnit {
  unit_id: string
  humidity: number | null
  temperature_c: number | null
  trays: BambuAmsTray[]
}

export interface BambuStatus {
  configured: boolean
  connected: boolean
  connection_state: BambuConnectionState
  missing_configuration: string[]
  configuration_error: string | null
  serial: string | null
  last_update_at: string | null
  state: BambuPrintState
  raw_state: string | null
  progress: number | null
  current_layer: number | null
  total_layers: number | null
  remaining_time_minutes: number | null
  current_print: string | null
  gcode_file: string | null
  project_name: string | null
  project_id: string | null
  profile_id: string | null
  task_id: string | null
  subtask_id: string | null
  current_tray: string | null
  ams: BambuAmsUnit[]
  external_tray: BambuAmsTray | null
  active_print_job_id: number | null
  ftps_configured: boolean
  ftps_reachable: boolean | null
  last_ftps_success_at: string | null
  last_ftps_error_code: string | null
}
