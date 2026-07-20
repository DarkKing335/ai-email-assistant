import type { ReactNode } from 'react'

import { Badge } from '@/components/ui'
import type { EmailSummary } from '@/types/api'

/**
 * The structured summary: overview, key points, action items.
 *
 * Sections render only when they have content — an empty "Action items"
 * heading reads as though something failed, when in fact the email simply
 * asked for nothing.
 */
export function SummaryView({
  summary,
  footer,
}: {
  summary: EmailSummary
  /** Actions closing out the summary. A slot rather than a prop for the link
   *  itself, so this stays a pure presenter and never learns about Gmail. */
  footer?: ReactNode
}) {
  return (
    <div className="space-y-3">
      <div>
        <div className="mb-1 flex items-center gap-1.5">
          <h4 className="text-xs font-semibold tracking-wide uppercase text-ink-500 dark:text-ink-400">
            Summary
          </h4>
          {/* The language of the original email — this is what decides which
              language the draft is written in. */}
          <Badge tone="neutral">{summary.language}</Badge>
          {summary.truncated && (
            <Badge tone="warning" className="ml-auto">
              truncated
            </Badge>
          )}
        </div>
        <p className="text-xs leading-relaxed text-ink-700 dark:text-ink-300">
          {summary.overview}
        </p>
      </div>

      {summary.key_points.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-semibold tracking-wide uppercase text-ink-500 dark:text-ink-400">
            Key points
          </h4>
          <ul className="list-disc space-y-0.5 pl-4">
            {summary.key_points.map((point, index) => (
              <li
                key={index}
                className="text-xs leading-relaxed text-ink-700 dark:text-ink-300"
              >
                {point.text}
              </li>
            ))}
          </ul>
        </div>
      )}

      {summary.action_items.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-semibold tracking-wide uppercase text-ink-500 dark:text-ink-400">
            Action items
          </h4>
          <ul className="space-y-1">
            {summary.action_items.map((item, index) => (
              <li key={index} className="text-xs leading-relaxed">
                <span className="text-ink-700 dark:text-ink-300">
                  {item.task}
                </span>
                {(item.owner || item.deadline) && (
                  <span className="mt-0.5 flex flex-wrap gap-1">
                    {item.owner && <Badge tone="info">{item.owner}</Badge>}
                    {item.deadline && (
                      <Badge tone="warning">{item.deadline}</Badge>
                    )}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {summary.truncated && (
        <p className="text-xs leading-relaxed text-amber-600 dark:text-amber-400">
          The original was too long to summarise in full, so parts of it were
          not read.
        </p>
      )}

      {/* Last, below the truncation caveat rather than above it: that caveat
          qualifies the summary above it, so an action wedged in between would
          split it from what it refers to. */}
      {footer && <div className="flex justify-start">{footer}</div>}
    </div>
  )
}
