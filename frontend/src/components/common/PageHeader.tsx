import * as React from 'react'
import { cn } from '@/lib/utils'

export interface PageHeaderProps {
  /** Page primary heading */
  title: string
  /** Explanatory subtext */
  description?: string
  /** Action slot (e.g., buttons, date pickers) right-aligned on wide screens */
  actions?: React.ReactNode
  /** Optional badge rendered alongside the title */
  badge?: React.ReactNode
  /** Optional container class name */
  className?: string
}

/**
 * Reusable page header component providing consistent title, description,
 * status badge, and optional action buttons across dashboard pages.
 */
export function PageHeader({
  title,
  description,
  actions,
  badge,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-4 pb-6 border-b border-border/60 sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
      data-testid="page-header"
    >
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            {title}
          </h1>
          {badge && <div className="inline-flex items-center">{badge}</div>}
        </div>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>

      {actions && (
        <div
          className="flex flex-wrap items-center gap-2.5 sm:justify-end"
          data-testid="page-header-actions"
        >
          {actions}
        </div>
      )}
    </div>
  )
}
