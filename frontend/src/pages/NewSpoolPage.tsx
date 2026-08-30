import { AlertCircle, RefreshCw } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { SpoolForm } from '../components/spool/SpoolForm'
import { useCreateSpool } from '../hooks/useCreateSpool'
import { useLocations } from '../hooks/useLocations'
import { useManufacturers } from '../hooks/useManufacturers'
import { useMaterials } from '../hooks/useMaterials'
import type { CreateSpoolPayload } from '../types/spool'

export function NewSpoolPage() {
  const navigate = useNavigate()
  const manufacturers = useManufacturers()
  const materials = useMaterials()
  const locations = useLocations()
  const createSpool = useCreateSpool()

  const isLoading = manufacturers.isPending || materials.isPending || locations.isPending
  const catalogError = manufacturers.error || materials.error || locations.error

  const retryCatalogs = () => {
    void manufacturers.refetch()
    void materials.refetch()
    void locations.refetch()
  }

  const submit = (payload: CreateSpoolPayload) => {
    createSpool.mutate(payload, {
      onSuccess: (spool) => {
        navigate('/inventory', {
          replace: true,
          state: { createdSpoolCode: spool.code },
        })
      },
    })
  }

  return (
    <section aria-labelledby="new-spool-title" className="mx-auto max-w-4xl">
      <div className="mb-7 border-b border-line pb-5">
        <div className="mb-3 flex items-center gap-3">
          <span aria-hidden="true" className="h-px w-8 bg-accent" />
          <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">
            Inventory / New spool
          </p>
        </div>
        <h2 className="text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl" id="new-spool-title">
          New Spool
        </h2>
        <p className="mt-2 text-sm leading-6 text-ink-muted sm:text-base">
          Register a spool and keep your filament inventory up to date.
        </p>
      </div>

      {isLoading && <FormSkeleton />}

      {catalogError && !isLoading && (
        <div className="rounded-lg border border-red-500/30 bg-surface px-5 py-10 text-center shadow-sm" role="alert">
          <AlertCircle aria-hidden="true" className="mx-auto size-6 text-red-600 dark:text-red-400" />
          <h3 className="mt-4 text-lg font-semibold text-ink">Unable to load form data.</h3>
          <p className="mt-2 text-sm text-ink-muted">Please check the backend connection and try again.</p>
          <button className="mt-6 inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" onClick={retryCatalogs} type="button"><RefreshCw aria-hidden="true" className="size-4" />Retry</button>
        </div>
      )}

      {!isLoading && !catalogError && (
        <SpoolForm
          isSubmitting={createSpool.isPending}
          locations={locations.data ?? []}
          manufacturers={manufacturers.data ?? []}
          materials={materials.data ?? []}
          onCancel={() => navigate('/inventory')}
          onSubmit={submit}
          submitError={createSpool.error}
        />
      )}
    </section>
  )
}

function FormSkeleton() {
  return (
    <div aria-label="Loading spool form" className="space-y-8" role="status">
      {[2, 2, 3, 2].map((fields, section) => (
        <div key={section}>
          <div className="h-5 w-36 animate-pulse rounded bg-surface-raised" />
          <div className="mt-4 grid gap-5 sm:grid-cols-2">
            {Array.from({ length: fields }, (_, field) => (
              <div key={field}><div className="h-4 w-24 animate-pulse rounded bg-surface-raised" /><div className="mt-2 h-11 animate-pulse rounded-md bg-surface-raised" /></div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
