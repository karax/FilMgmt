import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { confirmCalibration, createTareProfile, getCalibrations, getTareProfiles, previewCalibration, undoCalibration } from '../api/calibrations'
import type { CalibrationInput, TareProfileCreate } from '../types/calibration'
import { spoolQueryKey } from './useSpool'
import { spoolsQueryKey } from './useSpools'

export function useTareProfiles(enabled: boolean) {
  return useQuery({ queryKey: ['tare-profiles'], queryFn: ({ signal }) => getTareProfiles(signal), enabled })
}

export function useCalibrationHistory(code: string, enabled: boolean) {
  return useQuery({ queryKey: ['spool-calibrations', code], queryFn: ({ signal }) => getCalibrations(code, signal), enabled })
}

export function useCreateTareProfile() {
  const client = useQueryClient()
  return useMutation({ mutationFn: (payload: TareProfileCreate) => createTareProfile(payload), onSuccess: async () => client.invalidateQueries({ queryKey: ['tare-profiles'] }) })
}

export function usePreviewCalibration(code: string) {
  return useMutation({ mutationFn: (payload: CalibrationInput) => previewCalibration(code, payload) })
}

export function useConfirmCalibration(code: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (payload: CalibrationInput & { expected_current_remaining_g: string; idempotency_key: string }) => confirmCalibration(code, payload),
    onSuccess: async () => Promise.all([
      client.invalidateQueries({ queryKey: spoolQueryKey(code) }),
      client.invalidateQueries({ queryKey: spoolsQueryKey }),
      client.invalidateQueries({ queryKey: ['spool-calibrations', code] }),
      client.invalidateQueries({ queryKey: ['reconciliation'] }),
    ]),
  })
}

export function useUndoCalibration(code: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) => undoCalibration(code, id, reason),
    onSuccess: async () => Promise.all([
      client.invalidateQueries({ queryKey: spoolQueryKey(code) }),
      client.invalidateQueries({ queryKey: spoolsQueryKey }),
      client.invalidateQueries({ queryKey: ['spool-calibrations', code] }),
      client.invalidateQueries({ queryKey: ['reconciliation'] }),
    ]),
  })
}
