/** Mirrors `src/auto_reply/api/draft_router.py`. */

import http from '@/services/http'
import { API_PREFIX } from '@/services/config'
import type { GeneratedDraft, ProcessingStatus } from '@/types/api'

const BASE = `${API_PREFIX}/auto-reply`

/** The only place `retry_count` is exposed — the logs list omits it. */
export async function getProcessingStatus(
  logId: number,
): Promise<ProcessingStatus> {
  const { data } = await http.get<ProcessingStatus>(`${BASE}/status/${logId}`)
  return data
}

export async function getDraft(draftId: number): Promise<GeneratedDraft> {
  const { data } = await http.get<GeneratedDraft>(`${BASE}/drafts/${draftId}`)
  return data
}

/** Version history for a log, oldest first. Empty array if none were generated. */
export async function listDraftHistory(
  logId: number,
): Promise<GeneratedDraft[]> {
  const { data } = await http.get<GeneratedDraft[]>(
    `${BASE}/logs/${logId}/drafts`,
  )
  return data
}
