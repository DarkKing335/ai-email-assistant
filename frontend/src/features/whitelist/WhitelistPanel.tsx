import { useState } from 'react'

import {
  EmptyState,
  ErrorState,
  Pagination,
  SkeletonList,
} from '@/components/ui'
import { SectionHeader } from '@/layouts/SectionHeader'
import { WHITELIST_CACHE_TTL_SECONDS } from '@/types/api'

import { EntryRow } from './components/EntryRow'
import { ImportSection } from './components/ImportSection'
import { QuickAddBar } from './components/QuickAddBar'
import { useWhitelistList } from './hooks/useWhitelist'

const PAGE_SIZE = 25

/**
 * Matching rules people get wrong.
 *
 * Tucked into a `<details>` so it is available without taking up room
 * permanently.
 */
function MatchingRules() {
  return (
    <details className="rounded-lg border border-ink-200 px-3 py-2 dark:border-ink-800">
      <summary className="cursor-pointer text-xs font-medium select-none">
        How matching works
      </summary>
      <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-relaxed text-ink-600 dark:text-ink-400">
        <li>
          An exact address always beats a domain rule. Adding{' '}
          <code className="font-mono">@company.com</code> will not override an
          existing rule for one address at that domain.
        </li>
        <li>
          A value can appear only once, so there is never more than one rule to
          choose between.
        </li>
        <li>
          Changes can take up to {WHITELIST_CACHE_TTL_SECONDS} seconds to affect
          incoming mail — the backend caches matches.
        </li>
      </ul>
    </details>
  )
}

export function WhitelistPanel() {
  const [page, setPage] = useState(1)
  const query = useWhitelistList({ page, page_size: PAGE_SIZE })

  const total = query.data?.total ?? 0

  return (
    <div className="space-y-4">
      <SectionHeader
        title="Whitelist"
        description="Senders and domains that get an automatic draft."
      />

      <QuickAddBar />
      <MatchingRules />

      {query.isPending && <SkeletonList rows={4} />}

      {query.isError && (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      )}

      {query.isSuccess && query.data.items.length === 0 && (
        <EmptyState
          title="No rules yet"
          description="Add an address above, or import a list. Nothing is drafted automatically until something matches."
        />
      )}

      {query.isSuccess && query.data.items.length > 0 && (
        <>
          <ul className="space-y-2">
            {query.data.items.map((entry) => (
              <EntryRow key={entry.id} entry={entry} />
            ))}
          </ul>

          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={total}
            isFetching={query.isFetching}
            onPageChange={setPage}
          />
        </>
      )}

      <div className="border-t border-ink-200 pt-4 dark:border-ink-800">
        <ImportSection />
      </div>
    </div>
  )
}
