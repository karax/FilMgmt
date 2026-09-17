import { AlertCircle, Plus, Printer } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useInRouterContext } from 'react-router-dom'

import { PrintJobsSection } from '../components/prints/PrintJobsSection'
import { FinishPrintDialog, StartPrintDialog } from '../components/prints/PrintLifecycleDialogs'
import { usePrintJobs } from '../hooks/usePrintJobs'
import { useSpools } from '../hooks/useSpools'
import { jobsForStatus } from '../lib/printJobs'
import type { PrintJob } from '../types/printJob'

type PrintAction = { type: 'start' | 'finish'; jobId: number } | null

export function PrintsPage() {
  const { t } = useTranslation()
  const [feedback, setFeedback] = useState<string | null>(() => (
    (window.history.state as { usr?: { feedback?: string } } | null)?.usr?.feedback ?? null
  ))
  const [action, setAction] = useState<PrintAction>(null)
  const { data: jobs, error, isPending, isFetching, refetch } = usePrintJobs()
  const { data: spools = [] } = useSpools({ includeArchived: true })
  const spoolMap = new Map(spools.map((spool) => [spool.id, spool]))
  const selectedJob = action ? jobs?.find((job) => job.id === action.jobId) : undefined
  const selectedEntries = selectedJob?.spools.map((link) => ({ link, spool: spoolMap.get(link.spool_id) })) ?? []

  useEffect(() => {
    if (!action || !jobs) return
    const current = jobs.find((job) => job.id === action.jobId)
    const expectedStatus = action.type === 'start' ? 'PLANNED' : 'PRINTING'
    if (!current || current.status !== expectedStatus) setAction(null)
  }, [action, jobs])

  const openStart = (job: PrintJob) => setAction({ type: 'start', jobId: job.id })
  const openFinish = (job: PrintJob) => setAction({ type: 'finish', jobId: job.id })

  return (
    <section aria-labelledby="prints-title">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
        <div>
        <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">{t('prints.eyebrow')}</p>
        <h1 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl" id="prints-title">{t('prints.title')}</h1>
        <p className="mt-2 text-sm text-ink-muted">{t('prints.description')}</p>
        </div>
        <PrintsNewLink label={t('prints.actions.new')} />
      </div>

      {feedback && <div className="mt-5 flex items-center justify-between gap-4 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-ink" role="status"><span>{feedback}</span><button aria-label={t('prints.actions.dismiss')} className="font-semibold text-ink-muted hover:text-ink" onClick={() => setFeedback(null)} type="button">×</button></div>}

      {isPending && <div aria-label={t('prints.loading')} className="mt-7 grid gap-4 xl:grid-cols-2" role="status">{Array.from({ length: 4 }, (_, index) => <div className="h-48 animate-pulse rounded-lg border border-line bg-surface-raised" key={index} />)}</div>}

      {error && !isPending && <div className="mt-7 rounded-lg border border-red-500/30 bg-surface px-5 py-10 text-center shadow-sm" role="alert"><AlertCircle aria-hidden="true" className="mx-auto size-6 text-red-600 dark:text-red-400" /><h2 className="mt-4 text-lg font-semibold text-ink">{t('prints.error')}</h2><button className="mt-6 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar disabled:opacity-60" disabled={isFetching} onClick={() => void refetch()} type="button">{isFetching ? t('prints.retrying') : t('common.retry')}</button></div>}

      {!isPending && !error && jobs?.length === 0 && <div className="mt-8 rounded-lg border border-dashed border-line bg-surface px-5 py-14 text-center shadow-sm"><Printer aria-hidden="true" className="mx-auto size-7 text-ink-muted" /><h2 className="mt-4 text-lg font-semibold text-ink">{t('prints.emptyTitle')}</h2><p className="mt-2 text-sm text-ink-muted">{t('prints.emptyDescription')}</p></div>}

      {!isPending && !error && jobs && jobs.length > 0 && <>
        <PrintJobsSection title={t('prints.sections.printing')} jobs={jobsForStatus(jobs, 'PRINTING')} onFinish={openFinish} onStart={openStart} spools={spoolMap} />
        <PrintJobsSection title={t('prints.sections.planned')} jobs={jobsForStatus(jobs, 'PLANNED')} onFinish={openFinish} onStart={openStart} spools={spoolMap} />
        <PrintJobsSection title={t('prints.sections.success')} jobs={jobsForStatus(jobs, 'SUCCESS')} onFinish={openFinish} onStart={openStart} spools={spoolMap} />
        <PrintJobsSection title={t('prints.sections.other')} jobs={[...jobsForStatus(jobs, 'FAILED'), ...jobsForStatus(jobs, 'CANCELLED')]} onFinish={openFinish} onStart={openStart} spools={spoolMap} />
      </>}
      {action?.type === 'start' && selectedJob && <StartPrintDialog entries={selectedEntries} onCancel={() => setAction(null)} onSuccess={() => { setAction(null); setFeedback(t('prints.messages.started')) }} printJob={selectedJob} />}
      {action?.type === 'finish' && selectedJob && <FinishPrintDialog entries={selectedEntries} onCancel={() => setAction(null)} onSuccess={() => { setAction(null); setFeedback(t('prints.messages.finished')) }} printJob={selectedJob} />}
    </section>
  )
}

function PrintsNewLink({ label }: { label: string }) {
  const className = 'inline-flex min-h-11 items-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent'
  return useInRouterContext() ? <Link className={className} to="/prints/new"><Plus aria-hidden="true" className="size-4" />{label}</Link> : <a className={className} href="/prints/new"><Plus aria-hidden="true" className="size-4" />{label}</a>
}
