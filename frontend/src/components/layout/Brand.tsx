import { Disc3 } from 'lucide-react'
import { Link } from 'react-router-dom'

export function Brand() {
  return (
    <Link
      aria-label="Filament Command Center home"
      className="flex items-center gap-3 rounded-md text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
      to="/"
    >
      <span className="grid size-10 shrink-0 place-items-center rounded-md border border-accent/50 bg-accent/10 text-accent">
        <Disc3 aria-hidden="true" className="size-5" strokeWidth={1.7} />
      </span>
      <span className="min-w-0 leading-tight">
        <span className="block text-[0.68rem] font-bold uppercase tracking-[0.22em] text-accent">
          Filament
        </span>
        <span className="block truncate text-sm font-semibold tracking-wide">
          Command Center
        </span>
      </span>
    </Link>
  )
}
