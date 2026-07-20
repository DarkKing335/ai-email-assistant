import type { ReactNode } from 'react'

/**
 * Shown when a request succeeded but returned nothing.
 *
 * Distinct from `ErrorState` on purpose: a fresh database is the normal case
 * here, not a failure, and it should not look like one.
 */
export function EmptyState({
  media,
  title,
  description,
  action,
}: {
  /** Optional illustration above the title. Decorative — the title still has
   *  to carry the whole message on its own. */
  media?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
      {media && <div className="mb-4">{media}</div>}
      <p className="text-sm font-medium text-ink-700 dark:text-ink-300">
        {title}
      </p>
      {description && (
        <p className="mt-1 max-w-[36ch] text-xs leading-relaxed text-ink-500 dark:text-ink-400">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
