import { useState } from 'react'

import { Button, StatusBadge } from '@/components/ui'
import type { InboxItem } from '@/types/api'
import { formatDateTime, formatRelativeTime } from '@/utils/date'
import { buildGmailThreadUrl, openGmailThread } from '@/utils/gmailLink'

import { DraftSection } from './DraftSection'
import { SummaryView } from './SummaryView'

/** Signals that the action leaves the panel, so the label is not read as
 *  "expand further". Decorative — the `title` carries the meaning. */
function ExternalLinkIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-3"
      aria-hidden
    >
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
      <path d="M21 14v7H3V3h7" />
    </svg>
  )
}

/**
 * One email: sender and subject collapsed, summary and draft when expanded.
 *
 * Collapsed by default because the panel is narrow and a screen of full
 * summaries is unreadable — scanning senders is how people find the one they
 * care about.
 */
export function EmailCard({ item }: { item: InboxItem }) {
  const [isExpanded, setExpanded] = useState(false)

  const hasContent = item.summary !== null || item.latest_draft !== null

  // Closes out the summary when there is one. Without a summary there is no
  // Action items list to sit under, so it falls back to the foot of the card —
  // a failed email is exactly the one worth opening in Gmail.
  const detailsButton = (
    <Button
      size="sm"
      variant="secondary"
      title="Open this thread in Gmail"
      onClick={() => openGmailThread(buildGmailThreadUrl(item))}
    >
      See details
      <ExternalLinkIcon />
    </Button>
  )

  return (
    <li className="rounded-lg border border-ink-200 dark:border-ink-800">
      <button
        type="button"
        aria-expanded={isExpanded}
        onClick={() => setExpanded((open) => !open)}
        className="w-full rounded-lg p-2.5 text-left hover:bg-brand-50 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ink-400 dark:hover:bg-ink-900/50"
      >
        <div className="flex items-start justify-between gap-2">
          <span className="min-w-0 truncate text-sm font-medium">
            {item.sender_name || item.sender_email}
          </span>
          <StatusBadge status={item.status} />
        </div>

        <p className="mt-0.5 truncate text-xs text-ink-600 dark:text-ink-400">
          {item.subject || <span className="italic">(no subject)</span>}
        </p>

        <p
          className="mt-1 text-xs text-ink-500 dark:text-ink-400"
          title={formatDateTime(item.received_at)}
        >
          {formatRelativeTime(item.received_at)}
        </p>
      </button>

      {isExpanded && (
        <div className="space-y-3 border-t border-ink-100 px-2.5 py-2.5 dark:border-ink-800">
          {item.summary && (
            <SummaryView summary={item.summary} footer={detailsButton} />
          )}

          {item.latest_draft && (
            <DraftSection
              draft={item.latest_draft}
              versionCount={item.draft_count}
              threadIds={item}
            />
          )}

          {item.error_detail && (
            <div>
              <p className="text-xs font-medium text-red-700 dark:text-red-300">
                Error
              </p>
              <p className="mt-0.5 font-mono text-xs break-words text-red-600 dark:text-red-400">
                {item.error_detail}
              </p>
            </div>
          )}

          {/*
            Reaching here means the email matched a rule but produced neither a
            summary nor a draft — in flight, or processed before summaries were
            persisted. Saying so beats an empty panel.
          */}
          {!hasContent && !item.error_detail && (
            <p className="text-xs leading-relaxed text-ink-500 dark:text-ink-400">
              {item.status === 'pending' || item.status === 'processing'
                ? 'Still being processed — the summary and draft appear when it finishes.'
                : 'No summary was stored for this email. It was processed before summaries were kept.'}
            </p>
          )}

          {/* Only when the summary did not already carry it. The rule is
              summary-first, so this never renders twice. */}
          {!item.summary && (
            <div className="flex justify-start border-t border-ink-100 pt-2.5 dark:border-ink-800">
              {detailsButton}
            </div>
          )}
        </div>
      )}
    </li>
  )
}
