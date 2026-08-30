import type { ReactNode } from 'react'

export function SpoolInfoSection({ title, children }: { title: string; children: ReactNode }) {
  return <section aria-labelledby={`${title.toLowerCase().replaceAll(' ', '-')}-title`} className="rounded-lg border border-line bg-surface p-5 shadow-sm"><h2 id={`${title.toLowerCase().replaceAll(' ', '-')}-title`} className="text-lg font-semibold text-ink">{title}</h2><dl className="mt-5 space-y-4">{children}</dl></section>
}

export function InfoRow({ label, children }: { label: string; children: ReactNode }) {
  return <div className="grid gap-1 sm:grid-cols-[9rem_1fr] sm:gap-4"><dt className="text-sm text-ink-muted">{label}</dt><dd className="text-sm font-medium text-ink">{children}</dd></div>
}
