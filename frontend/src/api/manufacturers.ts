import type { Manufacturer } from '../types/spool'
import { apiDelete, apiGet, apiPost, apiPut } from './client'

export interface ManufacturerPayload { name: string; website: string | null }

export function getManufacturers(signal?: AbortSignal): Promise<Manufacturer[]> {
  return apiGet<Manufacturer[]>('/api/manufacturers', signal)
}

export function createManufacturer(payload: ManufacturerPayload): Promise<Manufacturer> {
  return apiPost('/api/manufacturers', payload)
}

export function updateManufacturer(id: number, payload: ManufacturerPayload): Promise<Manufacturer> {
  return apiPut(`/api/manufacturers/${id}`, payload)
}

export function deleteManufacturer(id: number): Promise<void> {
  return apiDelete(`/api/manufacturers/${id}`)
}
