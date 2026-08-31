import { AlertCircle } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { PrintJobForm, printJobFormValues } from '../components/prints/PrintJobForm'
import { usePrintJob } from '../hooks/usePrintJob'
import { useUpdatePrintJob } from '../hooks/usePrintJobMutations'
import { useSpools } from '../hooks/useSpools'
import { type UpdatePrintJobPayload } from '../types/printJob'
import { FormSkeleton, LoadError, PageHeading } from './NewPrintJobPage'

function updatedFields(_current: ReturnType<typeof printJobFormValues>, payload: UpdatePrintJobPayload): UpdatePrintJobPayload { return payload }

export function EditPrintJobPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const id = Number(useParams().id)
  const job = usePrintJob(Number.isInteger(id) && id > 0 ? id : undefined)
  const spools = useSpools({ includeArchived: true })
  const update = useUpdatePrintJob()
  if (job.isPending || spools.isPending) return <FormSkeleton />
  if (!job.data || job.error || spools.error) {
    if (job.error && 'status' in job.error && job.error.status === 404) return <NotFound />
    return <LoadError onRetry={() => { void job.refetch(); void spools.refetch() }} />
  }
  if (job.data.status !== 'PLANNED') return <section className="mx-auto max-w-3xl rounded-lg border border-line bg-surface p-7 text-center"><AlertCircle aria-hidden="true" className="mx-auto size-7 text-amber-600 dark:text-amber-300" /><h1 className="mt-4 text-xl font-semibold text-ink">{t('prints.messages.cannotEdit')}</h1><button className="mt-6 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar" onClick={() => navigate('/prints')} type="button">{t('prints.actions.back')}</button></section>
  const initialValues = printJobFormValues(job.data)
  return <section aria-labelledby="edit-print-title" className="mx-auto max-w-3xl"><PageHeading eyebrow={`Print Tracker / #${job.data.id} / Edit`} id="edit-print-title" subtitle={t('prints.edit.subtitle')} title={t('prints.edit.title')} /><PrintJobForm initialValues={initialValues} isSubmitting={update.isPending} mode="edit" onCancel={() => navigate('/prints')} onSubmit={(payload) => update.mutate({ id: job.data.id, payload: updatedFields(initialValues, payload) }, { onSuccess: () => navigate('/prints', { replace: true, state: { feedback: t('prints.messages.updated') } }) })} spools={spools.data ?? []} submitError={update.error} /></section>
}

function NotFound() { const { t } = useTranslation(); const navigate = useNavigate(); return <section className="mx-auto max-w-3xl rounded-lg border border-red-500/30 bg-surface px-5 py-12 text-center" role="alert"><AlertCircle aria-hidden="true" className="mx-auto size-7 text-red-600 dark:text-red-400" /><h1 className="mt-4 text-xl font-semibold text-ink">{t('prints.edit.notFound')}</h1><button className="mt-6 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar" onClick={() => navigate('/prints')} type="button">{t('prints.actions.back')}</button></section> }
