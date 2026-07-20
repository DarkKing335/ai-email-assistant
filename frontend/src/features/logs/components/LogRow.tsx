import { useState } from 'react'

import { StatusBadge } from '@/components/ui'
import type { MatchLog } from '@/types/api'
import { formatDateTime, formatRelativeTime } from '@/utils/date'
import { formatDuration } from '@/utils/format'

import { useProcessingStatus } from '../hooks/useLogs'

/** Explains a status whose meaning is not obvious from the word alone. */
function StatusNote({ log }: { log: MatchLog }) {
  if (log.status === 'skipped') {
    return (
      <p className="text-xs text-ink-500 dark:text-ink-400">
        The sender matched no whitelist rule, so nothing was drafted. This is
        the normal outcome for most mail.
      </p>
    )
  }
  if (log.status === 'pending') {
    return (
      <p className="text-xs text-ink-500 dark:text-ink-400">
        Queued — the background worker has not picked this up yet.
      </p>
    )
  }
  return null
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-ink-500 dark:text-ink-400">{label}</dt>
      <dd className="font-mono break-all">{value}</dd>
    </>
  )
}

export function LogRow({ log }: { log: MatchLog }) {
  const [isExpanded, setExpanded] = useState(false)

  // Only fires once the row is opened.
  const status = useProcessingStatus(log.id, isExpanded)

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
            {log.sender_email}
          </span>
          <StatusBadge status={log.status} />
        </div>

        <p className="mt-0.5 truncate text-xs text-ink-600 dark:text-ink-400">
          {log.subject || <span className="italic">(no subject)</span>}
        </p>

        {/* The reason a row failed is the most useful thing about it, so a
            single line of it shows without expanding. */}
        {log.status === 'failed' && log.error_detail && (
          <p className="mt-1 line-clamp-1 text-xs text-red-600 dark:text-red-400">
            {log.error_detail}
          </p>
        )}

        <p
          className="mt-1 text-xs text-ink-500 dark:text-ink-400"
          title={formatDateTime(log.received_at)}
        >
          {formatRelativeTime(log.received_at)}
          {log.processing_ms !== null && ` · ${formatDuration(log.processing_ms)}`}
        </p>
      </button>

      {isExpanded && (
        <div className="space-y-2 border-t border-ink-100 px-2.5 py-2 dark:border-ink-800">
          <StatusNote log={log} />

          {log.error_detail && (
            <div>
              <p className="text-xs font-medium text-red-700 dark:text-red-300">
                Error
              </p>
              <p className="mt-0.5 font-mono text-xs break-words text-red-600 dark:text-red-400">
                {log.error_detail}
              </p>
            </div>
          )}

          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
            <DetailRow
              label="Matched"
              value={log.matched_rule ?? 'no rule matched'}
            />
            <DetailRow label="Received" value={formatDateTime(log.received_at)} />
            {log.processed_at && (
              <DetailRow
                label="Processed"
                value={formatDateTime(log.processed_at)}
              />
            )}
            <DetailRow label="Message" value={log.gmail_message_id} />
            {/* Not in the list response — worth the extra request only here. */}
            {status.isSuccess && (
              <DetailRow label="Retries" value={String(status.data.retry_count)} />
            )}
          </dl>
        </div>
      )}
    </li>
  )
}
