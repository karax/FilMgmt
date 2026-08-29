interface PagePlaceholderProps {
  title: string
  description: string
  moduleCode: string
}

export function PagePlaceholder({
  title,
  description,
  moduleCode,
}: PagePlaceholderProps) {
  return (
    <section aria-labelledby="content-title" className="max-w-4xl">
      <div className="mb-4 flex items-center gap-3">
        <span className="h-px w-8 bg-accent" aria-hidden="true" />
        <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">
          Module / {moduleCode}
        </p>
      </div>
      <h2
        className="text-3xl font-semibold tracking-[-0.035em] text-ink sm:text-4xl"
        id="content-title"
      >
        {title}
      </h2>
      <p className="mt-3 max-w-2xl text-base leading-7 text-ink-muted sm:text-lg">
        {description}
      </p>
      <div className="mt-10 min-h-64 rounded-lg border border-dashed border-line bg-surface/55 p-6 sm:min-h-72 sm:p-8">
        <div className="flex items-center gap-2 font-mono text-[0.65rem] uppercase tracking-[0.16em] text-ink-muted">
          <span className="size-1.5 rounded-full bg-accent" aria-hidden="true" />
          Workspace ready
        </div>
      </div>
    </section>
  )
}
