import { useQuery } from '@tanstack/react-query'

import { healthApi } from '@/services/api'
import { queryKeys } from '@/utils/queryKeys'

/**
 * Background liveness probe for the header indicator.
 *
 * Cheap (no database work) and low-frequency, so it can poll while the panel is
 * open without being noticeable. Its real value is diagnostic: when a panel
 * shows an error, this says whether the backend is reachable at all.
 */
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: healthApi.getHealth,
    refetchInterval: 30_000,
    // Keep polling even while the request is failing, so recovery is picked up
    // without the user having to do anything.
    refetchIntervalInBackground: false,
    retry: false,
    staleTime: 15_000,
  })
}
