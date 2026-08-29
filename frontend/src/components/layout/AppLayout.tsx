import { useCallback, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import { getPageTitle } from '../../navigation'
import { Header } from './Header'
import { MobileNavigation } from './MobileNavigation'
import { PageContainer } from './PageContainer'
import { Sidebar } from './Sidebar'

export function AppLayout() {
  const [isMobileNavigationOpen, setMobileNavigationOpen] = useState(false)
  const location = useLocation()
  const closeMobileNavigation = useCallback(
    () => setMobileNavigationOpen(false),
    [],
  )

  useEffect(() => {
    closeMobileNavigation()
  }, [closeMobileNavigation, location.pathname])

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <a
        className="fixed left-4 top-3 z-[60] -translate-y-20 rounded-md bg-accent px-4 py-2 text-sm font-bold text-sidebar transition-transform focus:translate-y-0"
        href="#main-content"
      >
        Skip to content
      </a>
      <Sidebar />
      <div className="min-w-0 lg:pl-72">
        <Header
          isNavigationOpen={isMobileNavigationOpen}
          title={getPageTitle(location.pathname)}
          onOpenNavigation={() => setMobileNavigationOpen(true)}
        />
        <main
          className="min-h-[calc(100vh-4rem)] lg:min-h-[calc(100vh-4.5rem)]"
          id="main-content"
        >
          <PageContainer>
            <Outlet />
          </PageContainer>
        </main>
      </div>
      <MobileNavigation
        isOpen={isMobileNavigationOpen}
        onClose={closeMobileNavigation}
      />
    </div>
  )
}
