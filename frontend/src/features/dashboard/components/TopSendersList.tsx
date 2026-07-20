import type { TopSender } from '@/types/api'

/**
 * Ranked magnitude, one series.
 *
 * Every bar is the same hue. Senders are a nominal category with no natural
 * order, so shading them by value would double-encode length as lightness —
 * spending the only free channel on information the bar already carries.
 *
 * No legend: a single series is named by the section title, and a one-swatch
 * legend box would just restate it.
 *
 * Counts sit on the label line rather than at the bar tip. Email addresses are
 * long and the panel is narrow, so a tip-anchored label would collide with the
 * name or get clipped — which is worse than moving it.
 */
export function TopSendersList({ senders }: { senders: TopSender[] }) {
  if (senders.length === 0) {
    return (
      <p className="text-xs text-ink-500 dark:text-ink-400">
        No matched senders in this window.
      </p>
    )
  }

  // Scale against the leader, not the total: the comparison that matters here
  // is between senders, not each sender's share of everything.
  const max = Math.max(...senders.map((sender) => sender.count))

  return (
    <ul className="space-y-2">
      {senders.map((sender) => (
        <li key={sender.sender}>
          <div className="flex items-baseline justify-between gap-2">
            <span
              className="min-w-0 truncate text-xs text-ink-700 dark:text-ink-300"
              title={sender.sender}
            >
              {sender.sender}
            </span>
            <span className="shrink-0 text-xs font-medium tabular-nums">
              {sender.count}
            </span>
          </div>
          <div className="mt-1 h-1.5 w-full">
            <div
              className="h-full"
              style={{
                width: `${(sender.count / max) * 100}%`,
                backgroundColor: 'var(--viz-progress)',
                // Square at the baseline, rounded at the data end.
                borderRadius: '0 4px 4px 0',
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}
