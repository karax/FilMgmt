import { createBrowserRouter, type RouteObject } from 'react-router-dom'

import { AppLayout } from '../components/layout/AppLayout'
import { AdvisorPage } from '../pages/AdvisorPage'
import { AnalyticsPage } from '../pages/AnalyticsPage'
import { DashboardPage } from '../pages/DashboardPage'
import { InventoryPage } from '../pages/InventoryPage'
import { NewSpoolPage } from '../pages/NewSpoolPage'
import { PrintsPage } from '../pages/PrintsPage'
import { SettingsPage } from '../pages/SettingsPage'
import { SpoolDetailsPage } from '../pages/SpoolDetailsPage'
import { EditSpoolPage } from '../pages/EditSpoolPage'
import { EditPrintJobPage } from '../pages/EditPrintJobPage'
import { NewPrintJobPage } from '../pages/NewPrintJobPage'
import { PrintJobDetailsPage } from '../pages/PrintJobDetailsPage'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'inventory', element: <InventoryPage /> },
      { path: 'inventory/new', element: <NewSpoolPage /> },
      { path: 'spools/:code/edit', element: <EditSpoolPage /> },
      { path: 'spools/:code', element: <SpoolDetailsPage /> },
      { path: 'prints', element: <PrintsPage /> },
      { path: 'prints/new', element: <NewPrintJobPage /> },
      { path: 'prints/:id/edit', element: <EditPrintJobPage /> },
      { path: 'prints/:id', element: <PrintJobDetailsPage /> },
      { path: 'advisor', element: <AdvisorPage /> },
      { path: 'analytics', element: <AnalyticsPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
