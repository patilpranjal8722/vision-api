import * as React from 'react'
import { AlertCircle, Copy, Check, RotateCw } from 'lucide-react'
import { ApiError, normalizeError } from '@/api/errors'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface ErrorStateProps {
  /** Caught error or ApiError to extract message, status, and requestId from */
  error?: unknown
  /** Explicit title override */
  title?: string
  /** Explicit message override */
  message?: string
  /** Explicit request ID override */
  requestId?: string
  /** Callback to re-attempt the failed operation */
  onRetry?: () => void
  /** Label for the retry button. Default: 'Try again' */
  retryLabel?: string
  /** Visual presentation mode */
  variant?: 'card' | 'inline'
  className?: string
}

/**
 * ErrorState:
 * Accessible error presentation with support for normalized ApiError,
 * network failures, rate limit (429) warnings, request ID tracking, and retry.
 */
export function ErrorState({
  error,
  title,
  message,
  requestId,
  onRetry,
  retryLabel = 'Try again',
  variant = 'card',
  className,
}: ErrorStateProps) {
  const [copied, setCopied] = React.useState(false)

  // Normalize caught error if provided
  const normalized: ApiError | null = error ? normalizeError(error) : null

  const resolvedRequestId = requestId || normalized?.requestId
  const resolvedMessage =
    message || normalized?.message || 'An unexpected error occurred.'
  const resolvedTitle =
    title ||
    (normalized?.status === 0
      ? 'Connection Error'
      : normalized?.status === 429
        ? 'Rate Limit Reached'
        : 'Something went wrong')

  const handleCopyRequestId = React.useCallback(async () => {
    if (!resolvedRequestId) return
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(resolvedRequestId)
      }
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Ignore clipboard write failures in restricted environments
    }
  }, [resolvedRequestId])

  if (variant === 'inline') {
    return (
      <div
        role="alert"
        aria-live="assertive"
        className={cn(
          'flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3.5 text-sm text-destructive',
          className,
        )}
        data-testid="error-state-inline"
      >
        <div className="flex items-start gap-2.5 flex-1 min-w-0">
          <AlertCircle
            className="size-4 shrink-0 mt-0.5 text-destructive"
            aria-hidden="true"
          />
          <div className="space-y-0.5 flex-1 min-w-0">
            <p className="font-semibold">{resolvedTitle}</p>
            <p className="text-destructive/90 text-xs sm:text-sm">{resolvedMessage}</p>
            {resolvedRequestId && (
              <div className="flex items-center gap-1.5 pt-1 text-xs text-muted-foreground">
                <span className="font-mono">Ref: {resolvedRequestId}</span>
                <button
                  type="button"
                  onClick={handleCopyRequestId}
                  className="inline-flex items-center text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring rounded px-1"
                  aria-label="Copy request ID"
                >
                  {copied ? (
                    <Check className="size-3 text-verdict-compliant" />
                  ) : (
                    <Copy className="size-3" />
                  )}
                </button>
              </div>
            )}
          </div>
        </div>

        {onRetry && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="shrink-0 border-destructive/40 text-destructive hover:bg-destructive/10 h-8"
          >
            <RotateCw className="mr-1.5 size-3.5" aria-hidden="true" />
            {retryLabel}
          </Button>
        )}
      </div>
    )
  }

  // Card Variant
  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        'flex flex-col items-center justify-center rounded-xl border border-destructive/30 bg-card p-6 text-center text-card-foreground shadow-sm sm:p-10',
        className,
      )}
      data-testid="error-state-card"
    >
      <div className="flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive mb-3.5">
        <AlertCircle className="size-6" aria-hidden="true" />
      </div>

      <h3 className="text-base font-semibold text-foreground tracking-tight sm:text-lg">
        {resolvedTitle}
      </h3>
      <p className="mt-1.5 max-w-md text-sm text-muted-foreground text-balance">
        {resolvedMessage}
      </p>

      {resolvedRequestId && (
        <div className="mt-3 flex items-center justify-center gap-1.5 rounded bg-muted/60 px-2.5 py-1 text-xs text-muted-foreground">
          <span className="font-mono">Ref: {resolvedRequestId}</span>
          <button
            type="button"
            onClick={handleCopyRequestId}
            className="inline-flex items-center rounded p-0.5 hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            aria-label="Copy request reference ID"
            title="Copy request reference ID"
          >
            {copied ? (
              <Check className="size-3.5 text-verdict-compliant" />
            ) : (
              <Copy className="size-3.5" />
            )}
          </button>
        </div>
      )}

      {onRetry && (
        <Button type="button" onClick={onRetry} variant="outline" className="mt-5">
          <RotateCw className="mr-2 size-4" aria-hidden="true" />
          {retryLabel}
        </Button>
      )}
    </div>
  )
}
