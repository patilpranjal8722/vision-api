import { cn } from '@/lib/utils'
import { getVerdictMeta, type Verdict } from '@/lib/verdict'

export interface VerdictBadgeProps {
  /** The PPE compliance classification */
  verdict: Verdict
  /** Badge size preset */
  size?: 'sm' | 'md'
  /** Whether to render the leading icon. Defaults to true */
  showIcon?: boolean
  /** Optional custom text override (e.g. "No helmet", "Wearing vest") */
  label?: string
  /** Additional custom class names */
  className?: string
}

/**
 * VerdictBadge:
 * Renders a semantic badge with icon and label for PPE compliance status.
 * Icons are aria-hidden so screen readers consume only the human-readable text.
 */
export function VerdictBadge({
  verdict,
  size = 'md',
  showIcon = true,
  label,
  className,
}: VerdictBadgeProps) {
  const meta = getVerdictMeta(verdict)
  const Icon = meta.icon
  const displayText = label || meta.label

  const sizeClasses =
    size === 'sm'
      ? 'text-xs px-2 py-0.5 gap-1.5 font-medium'
      : 'text-sm px-2.5 py-1 gap-2 font-medium'

  const iconSizeClass = size === 'sm' ? 'size-3.5' : 'size-4'

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border font-sans tracking-wide shrink-0 transition-colors',
        meta.badgeClassName,
        sizeClasses,
        className,
      )}
      data-verdict={verdict}
      data-testid={`verdict-badge-${verdict}`}
    >
      {showIcon && (
        <Icon
          className={cn('shrink-0', iconSizeClass)}
          aria-hidden="true"
          data-slot="verdict-icon"
        />
      )}
      <span className="whitespace-nowrap">{displayText}</span>
    </span>
  )
}
