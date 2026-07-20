import { useQuery } from '@tanstack/react-query'

import { draftsApi, logsApi } from '@/services/api'
import type { LogQueryParams } from '@/types/api'
import { queryKeys } from '@/utils/queryKeys'

export function useLogsList(params: LogQueryParams) {
  return useQuery({
    queryKey: queryKeys.logs.list(params),
    queryFn: () => logsApi.listLogs(params),
    // Keeps the current page visible while the next one loads, so changing
    // filters does not flash a skeleton and lose the scroll position.
    placeholderData: (previous) => previous,
  })
}

/**
 * `retry_count` exists on the ORM model but the list endpoint does not return
 * it — this per-log call is the only place it surfaces. Fetched lazily when a
 * row is expanded rather than N times up front, which is exactly the N+1 the
 * plan warns about for the Inbox.
 */
export function useProcessingStatus(logId: number, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.drafts.processingStatus(logId),
    queryFn: () => draftsApi.getProcessingStatus(logId),
    enabled,
  })
}
