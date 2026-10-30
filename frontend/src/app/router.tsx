import * as React from 'react'
import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom'
import { AppLayout } from '@/app/layouts/AppLayout'
import { AuthLayout } from '@/app/layouts/AuthLayout'
import { ProtectedRoute, PublicOnlyRoute } from '@/app/guards'
import { AnalyzePage } from '@/pages/AnalyzePage'
import { ViolationsPage } from '@/pages/ViolationsPage'
import { ResultsPage } from '@/pages/ResultsPage'
import { WorkersPage } from '@/pages/WorkersPage'
import { LoginPage } from '@/pages/LoginPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { RouteErrorPage } from '@/pages/RouteErrorPage'
import { LoadingState } from '@/components/common/LoadingState'

// Dev-only UI Kit page loaded lazily so it is excluded from production builds
const DevUiKitPage = import.meta.env.DEV
  ? React.lazy(() => import('@/pages/dev/UiKitPage'))
  : null

export const routes: RouteObject[] = [
  // Public-only auth routes
  {
    element: <PublicOnlyRoute />,
    errorElement: <RouteErrorPage />,
    children: [
      {
        path: '/login',
        element: <AuthLayout />,
        children: [{ index: true, element: <LoginPage /> }],
      },
      {
        path: '/register',
        element: <AuthLayout />,
        children: [{ index: true, element: <RegisterPage /> }],
      },
    ],
  },
  // Protected dashboard routes
  {
    path: '/',
    element: <ProtectedRoute />,
    errorElement: <RouteErrorPage />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <Navigate to="/analyze" replace /> },
          { path: 'analyze', element: <AnalyzePage /> },
          { path: 'violations', element: <ViolationsPage /> },
          { path: 'results', element: <ResultsPage /> },
          { path: 'workers', element: <WorkersPage /> },
          ...(import.meta.env.DEV && DevUiKitPage
            ? [
                {
                  path: 'dev/ui-kit',
                  element: (
                    <React.Suspense
                      fallback={<LoadingState message="Loading UI kit showcase..." />}
                    >
                      <DevUiKitPage />
                    </React.Suspense>
                  ),
                },
              ]
            : []),
        ],
      },
    ],
  },
  // Catch-all 404 (always public)
  {
    path: '*',
    element: <AuthLayout />,
    errorElement: <RouteErrorPage />,
    children: [
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
]

export const router = createBrowserRouter(routes)
