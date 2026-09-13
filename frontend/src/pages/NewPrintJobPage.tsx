import { AlertCircle, RefreshCw } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { PrintJobForm } from '../components/prints/PrintJobForm'
import { useCreatePrintJob } from '../hooks/usePrintJobMutations'
import { useSpools } from '../hooks/useSpools'
import type { PrintJobPayload } from '../types/printJob'

export function NewPrintJobPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const spools = useSpools()
  const create = useCreatePrintJob()
  const submit = (payload: PrintJobPayload) => create.mutate(payload, { onSuccess: () => navigate('/prints', { replace: true, state: { feedback: t('prints.messages.created') } }) })

  return <section aria-labelledby="new-print-title" className="mx-auto max-w-3xl">
    <PageHeading eyebrow="Print Tracker / New" id="new-print-title" title={t('prints.create.title')} subtitle={t('prints.create.subtitle')} />
    {spools.isPending && <FormSkeleton />}
    {spools.error && !spools.data && !spools.isPending && <LoadError onRetry={() => void spools.refetch()} />}
    {spools.data && <PrintJobForm isSubmitting={create.isPending} mode="create" onCancel={() => navigate('/prints')} onSubmit={submit} spools={spools.data} submitError={create.error} />}
  </section>
}

export function PageHeading({ eyebrow, id, subtitle, title }: { eyebrow: string; id: string; subtitle: string; title: string }) { return <div className="mb-7 border-b border-line pb-5"><p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">{eyebrow}</p><h1 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl" id={id}>{title}</h1><p className="mt-2 text-sm leading-6 text-ink-muted sm:text-base">{subtitle}</p></div> }
export function FormSkeleton() { return <div aria-label="Loading print form" className="space-y-6" role="status">{Array.from({ length: 5 }, (_, index) => <div className="h-20 animate-pulse rounded-lg bg-surface-raised" key={index} />)}</div> }
export function LoadError({ onRetry }: { onRetry: () => void }) { const { t } = useTranslation(); return <div className="rounded-lg border border-red-500/30 bg-surface px-5 py-10 text-center shadow-sm" role="alert"><AlertCircle aria-hidden="true" className="mx-auto size-6 text-red-600 dark:text-red-400" /><h2 className="mt-4 text-lg font-semibold text-ink">{t('prints.form.loadError')}</h2><button className="mt-6 inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar" onClick={onRetry} type="button"><RefreshCw aria-hidden="true" className="size-4" />{t('common.retry')}</button></div> }
