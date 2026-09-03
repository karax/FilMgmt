export type GCodeUploadStatus = 'UPLOADED'

export interface GCodeUploadResponse {
  upload_id: string
  filename: string
  size_bytes: number
  created_at: string
  status: GCodeUploadStatus
}

export interface GCodeToolSummary {
  tool: number
  extrusion_length_mm: number | null
  extrusion_volume_mm3: number | null
}

export interface GCodeParseResult {
  parser_version: 1
  upload_id: string
  filename: string
  source_size_bytes: number
  line_count: number
  blank_line_count: number
  comment_line_count: number
  command_line_count: number
  unknown_line_count: number
  malformed_line_count: number
  command_counts: Record<string, number>
  units: 'mm' | 'in'
  xyz_positioning: 'absolute' | 'relative'
  extrusion_mode: 'absolute' | 'relative'
  current_tool: number
  tools: GCodeToolSummary[]
  total_extrusion_length_mm: number | null
  total_extrusion_volume_mm3: number | null
  nozzle_temperatures_c: number[]
  bed_temperatures_c: number[]
  metadata: Record<string, string>
  warnings: string[]
}

export interface GCodeWeightToolRequest {
  tool: number
  material_id?: number
  filament_diameter_mm?: string
}

export interface GCodeWeightRequest {
  tools: GCodeWeightToolRequest[]
}

export type GCodeWeightSource = 'material' | 'gcode_metadata' | 'request' | 'not_available'

export interface GCodeToolWeightResult {
  tool: number
  material_id: number | null
  material_name: string | null
  extrusion_mode: 'linear' | 'volumetric' | 'mixed' | 'none'
  extrusion_length_mm: string | null
  extrusion_volume_mm3: string | null
  calculated_volume_mm3: string
  filament_diameter_mm: string | null
  diameter_source: Extract<GCodeWeightSource, 'request' | 'gcode_metadata' | 'not_available'>
  density_g_cm3: string | null
  density_source: Extract<GCodeWeightSource, 'material' | 'gcode_metadata' | 'not_available'>
  estimated_weight_g: string | null
  warnings: string[]
}

export interface GCodeWeightResult {
  upload_id: string
  parser_version: number
  tools: GCodeToolWeightResult[]
  total_estimated_weight_g: string | null
  known_estimated_weight_g: string
  is_complete: boolean
  warnings: string[]
}

export type GCodeTimeSource = 'slicer_metadata' | 'command_kinematics'

export interface GCodeTimeResult {
  time_estimator_version: 1
  upload_id: string
  parser_version: number
  estimated_time_seconds: number | null
  source: GCodeTimeSource | null
  slicer_estimated_time_seconds: number | null
  slicer_time_key: string | null
  kinematic_estimated_time_seconds: number | null
  motion_time_seconds: number
  dwell_time_seconds: number
  kinematic_is_complete: boolean
  unestimated_motion_count: number
  is_heuristic: boolean
  is_complete: boolean
  warnings: string[]
}

export type GCodeMaterialDetectionSource = 'slicer_metadata' | 'temperature_heuristic'
export type GCodeMaterialConfidence = 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE'

export interface GCodeMaterialCandidate {
  material_id: number
  material_name: string
}

export interface GCodeMaterialEvidence {
  metadata_key: string | null
  nozzle_temperatures_c: number[]
  bed_temperatures_c: number[]
}

export interface GCodeToolMaterialDetection {
  tool: number
  material_id: number | null
  material_name: string | null
  raw_material_label: string | null
  source: GCodeMaterialDetectionSource | null
  confidence: GCodeMaterialConfidence
  evidence: GCodeMaterialEvidence
  candidates: GCodeMaterialCandidate[]
  warnings: string[]
}

export interface GCodeMaterialDetectionResult {
  upload_id: string
  parser_version: number
  tools: GCodeToolMaterialDetection[]
  is_complete: boolean
  warnings: string[]
}
