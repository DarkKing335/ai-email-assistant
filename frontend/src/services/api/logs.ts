/** Mirrors `src/auto_reply/api/log_router.py`. */

import http from '@/services/http'
import { API_PREFIX } from '@/services/config'
import type { LogQueryParams, MatchLog, Paginated } from '@/types/api'

const BASE = `${API_PREFIX}/auto-reply/logs`

export async function listLogs(
  params: LogQueryParams = {},
): Promise<Paginated<MatchLog>> {
  const { data } = await http.get<Paginated<MatchLog>>(BASE, { params })
  return data
}

/**
 * Count of logs received since `since` — the badge number.
 *
 * Asks for a single row and reads `total`, since only the count is needed.
 * There is no unread concept in the backend; "new" is entirely a client-side
 * notion built on a stored `lastSeenAt` (step 8).
 */
export async function countLogsSince(since: string): Promise<number> {
  const { data } = await http.get<Paginated<MatchLog>>(BASE, {
    params: { date_from: since, page_size: 1 },
  })
  return data.total
}
