import { useState } from 'react'

import { ErrorState, Skeleton } from '@/components/ui'
import { SectionHeader } from '@/layouts/SectionHeader'
import { formatDuration } from '@/utils/format'

import { StatCard } from './components/StatCard'
import { StatusBreakdownBar } from './components/StatusBreakdownBar'
import { TopSendersList } from './components/TopSendersList'
import { WindowFilter } from './components/WindowFilter'
import { useDashboard } from './hooks/useDashboard'

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold tracking-wide uppercase text-ink-500 dark:text-ink-400">
        {title}
      </h3>
      {children}
    </section>
  )
}

export function DashboardPanel() {
  const [sinceHours, setSinceHours] = useState(24)
  const query = useDashboard(sinceHours)

  return (
    <div className="viz-root space-y-4">
      <SectionHeader
        title="Dashboard"
        description="Volume, outcomes and top senders."
      />

      <WindowFilter value={sinceHours} onChange={setSinceHours} />

      {query.isPending && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-[4.5rem]" />
            ))}
          </div>
          <Skeleton className="h-6 w-full" />
        </div>
      )}

      {query.isError && (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      )}

      {query.data && (
        // Refetches hold the previous render and dim it rather than dropping
        // back to skeletons — no layout jump when the window changes or the
        // 30s poll fires.
        <div
          className={`space-y-5 transition-opacity ${
            query.isFetching ? 'opacity-60' : 'opacity-100'
          }`}
        >
          <div className="grid grid-cols-2 gap-2">
            <StatCard label="Inbound" value={query.data.total_inbound_emails} />
            <StatCard label="Matched" value={query.data.matched_whitelist} />
            {/*
              The design asks for a "summarized" count. There is none: summaries
              are generated and discarded, so the backend cannot compute one.
              Drafts generated is the closest true figure.
            */}
            <StatCard
              label="Drafts"
              value={query.data.total_drafts_generated}
            />
            <StatCard label="Failed" value={query.data.failed_generation} />
          </div>

          <Section title="Outcomes">
            <StatusBreakdownBar breakdown={query.data.status_breakdown} />
          </Section>

          <Section title="Top senders">
            <TopSendersList senders={query.data.top_senders} />
          </Section>

          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-ink-200 pt-3 text-xs dark:border-ink-800">
            <dt className="text-ink-500 dark:text-ink-400">
              Avg processing
            </dt>
            <dd className="text-right font-medium tabular-nums">
              {query.data.avg_processing_ms === null
                ? '—'
                : formatDuration(query.data.avg_processing_ms)}
            </dd>
            <dt className="text-ink-500 dark:text-ink-400">Active rules</dt>
            <dd className="text-right font-medium tabular-nums">
              {query.data.active_whitelist_entries}
            </dd>
            <dt className="text-ink-500 dark:text-ink-400">Unmatched</dt>
            <dd className="text-right font-medium tabular-nums">
              {query.data.unmatched}
            </dd>
          </dl>
        </div>
      )}
    </div>
  )
}
