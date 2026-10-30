import { cn } from '@/lib/utils'
import { Spinner, type SpinnerProps } from '@/components/common/Spinner'

export interface LoadingStateProps {
  /** Optional loading message to display below or next to the spinner */
  message?: string
  /** Size of the spinner icon */
  spinnerSize?: SpinnerProps['size']
  /** Additional container styling */
  className?: string
}

/**
 * Centered loading state for panels, cards, or whole pages.
 * Configured with role="status" and aria-live="polite" for accessibility.
 */
export function LoadingState({
  message = 'Loading...',
  spinnerSize = 'md',
  className,
}: LoadingStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'flex min-h-48 w-full flex-col items-center justify-center gap-3 p-6 text-center text-muted-foreground',
        className,
      )}
    >
      <Spinner size={spinnerSize} label={message} />
      {message && <p className="text-sm font-medium">{message}</p>}
    </div>
  )
}
