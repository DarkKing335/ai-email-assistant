import { formatCompact } from '@/utils/format'

/**
 * Stat tile: label (sentence case, no trailing colon) + value.
 *
 * No delta or sparkline — the backend exposes a single aggregate per window,
 * with no prior period or per-day series to compare against. An invented
 * baseline would be worse than none.
 *
 * Values use the font's default proportional figures; `tabular-nums` is for
 * columns that align vertically, and makes a standalone number look loose.
 */
export function StatCard({
  label,
  value,
  hint,
}: {
  label: string
  value: number | string
  hint?: string
}) {
  return (
    <div className="rounded-lg border border-ink-200 p-2.5 dark:border-ink-800">
      <p className="text-xs text-ink-500 dark:text-ink-400">{label}</p>
      <p className="mt-0.5 text-xl font-semibold">
        {typeof value === 'number' ? formatCompact(value) : value}
      </p>
      {hint && (
        <p className="mt-0.5 text-xs text-ink-500 dark:text-ink-400">
          {hint}
        </p>
      )}
    </div>
  )
}
