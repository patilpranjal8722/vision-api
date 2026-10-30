import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom'
import { AppLayout } from '@/app/layouts/AppLayout'
import { AuthLayout } from '@/app/layouts/AuthLayout'
import { AnalyzePage } from '@/pages/AnalyzePage'
import { ViolationsPage } from '@/pages/ViolationsPage'
import { ResultsPage } from '@/pages/ResultsPage'
import { WorkersPage } from '@/pages/WorkersPage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

/**
 * Application route definitions.
 * Exported separately to allow createMemoryRouter usage in unit & integration tests.
 */
export const routes: RouteObject[] = [
  {
    path: '/login',
    element: <AuthLayout />,
    children: [
      {
        index: true,
        element: <LoginPage />,
      },
    ],
  },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: <Navigate to="/analyze" replace />,
      },
      {
        path: 'analyze',
        element: <AnalyzePage />,
      },
      {
        path: 'violations',
        element: <ViolationsPage />,
      },
      {
        path: 'results',
        element: <ResultsPage />,
      },
      {
        path: 'workers',
        element: <WorkersPage />,
      },
    ],
  },
  {
    path: '*',
    element: <AuthLayout />,
    children: [
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
]

/**
 * Browser router instance using HTML5 History API.
 */
export const router = createBrowserRouter(routes)
