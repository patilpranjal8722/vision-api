import { useRouteError, isRouteErrorResponse } from 'react-router-dom'
import { ErrorState } from '@/components/common/ErrorState'

/**
 * RouteErrorPage:
 * Top-level route boundary error element for react-router.
 * Catches route navigation, loader, or action exceptions and displays ErrorState.
 */
export function RouteErrorPage() {
  const error = useRouteError()

  if (import.meta.env.DEV) {
    console.error('[RouteErrorPage unhandled route error]:', error)
  }

  let title = 'Page Error'
  let message = 'An unexpected routing error occurred.'

  if (isRouteErrorResponse(error)) {
    title = `${error.status} ${error.statusText}`
    message = error.data?.message || error.data || 'Failed to load route.'
  } else if (error instanceof Error) {
    message = error.message
  }

  return (
    <div className="flex min-h-screen w-full items-center justify-center p-6 bg-background">
      <ErrorState
        title={title}
        message={message}
        onRetry={() => window.location.reload()}
        retryLabel="Reload page"
        className="w-full max-w-lg shadow-md"
      />
    </div>
  )
}
