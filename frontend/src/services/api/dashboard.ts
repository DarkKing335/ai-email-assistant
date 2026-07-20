/** Mirrors `src/auto_reply/api/dashboard_router.py`. */

import http from '@/services/http'
import { API_PREFIX } from '@/services/config'
import type { DashboardSummary } from '@/types/api'

const BASE = `${API_PREFIX}/auto-reply/dashboard`

/** `since_hours` is clamped to 1–8760 by the backend; default 24. */
export async function getDashboardSummary(
  sinceHours = 24,
): Promise<DashboardSummary> {
  const { data } = await http.get<DashboardSummary>(`${BASE}/summary`, {
    params: { since_hours: sinceHours },
  })
  return data
}
