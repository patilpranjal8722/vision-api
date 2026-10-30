import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export interface CardSkeletonProps {
  className?: string
  /** Whether to show an icon placeholder in the header */
  hasIcon?: boolean
}

/**
 * CardSkeleton:
 * Loading placeholder mimicking a standard card with header, metric, and footer/hint.
 */
export function CardSkeleton({ className, hasIcon = true }: CardSkeletonProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-card p-6 shadow-sm space-y-4',
        className,
      )}
      data-testid="card-skeleton"
    >
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-28 rounded" />
        {hasIcon && <Skeleton className="h-5 w-5 rounded-md" />}
      </div>
      <Skeleton className="h-8 w-20 rounded" />
      <Skeleton className="h-3 w-40 rounded" />
    </div>
  )
}
