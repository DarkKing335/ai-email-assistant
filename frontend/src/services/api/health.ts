import http from '@/services/http'
import type { HealthResponse } from '@/types/api'

/**
 * Unversioned — `/health` sits outside `/api/v1`.
 *
 * The cheapest end-to-end probe there is: it exercises host permissions, the
 * base URL, CORS and the error normaliser without touching the database.
 */
export async function getHealth(): Promise<HealthResponse> {
  const { data } = await http.get<HealthResponse>('/health')
  return data
}
