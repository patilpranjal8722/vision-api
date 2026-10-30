import type { LucideIcon } from 'lucide-react'
import { ShieldCheck, ShieldAlert, ShieldQuestion } from 'lucide-react'

export type Verdict = 'compliant' | 'violation' | 'uncertain'

export interface VerdictMeta {
  readonly label: string
  readonly description: string
  readonly icon: LucideIcon
  readonly badgeClassName: string
  readonly textClassName: string
  readonly borderClassName: string
  readonly bgClassName: string
  readonly cssVar: string
}

/**
 * Metadata and design tokens for each PPE compliance verdict.
 * Colors are linked directly to semantic F1 CSS variables defined in globals.css.
 */
export const VERDICT_META: Record<Verdict, VerdictMeta> = {
  compliant: {
    label: 'Compliant',
    description: 'Compliant means all required PPE items are detected and properly worn.',
    icon: ShieldCheck,
    badgeClassName:
      'bg-verdict-compliant/15 text-verdict-compliant border-verdict-compliant/30 dark:bg-verdict-compliant/20',
    textClassName: 'text-verdict-compliant',
    borderClassName: 'border-verdict-compliant',
    bgClassName: 'bg-verdict-compliant',
    cssVar: '--verdict-compliant',
  },
  violation: {
    label: 'Violation',
    description: 'Violation means one or more required PPE items are missing.',
    icon: ShieldAlert,
    badgeClassName:
      'bg-verdict-violation/15 text-verdict-violation border-verdict-violation/30 dark:bg-verdict-violation/20',
    textClassName: 'text-verdict-violation',
    borderClassName: 'border-verdict-violation',
    bgClassName: 'bg-verdict-violation',
    cssVar: '--verdict-violation',
  },
  uncertain: {
    label: 'Uncertain',
    description: 'Uncertain means the worker is partly hidden and needs a human check.',
    icon: ShieldQuestion,
    badgeClassName:
      'bg-verdict-uncertain/15 text-verdict-uncertain border-verdict-uncertain/30 dark:bg-verdict-uncertain/20',
    textClassName: 'text-verdict-uncertain',
    borderClassName: 'border-verdict-uncertain',
    bgClassName: 'bg-verdict-uncertain',
    cssVar: '--verdict-uncertain',
  },
} as const

/** Ordered list of verdicts for display and legends */
export const VERDICT_ORDER: readonly Verdict[] = [
  'compliant',
  'violation',
  'uncertain',
] as const

/**
 * Returns metadata for a given verdict, defaulting safely to uncertain if an unexpected string is passed.
 */
export function getVerdictMeta(verdict: Verdict): VerdictMeta {
  return VERDICT_META[verdict] ?? VERDICT_META.uncertain
}
