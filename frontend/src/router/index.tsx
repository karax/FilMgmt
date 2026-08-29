import { createBrowserRouter, type RouteObject } from 'react-router-dom'

import { AppLayout } from '../components/layout/AppLayout'
import { AdvisorPage } from '../pages/AdvisorPage'
import { AnalyticsPage } from '../pages/AnalyticsPage'
import { DashboardPage } from '../pages/DashboardPage'
import { InventoryPage } from '../pages/InventoryPage'
import { PrintsPage } from '../pages/PrintsPage'
import { SettingsPage } from '../pages/SettingsPage'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'inventory', element: <InventoryPage /> },
      { path: 'prints', element: <PrintsPage /> },
      { path: 'advisor', element: <AdvisorPage /> },
      { path: 'analytics', element: <AnalyticsPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
