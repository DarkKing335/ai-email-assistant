import type { ReactNode } from 'react'

import type { ExecutionStatus } from '@/types/api'

export type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info'

const TONE_CLASSES: Record<Tone, string> = {
  neutral:
    'bg-ink-100 text-ink-700 dark:bg-ink-800 dark:text-ink-300',
  success:
    'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300',
  warning:
    'bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300',
  danger: 'bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300',
  info: 'bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300',
}

export function Badge({
  tone = 'neutral',
  children,
  className = '',
}: {
  tone?: Tone
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap ${TONE_CLASSES[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

/**
 * `skipped` is deliberately neutral rather than a warning: it means the sender
 * simply was not on the whitelist, which is the expected outcome for most mail,
 * not a problem to draw attention to.
 */
export const STATUS_TONES: Record<ExecutionStatus, Tone> = {
  pending: 'neutral',
  processing: 'info',
  completed: 'success',
  failed: 'danger',
  skipped: 'neutral',
}

export function StatusBadge({ status }: { status: ExecutionStatus }) {
  return <Badge tone={STATUS_TONES[status]}>{status}</Badge>
}
