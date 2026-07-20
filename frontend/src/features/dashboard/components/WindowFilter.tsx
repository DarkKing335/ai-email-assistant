/**
 * One filter row, above everything it scopes.
 *
 * Both the stat tiles and the two charts re-render against the same slice —
 * per-chart date controls would let two figures on one screen describe
 * different periods.
 */
const WINDOWS = [
  { hours: 1, label: '1h' },
  { hours: 6, label: '6h' },
  { hours: 12, label: '12h' },
  { hours: 24, label: '24h' },
]

export function WindowFilter({
  value,
  onChange,
}: {
  value: number
  onChange: (hours: number) => void
}) {
  return (
    <div role="group" aria-label="Time window" className="flex gap-1">
      {WINDOWS.map((window) => {
        const isActive = window.hours === value
        return (
          <button
            key={window.hours}
            type="button"
            aria-pressed={isActive}
            onClick={() => onChange(window.hours)}
            className={`rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-400 ${
              isActive
                ? 'border-ink-900 bg-ink-900 text-white dark:border-ink-100 dark:bg-ink-100 dark:text-ink-900'
                : 'border-ink-300 text-ink-600 hover:bg-brand-50 dark:border-ink-700 dark:text-ink-400 dark:hover:bg-ink-800'
            }`}
          >
            {window.label}
          </button>
        )
      })}
    </div>
  )
}
