import * as React from 'react'
import type { LucideIcon } from 'lucide-react'
import { Inbox } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface EmptyStateAction {
  label: string
  onClick: () => void
  disabled?: boolean
  variant?: 'default' | 'secondary' | 'outline' | 'ghost'
}

export interface EmptyStateProps {
  /** Leading icon representing the empty entity. Defaults to Inbox */
  icon?: LucideIcon
  /** Primary title explaining why the section is empty */
  title: string
  /** Helpful explanatory text or guidance */
  description: string
  /** Optional action button or custom action node */
  action?: EmptyStateAction | React.ReactNode
  /** Container classes */
  className?: string
}

/**
 * EmptyState:
 * Displayed when lists, tables, or search filters yield zero items.
 * Guides the user with an icon, explanatory copy, and an optional recovery action.
 */
export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  const isActionObject =
    action && typeof action === 'object' && 'label' in action && 'onClick' in action

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card/50 p-8 text-center text-card-foreground sm:p-12',
        className,
      )}
      data-testid="empty-state"
    >
      <div className="flex size-14 items-center justify-center rounded-full bg-muted/60 text-muted-foreground mb-4">
        <Icon className="size-7" aria-hidden="true" />
      </div>

      <h3 className="text-base font-semibold text-foreground tracking-tight sm:text-lg">
        {title}
      </h3>
      <p className="mt-1.5 max-w-sm text-sm text-muted-foreground text-balance">
        {description}
      </p>

      {action && (
        <div className="mt-6">
          {isActionObject ? (
            <Button
              type="button"
              variant={(action as EmptyStateAction).variant ?? 'default'}
              onClick={(action as EmptyStateAction).onClick}
              disabled={(action as EmptyStateAction).disabled}
            >
              {(action as EmptyStateAction).label}
            </Button>
          ) : (
            action
          )}
        </div>
      )}
    </div>
  )
}
