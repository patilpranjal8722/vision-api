import { cn } from '@/lib/utils'
import { VERDICT_ORDER, getVerdictMeta } from '@/lib/verdict'
import { VerdictBadge } from '@/components/common/VerdictBadge'

export interface VerdictLegendProps {
  /** Optional container class name */
  className?: string
  /** Badge size to use in legend */
  badgeSize?: 'sm' | 'md'
}

/**
 * VerdictLegend:
 * Explains the three compliance categories (Compliant, Violation, Uncertain)
 * along with their human-readable definitions.
 */
export function VerdictLegend({ className, badgeSize = 'md' }: VerdictLegendProps) {
  return (
    <div
      className={cn(
        'space-y-3 rounded-lg border border-border bg-card p-4 text-card-foreground',
        className,
      )}
      aria-label="PPE compliance status legend"
    >
      <h3 className="text-sm font-semibold text-foreground">Compliance Verdicts</h3>
      <ul className="space-y-2.5">
        {VERDICT_ORDER.map((verdict) => {
          const meta = getVerdictMeta(verdict)
          return (
            <li
              key={verdict}
              className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3"
            >
              <VerdictBadge verdict={verdict} size={badgeSize} />
              <span className="text-xs sm:text-sm text-muted-foreground">
                {meta.description}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
