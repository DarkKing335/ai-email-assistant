import { useQuery } from '@tanstack/react-query'

import { dashboardApi } from '@/services/api'
import { queryKeys } from '@/utils/queryKeys'

export function useDashboard(sinceHours: number) {
  return useQuery({
    queryKey: queryKeys.dashboard.summary(sinceHours),
    queryFn: () => dashboardApi.getDashboardSummary(sinceHours),
    // Dashboard is one of the two views the plan polls while the panel is open.
    refetchInterval: 30_000,
    // Changing the window holds the old numbers on screen instead of flashing
    // skeletons — no layout jump on refetch.
    placeholderData: (previous) => previous,
  })
}
