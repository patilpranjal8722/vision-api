import * as React from 'react'
import { ErrorState } from '@/components/common/ErrorState'

export interface ErrorBoundaryProps {
  children: React.ReactNode
  /** Optional custom fallback component */
  fallback?: React.ReactNode | ((error: Error) => React.ReactNode)
}

export interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

/**
 * ErrorBoundary:
 * React class component error boundary. Catches JavaScript errors anywhere in its child
 * component tree, logs them only in development, and renders an accessible fallback UI
 * with a "Reload page" action.
 */
export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // Only log unhandled rendering errors to the console during development
    if (import.meta.env.DEV) {
      console.error('[ErrorBoundary caught an error]:', error, errorInfo)
    }
  }

  render(): React.ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        if (typeof this.props.fallback === 'function') {
          return this.props.fallback(this.state.error ?? new Error('Unknown error'))
        }
        return this.props.fallback
      }

      return (
        <div className="flex min-h-[50vh] w-full items-center justify-center p-6">
          <ErrorState
            title="Page Error"
            message={
              this.state.error?.message ||
              'An unexpected error occurred while displaying this page.'
            }
            onRetry={() => window.location.reload()}
            retryLabel="Reload page"
            className="w-full max-w-lg"
          />
        </div>
      )
    }

    return this.props.children
  }
}
