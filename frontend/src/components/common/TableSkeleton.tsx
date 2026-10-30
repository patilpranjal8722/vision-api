import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export interface TableSkeletonProps {
  /** Number of table rows to render. Default: 5 */
  rows?: number
  /** Number of columns per row. Default: 4 */
  columns?: number
  className?: string
}

/**
 * TableSkeleton:
 * Loading placeholder for data tables, rendering header and rows with subtle variations.
 */
export function TableSkeleton({ rows = 5, columns = 4, className }: TableSkeletonProps) {
  const rowList = Array.from({ length: Math.max(1, rows) }, (_, i) => i)
  const colList = Array.from({ length: Math.max(1, columns) }, (_, i) => i)

  return (
    <div
      className={cn(
        'w-full rounded-xl border border-border bg-card overflow-hidden',
        className,
      )}
      data-testid="table-skeleton"
    >
      {/* Table Header Placeholder */}
      <div className="flex items-center gap-4 border-b border-border bg-muted/30 px-6 py-3.5">
        {colList.map((colIdx) => (
          <Skeleton key={`header-${colIdx}`} className="h-4 flex-1 rounded" />
        ))}
      </div>

      {/* Table Rows Placeholder */}
      <div className="divide-y divide-border">
        {rowList.map((rowIdx) => (
          <div key={`row-${rowIdx}`} className="flex items-center gap-4 px-6 py-4">
            {colList.map((colIdx) => (
              <Skeleton
                key={`cell-${rowIdx}-${colIdx}`}
                className={cn('h-4 rounded', colIdx === 0 ? 'w-24' : 'flex-1')}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
