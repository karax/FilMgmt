import type { LucideIcon } from 'lucide-react'
import {
  ChartNoAxesCombined,
  LayoutDashboard,
  Lightbulb,
  PackageOpen,
  Printer,
  Settings2,
} from 'lucide-react'

export interface NavigationItem {
  label: string
  title: string
  path: string
  icon: LucideIcon
}

export const navigationItems: readonly NavigationItem[] = [
  { label: 'Dashboard', title: 'Dashboard', path: '/', icon: LayoutDashboard },
  { label: 'Inventory', title: 'Inventory', path: '/inventory', icon: PackageOpen },
  { label: 'Prints', title: 'Prints', path: '/prints', icon: Printer },
  { label: 'Advisor', title: 'Filament Advisor', path: '/advisor', icon: Lightbulb },
  {
    label: 'Analytics',
    title: 'Analytics',
    path: '/analytics',
    icon: ChartNoAxesCombined,
  },
  { label: 'Settings', title: 'Settings', path: '/settings', icon: Settings2 },
]

export function getPageTitle(pathname: string): string {
  if (pathname === '/inventory/new') return 'New Spool'

  return (
    navigationItems.find((item) => item.path === pathname)?.title ??
    'Filament Command Center'
  )
}
