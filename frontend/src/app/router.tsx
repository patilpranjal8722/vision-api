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


export const routes: RouteObject[] = [
  // Public-only auth routes
  {
    element: <PublicOnlyRoute />,
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
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <Navigate to="/analyze" replace /> },
          { path: 'analyze', element: <AnalyzePage /> },
          { path: 'violations', element: <ViolationsPage /> },
          { path: 'results', element: <ResultsPage /> },
          { path: 'workers', element: <WorkersPage /> },
        ],
      },
    ],
  },
  // Catch-all 404 (always public)
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

export const router = createBrowserRouter(routes)
