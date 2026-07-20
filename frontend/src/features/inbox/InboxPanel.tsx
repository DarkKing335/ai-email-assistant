import { useEffect, useState } from 'react'

import {
  EmptyState,
  ErrorState,
  Pagination,
  SkeletonList,
} from '@/components/ui'
import { SectionHeader } from '@/layouts/SectionHeader'
import { markSeenNow } from '@/utils/lastSeen'

import { EmailCard } from './components/EmailCard'
import { useInbox } from './hooks/useInbox'

const PAGE_SIZE = 25

export function InboxPanel() {
  const [page, setPage] = useState(1)
  const query = useInbox({ page, page_size: PAGE_SIZE })

  /**
   * This is now where newly processed mail is reviewed, so viewing it is what
   * "seeing" means — the watermark advances and the badge clears here rather
   * than in Logs.
   */
  useEffect(() => {
    void markSeenNow()
  }, [])

  return (
    <div className="space-y-3">
      <SectionHeader
        title="Inbox"
        description="Whitelisted emails, with their summary and draft reply."
      />

      {query.isPending && <SkeletonList rows={5} />}

      {query.isError && (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      )}

      {query.isSuccess && query.data.items.length === 0 && (
        <EmptyState
          title="Nothing here yet"
          description="Emails from whitelisted senders appear here once they have been summarised. Senders that match no rule stay in Logs."
        />
      )}

      {query.isSuccess && query.data.items.length > 0 && (
        <>
          <ul className="space-y-2">
            {query.data.items.map((item) => (
              <EmailCard key={item.id} item={item} />
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
