import { useQuery } from '@tanstack/react-query'

import { inboxApi } from '@/services/api'
import type { InboxParams } from '@/services/api/inbox'
import { queryKeys } from '@/utils/queryKeys'

export function useInbox(params: InboxParams) {
  return useQuery({
    queryKey: queryKeys.inbox.list(params),
    queryFn: () => inboxApi.getInbox(params),
    // One of the two views the plan polls while the panel is open — this is
    // where newly processed mail shows up.
    refetchInterval: 30_000,
    placeholderData: (previous) => previous,
  })
}
