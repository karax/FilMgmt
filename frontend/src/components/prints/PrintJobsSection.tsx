import type { PrintJob } from '../../types/printJob'
import type { Spool } from '../../types/spool'
import { PrintJobCard } from './PrintJobCard'

export function PrintJobsSection({ title, jobs, spools, onStart, onFinish }: { title: string; jobs: PrintJob[]; spools: Map<number, Spool>; onStart: (job: PrintJob) => void; onFinish: (job: PrintJob) => void }) {
  if (jobs.length === 0) return null
  return <section aria-label={title} className="mt-9"><h2 className="text-base font-semibold text-ink">{title}</h2><div className="mt-4 grid gap-4 xl:grid-cols-2">{jobs.map((job) => <PrintJobCard key={job.id} onFinish={onFinish} onStart={onStart} printJob={job} spools={job.spools.map((link) => spools.get(link.spool_id)).filter((spool): spool is Spool => Boolean(spool))} />)}</div></section>
}
