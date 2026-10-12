import type {
  CalibrationEvent,
  CalibrationInput,
  CalibrationPreview,
  TareProfile,
  TareProfileCreate,
} from '../types/calibration'
import { apiGet, apiPost } from './client'

export function getTareProfiles(signal?: AbortSignal): Promise<TareProfile[]> {
  return apiGet<TareProfile[]>('/api/tare-profiles', signal)
}

export function createTareProfile(payload: TareProfileCreate): Promise<TareProfile> {
  return apiPost<TareProfile, TareProfileCreate>('/api/tare-profiles', payload)
}

export function previewCalibration(code: string, payload: CalibrationInput): Promise<CalibrationPreview> {
  return apiPost<CalibrationPreview, CalibrationInput>(`/api/spools/${encodeURIComponent(code)}/calibrations/preview`, payload)
}

export function confirmCalibration(code: string, payload: CalibrationInput & { expected_current_remaining_g: string; idempotency_key: string }): Promise<CalibrationEvent> {
  return apiPost<CalibrationEvent, typeof payload>(`/api/spools/${encodeURIComponent(code)}/calibrations`, payload)
}

export function getCalibrations(code: string, signal?: AbortSignal): Promise<CalibrationEvent[]> {
  return apiGet<CalibrationEvent[]>(`/api/spools/${encodeURIComponent(code)}/calibrations`, signal)
}

export function undoCalibration(code: string, id: number, reason: string): Promise<CalibrationEvent> {
  return apiPost<CalibrationEvent, { reason: string }>(`/api/spools/${encodeURIComponent(code)}/calibrations/${id}/undo`, { reason })
}
