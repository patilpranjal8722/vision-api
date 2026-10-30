import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SpinnerProps {
  /** Preset size for spinner */
  size?: 'sm' | 'md' | 'lg'
  /** Additional custom classes */
  className?: string
  /** Screen-reader label. Default: "Loading..." */
  label?: string
}

const sizeClasses = {
  sm: 'size-4',
  md: 'size-6',
  lg: 'size-8',
}

/**
 * Reusable animated spinner with accessible hidden text.
 */
export function Spinner({ size = 'md', className, label = 'Loading...' }: SpinnerProps) {
  return (
    <span className="inline-flex items-center justify-center" role="status">
      <Loader2
        className={cn('animate-spin text-muted-foreground', sizeClasses[size], className)}
        aria-hidden="true"
        data-testid="spinner-icon"
      />
      <span className="sr-only">{label}</span>
    </span>
  )
}
