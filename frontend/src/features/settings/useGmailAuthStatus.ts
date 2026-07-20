import { useQuery } from '@tanstack/react-query'

import { gmailAuthApi } from '@/services/api'

export const GMAIL_STATUS_KEY = ['gmailAuth', 'status'] as const

/**
 * Shared because two places depend on it: the settings row, and the gate that
 * decides whether the rest of the panel renders at all. One query key means
 * both read the same cache entry and only one request is in flight.
 */
export function useGmailAuthStatus() {
  return useQuery({
    queryKey: GMAIL_STATUS_KEY,
    queryFn: gmailAuthApi.getGmailAuthStatus,
    // The connection happens in another tab, so this polls to notice it
    // completing rather than making the user come back and refresh.
    refetchInterval: 5000,
  })
}
