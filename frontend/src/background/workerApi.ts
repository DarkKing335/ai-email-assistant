/**
 * The worker's only backend call.
 *
 * Uses `fetchJson`, **never** `services/http.ts` — axios's browser build is
 * built on `XMLHttpRequest`, which does not exist in a service worker. Keeping
 * the worker's API surface to this one file makes that boundary impossible to
 * cross by accident.
 */

import { fetchJson } from '@/services/fetchClient'
import { API_PREFIX } from '@/services/config'
import type { MatchLog, Paginated } from '@/types/api'

/**
 * Logs received since `since`.
 *
 * Asks for a single row: `total` carries the count for the badge, and
 * `items[0]` is the most recent sender, which makes the notification specific
 * rather than "you have new mail".
 */
export async function fetchNewSince(
  since: string,
): Promise<{ total: number; latest: MatchLog | undefined }> {
  const page = await fetchJson<Paginated<MatchLog>>(
    `${API_PREFIX}/auto-reply/logs`,
    { params: { date_from: since, page_size: 1 } },
  )
  return { total: page.total, latest: page.items[0] }
}
