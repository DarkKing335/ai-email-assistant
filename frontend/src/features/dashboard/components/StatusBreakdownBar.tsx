import type { StatusBreakdown } from '@/types/api'

/**
 * Part-to-whole: one horizontal stacked bar.
 *
 * `pending` and `processing` are merged into a single "In progress" segment.
 * Both mean the same thing to a reader — not finished yet — and at typical
 * counts each would be a sliver too thin to see or hover. The Logs panel has
 * the exact split.
 *
 * `skipped` is rendered as the neutral **track** rather than a hue. It means
 * "matched no rule, so nothing was done", which is the expected outcome for
 * most mail — giving it a saturated colour would make routine mail look like
 * an event. A neutral also keeps the two coloured neighbours (blue and red)
 * from touching.
 *
 * `rate_limited` is deliberately not rendered: `ExecutionStatus` has no such
 * member, so the backend cannot ever increment it. It is shown only if it
 * somehow becomes non-zero, which would mean the backend grew a new state.
 */

type Segment = {
  key: string
  label: string
  count: number
  color: string
  /** Whether the swatch needs a ring to be visible against the surface. */
  isNeutral?: boolean
}

export function StatusBreakdownBar({
  breakdown,
}: {
  breakdown: StatusBreakdown
}) {
  const inProgress = breakdown.pending + breakdown.processing

  const segments: Segment[] = [
    {
      key: 'completed',
      label: 'Completed',
      count: breakdown.completed,
      color: 'var(--viz-completed)',
    },
    {
      key: 'progress',
      label: 'In progress',
      count: inProgress,
      color: 'var(--viz-progress)',
    },
    {
      key: 'skipped',
      label: 'Skipped',
      count: breakdown.skipped,
      color: 'var(--viz-skipped)',
      isNeutral: true,
    },
    {
      key: 'failed',
      label: 'Failed',
      count: breakdown.failed,
      color: 'var(--viz-failed)',
    },
  ]

  if (breakdown.rate_limited > 0) {
    segments.push({
      key: 'rate_limited',
      label: 'Rate limited',
      count: breakdown.rate_limited,
      color: 'var(--viz-failed)',
    })
  }

  const total = segments.reduce((sum, segment) => sum + segment.count, 0)
  if (total === 0) {
    return (
      <p className="text-xs text-ink-500 dark:text-ink-400">
        Nothing processed in this window.
      </p>
    )
  }

  const visible = segments.filter((segment) => segment.count > 0)
  const percent = (count: number) => (count / total) * 100

  return (
    <div>
      {/*
        24px tall: the mark spec's cap, and also the minimum comfortable hover
        target. Segments are separated by a real 2px flex gap rather than a
        painted divider or a border — the gap is the mechanism, and a real gap
        works on whatever surface the panel happens to be.
      */}
      <div
        className="flex h-6 w-full gap-0.5 overflow-hidden"
        role="img"
        aria-label={visible
          .map((s) => `${s.label} ${s.count}`)
          .join(', ')}
      >
        {visible.map((segment, index) => (
          <div
            key={segment.key}
            title={`${segment.label}: ${segment.count} (${percent(segment.count).toFixed(0)}%)`}
            style={{
              width: `${percent(segment.count)}%`,
              backgroundColor: segment.color,
              // Square at the baseline (left), 4px rounded at the data end.
              borderRadius:
                index === visible.length - 1 ? '0 4px 4px 0' : undefined,
            }}
            className={index === 0 ? 'rounded-l' : undefined}
          />
        ))}
      </div>

      {/*
        The legend doubles as the table view: every value is readable without
        hovering, so the tooltips enhance rather than gate.
      */}
      <ul className="mt-2.5 grid grid-cols-2 gap-x-3 gap-y-1">
        {visible.map((segment) => (
          <li key={segment.key} className="flex items-center gap-1.5 text-xs">
            <span
              aria-hidden
              className={`size-2 shrink-0 rounded-full ${
                segment.isNeutral
                  ? 'ring-1 ring-ink-300 dark:ring-ink-700'
                  : ''
              }`}
              style={{ backgroundColor: segment.color }}
            />
            <span className="truncate text-ink-600 dark:text-ink-400">
              {segment.label}
            </span>
            <span className="ml-auto font-medium tabular-nums">
              {segment.count}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
