import { apiPost, apiPostFormData, apiPostWithoutBody } from './client'
import type {
  GCodeMaterialDetectionResult,
  GCodeParseResult,
  GCodeTimeResult,
  GCodeUploadResponse,
  GCodeWeightRequest,
  GCodeWeightResult,
} from '../types/gcode'

export function uploadGCode(file: File): Promise<GCodeUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  return apiPostFormData<GCodeUploadResponse>('/api/gcode/uploads', formData)
}

export function parseGCode(uploadId: string): Promise<GCodeParseResult> {
  return apiPostWithoutBody<GCodeParseResult>(
    `/api/gcode/uploads/${encodeURIComponent(uploadId)}/parse`,
  )
}

export function estimateGCodeTime(uploadId: string): Promise<GCodeTimeResult> {
  return apiPostWithoutBody<GCodeTimeResult>(
    `/api/gcode/uploads/${encodeURIComponent(uploadId)}/time`,
  )
}

export function detectGCodeMaterial(uploadId: string): Promise<GCodeMaterialDetectionResult> {
  return apiPostWithoutBody<GCodeMaterialDetectionResult>(
    `/api/gcode/uploads/${encodeURIComponent(uploadId)}/material-detection`,
  )
}

export function calculateGCodeWeight(
  uploadId: string,
  payload: GCodeWeightRequest,
): Promise<GCodeWeightResult> {
  return apiPost<GCodeWeightResult, GCodeWeightRequest>(
    `/api/gcode/uploads/${encodeURIComponent(uploadId)}/weight`,
    payload,
  )
}
