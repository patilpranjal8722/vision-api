import * as React from 'react'
import type { LucideIcon } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export type StatTone = 'default' | 'compliant' | 'violation' | 'uncertain'

export interface StatCardProps {
  /** Metric label (e.g. "Total Scans", "Compliance Rate") */
  label: string
  /** Metric value to display */
  value: React.ReactNode
  /** Optional icon displayed in header */
  icon?: LucideIcon
  /** Optional footnote or context hint (e.g. "+5% vs yesterday") */
  hint?: string
  /** Semantic visual tone adding subtle accent from verdict tokens */
  tone?: StatTone
  /** Whether the card is in loading state (renders skeleton for value) */
  loading?: boolean
  className?: string
}

const toneCardClasses: Record<StatTone, string> = {
  default: 'border-border',
  compliant: 'border-l-4 border-l-verdict-compliant border-border',
  violation: 'border-l-4 border-l-verdict-violation border-border',
  uncertain: 'border-l-4 border-l-verdict-uncertain border-border',
}

const toneIconClasses: Record<StatTone, string> = {
  default: 'text-muted-foreground',
  compliant: 'text-verdict-compliant bg-verdict-compliant/10',
  violation: 'text-verdict-violation bg-verdict-violation/10',
  uncertain: 'text-verdict-uncertain bg-verdict-uncertain/10',
}

/**
 * StatCard:
 * Key performance indicator card featuring a metric value, label, optional icon,
 * semantic color tone accents, and loading skeleton support.
 */
export function StatCard({
  label,
  value,
  icon: Icon,
  hint,
  tone = 'default',
  loading = false,
  className,
}: StatCardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border bg-card p-5 shadow-sm text-card-foreground transition-all space-y-2',
        toneCardClasses[tone],
        className,
      )}
      data-testid="stat-card"
      data-tone={tone}
    >
      <div className="flex items-center justify-between text-muted-foreground">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        {Icon && (
          <div
            className={cn(
              'flex size-8 items-center justify-center rounded-md',
              toneIconClasses[tone],
            )}
            aria-hidden="true"
          >
            <Icon className="size-4" />
          </div>
        )}
      </div>

      <div className="pt-1">
        {loading ? (
          <Skeleton className="h-8 w-24 rounded" data-testid="stat-card-skeleton" />
        ) : (
          <div className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            {value}
          </div>
        )}
      </div>

      {hint && <p className="text-xs text-muted-foreground pt-0.5">{hint}</p>}
    </div>
  )
}
