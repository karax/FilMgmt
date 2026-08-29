import { X } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { Brand } from './Brand'
import { NavigationList } from './NavigationList'

interface MobileNavigationProps {
  isOpen: boolean
  onClose: () => void
}

export function MobileNavigation({ isOpen, onClose }: MobileNavigationProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const returnFocusRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!isOpen) return

    const previousOverflow = document.body.style.overflow
    returnFocusRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
    document.body.style.overflow = 'hidden'
    closeButtonRef.current?.focus()

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)

    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', closeOnEscape)
      returnFocusRef.current?.focus()
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <button
        aria-label="Close navigation overlay"
        className="absolute inset-0 cursor-default bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        type="button"
      />
      <aside
        aria-label="Mobile navigation"
        aria-modal="true"
        className="relative flex h-full w-[min(20rem,88vw)] flex-col border-r border-white/10 bg-sidebar shadow-2xl"
        id="mobile-navigation"
        role="dialog"
      >
        <div className="flex items-center justify-between gap-4 border-b border-white/8 px-5 py-5">
          <Brand />
          <button
            ref={closeButtonRef}
            aria-label="Close navigation menu"
            className="grid size-10 shrink-0 place-items-center rounded-md border border-white/10 text-sidebar-muted transition-colors hover:border-accent/60 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" className="size-5" />
          </button>
        </div>
        <nav
          aria-label="Mobile primary navigation"
          className="flex-1 overflow-y-auto px-4 py-6"
        >
          <NavigationList />
        </nav>
      </aside>
    </div>
  )
}
