import type { ExecutionStatus } from '@/types/api'

/**
 * The plan's design lists four filters (all / completed / failed / skipped).
 * Pending and processing are included anyway: without them there is no way to
 * see work that is in flight, and "my email vanished" during a demo is almost
 * always a log sitting in `pending`. The row scrolls rather than wraps.
 */
const OPTIONS: { value: ExecutionStatus | undefined; label: string }[] = [
  { value: undefined, label: 'All' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'skipped', label: 'Skipped' },
  { value: 'pending', label: 'Pending' },
  { value: 'processing', label: 'Processing' },
]

export function StatusFilterTabs({
  value,
  onChange,
}: {
  value: ExecutionStatus | undefined
  onChange: (status: ExecutionStatus | undefined) => void
}) {
  return (
    <div
      role="group"
      aria-label="Filter by status"
      className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1"
    >
      {OPTIONS.map((option) => {
        const isActive = option.value === value
        return (
          <button
            key={option.label}
            type="button"
            aria-pressed={isActive}
            onClick={() => onChange(option.value)}
            className={`rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-400 ${
              isActive
                ? 'border-ink-900 bg-ink-900 text-white dark:border-ink-100 dark:bg-ink-100 dark:text-ink-900'
                : 'border-ink-300 text-ink-600 hover:bg-brand-50 dark:border-ink-700 dark:text-ink-400 dark:hover:bg-ink-800'
            }`}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
