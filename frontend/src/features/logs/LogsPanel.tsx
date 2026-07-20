import { useEffect, useState } from 'react'

import {
  EmptyState,
  ErrorState,
  Pagination,
  SkeletonList,
} from '@/components/ui'
import { SectionHeader } from '@/layouts/SectionHeader'
import type { ExecutionStatus } from '@/types/api'
import { markSeenNow } from '@/utils/lastSeen'

import { LogRow } from './components/LogRow'
import { StatusFilterTabs } from './components/StatusFilterTabs'
import { useLogsList } from './hooks/useLogs'

const PAGE_SIZE = 25

const EMPTY_COPY: Record<string, { title: string; description: string }> = {
  all: {
    title: 'Nothing processed yet',
    description:
      'Every inbound email checked against the whitelist shows up here, matched or not.',
  },
  completed: {
    title: 'No completed runs',
    description: 'Nothing has made it all the way to a generated draft yet.',
  },
  failed: {
    title: 'No failures',
    description: 'Nothing has errored in this window.',
  },
  skipped: {
    title: 'Nothing skipped',
    description: 'Every email so far matched a whitelist rule.',
  },
  pending: {
    title: 'Nothing queued',
    description: 'The worker has picked up everything that arrived.',
  },
  processing: {
    title: 'Nothing in flight',
    description: 'No email is being processed right now.',
  },
}

export function LogsPanel() {
  const [status, setStatus] = useState<ExecutionStatus | undefined>(undefined)
  const [page, setPage] = useState(1)

  const query = useLogsList({
    page,
    page_size: PAGE_SIZE,
    status_filter: status,
  })

  /**
   * Also marks mail as seen. Logs is a superset of Inbox (it includes skipped
   * and failed rows), so reaching this screen means the new arrivals have been
   * looked at just as much as opening Inbox does.
   */
  useEffect(() => {
    void markSeenNow()
  }, [])

  function handleStatusChange(next: ExecutionStatus | undefined) {
    setStatus(next)
    // Page 3 of "all" is rarely a valid page of "failed".
    setPage(1)
  }

  const empty = EMPTY_COPY[status ?? 'all']

  return (
    <div className="space-y-3">
      <SectionHeader
        title="Logs"
        description="Every inbound email checked against the whitelist."
      />

      <StatusFilterTabs value={status} onChange={handleStatusChange} />

      {query.isPending && <SkeletonList rows={6} />}

      {query.isError && (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      )}

      {query.isSuccess && query.data.items.length === 0 && (
        <EmptyState title={empty.title} description={empty.description} />
      )}

      {query.isSuccess && query.data.items.length > 0 && (
        <>
          <ul className="space-y-2">
            {query.data.items.map((log) => (
              <LogRow key={log.id} log={log} />
            ))}
          </ul>

          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={query.data.total}
            isFetching={query.isFetching}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  )
}
