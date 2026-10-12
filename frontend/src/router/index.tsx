import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom'
import { lazy, Suspense } from 'react'

import { AppLayout } from '../components/layout/AppLayout'
import { DashboardPage } from '../pages/DashboardPage'
import { GCodeUploadPage } from '../pages/GCodeUploadPage'
import { InventoryPage } from '../pages/InventoryPage'
import { NewSpoolPage } from '../pages/NewSpoolPage'
import { PrintsPage } from '../pages/PrintsPage'
import { QrScannerPage } from '../pages/QrScannerPage'
import { SettingsPage } from '../pages/SettingsPage'
import { CatalogsPage } from '../pages/CatalogsPage'
import { SpoolDetailsPage } from '../pages/SpoolDetailsPage'
import { SpoolQrLandingPage } from '../pages/SpoolQrLandingPage'
import { EditSpoolPage } from '../pages/EditSpoolPage'
import { EditPrintJobPage } from '../pages/EditPrintJobPage'
import { NewPrintJobPage } from '../pages/NewPrintJobPage'
import { PrintJobDetailsPage } from '../pages/PrintJobDetailsPage'
import { PrinterStatusPage } from '../pages/PrinterStatusPage'
import { ReconciliationPage } from '../pages/ReconciliationPage'

const AnalyticsPage = lazy(async () => {
  const module = await import('../pages/AnalyticsPage')
  return { default: module.AnalyticsPage }
})

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate replace to="inventory" /> },
      { path: 'inventory', element: <InventoryPage /> },
      { path: 'inventory/new', element: <NewSpoolPage /> },
      { path: 'scan', element: <QrScannerPage /> },
      { path: 'gcode', element: <GCodeUploadPage /> },
      { path: 'spools/:code/edit', element: <EditSpoolPage /> },
      { path: 'spools/:code', element: <SpoolDetailsPage /> },
      { path: 'qr/spool/:code', element: <SpoolQrLandingPage /> },
      { path: 'prints', element: <PrintsPage /> },
      { path: 'prints/new', element: <NewPrintJobPage /> },
      { path: 'prints/:id/edit', element: <EditPrintJobPage /> },
      { path: 'prints/:id', element: <PrintJobDetailsPage /> },
      { path: 'printer-status', element: <PrinterStatusPage /> },
      { path: 'reconciliation', element: <ReconciliationPage /> },
      {
        path: 'analytics',
        element: (
          <Suspense fallback={<div aria-label="Loading analytics dashboard" className="h-72 animate-pulse rounded-xl border border-line bg-surface" role="status" />}>
            <AnalyticsPage />
          </Suspense>
        ),
      },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: 'settings/catalogs', element: <CatalogsPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
