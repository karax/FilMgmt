import { Menu } from 'lucide-react'

import { ThemeToggle } from '../theme/ThemeToggle'

interface HeaderProps {
  title: string
  isNavigationOpen: boolean
  onOpenNavigation: () => void
}

export function Header({
  title,
  isNavigationOpen,
  onOpenNavigation,
}: HeaderProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-surface/90 backdrop-blur-xl">
      <div className="flex min-h-16 items-center gap-3 px-4 sm:px-6 lg:min-h-[4.5rem] lg:px-8">
        <button
          aria-controls="mobile-navigation"
          aria-expanded={isNavigationOpen}
          aria-label="Open navigation menu"
          className="grid size-10 shrink-0 place-items-center rounded-md border border-line bg-surface-raised text-ink transition-colors hover:border-accent hover:text-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent lg:hidden"
          onClick={onOpenNavigation}
          type="button"
        >
          <Menu aria-hidden="true" className="size-5" />
        </button>
        <div className="min-w-0 flex-1">
          <p className="hidden font-mono text-[0.62rem] uppercase tracking-[0.2em] text-ink-muted sm:block">
            Filament Command Center
          </p>
          <h1 className="truncate text-lg font-semibold tracking-tight text-ink sm:text-xl">
            {title}
          </h1>
        </div>
        <div aria-label="Page actions" className="flex items-center gap-2">
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
