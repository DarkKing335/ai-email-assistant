/** Mirrors `src/auto_reply/api/inbox_router.py`. */

import http from '@/services/http'
import { API_PREFIX } from '@/services/config'
import type { InboxItem, Paginated } from '@/types/api'

const BASE = `${API_PREFIX}/auto-reply/inbox`

export type InboxParams = {
  /** ISO-8601. Only emails received after this instant. */
  since?: string
  page?: number
  page_size?: number
  /**
   * Skipped emails have no summary or draft — nothing for this view to show.
   * Excluded by default; the Logs tab is where they belong.
   */
  include_skipped?: boolean
}

export async function getInbox(
  params: InboxParams = {},
): Promise<Paginated<InboxItem>> {
  const { data } = await http.get<Paginated<InboxItem>>(BASE, { params })
  return data
}
