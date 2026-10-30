import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * ProtectedRoute:
 * - Shows a full-page Skeleton while authentication state is initializing.
 * - Redirects unauthenticated users to /login and saves current location in route state.
 * - Renders child Outlet when authenticated.
 */
export function ProtectedRoute() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen w-full flex-col p-6 space-y-4 bg-background">
        <Skeleton className="h-14 w-full rounded-lg" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 flex-1">
          <Skeleton className="h-96 w-full hidden md:block rounded-lg" />
          <div className="md:col-span-3 space-y-4">
            <Skeleton className="h-28 w-full rounded-lg" />
            <Skeleton className="h-72 w-full rounded-lg" />
          </div>
        </div>
      </div>
    )
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <Outlet />
}

/**
 * PublicOnlyRoute:
 * - Prevents already-authenticated users from re-visiting /login or /register.
 * - Redirects authenticated users to their intended destination or /analyze.
 */
export function PublicOnlyRoute() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center p-6 bg-background">
        <Skeleton className="h-96 w-full max-w-md rounded-xl" />
      </div>
    )
  }

  if (status === 'authenticated') {
    const from =
      (location.state as { from?: { pathname: string } })?.from?.pathname || '/analyze'
    return <Navigate to={from} replace />
  }

  return <Outlet />
}
