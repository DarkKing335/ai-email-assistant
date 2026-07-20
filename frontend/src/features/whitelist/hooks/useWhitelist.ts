import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { whitelistApi } from '@/services/api'
import type { ListWhitelistParams } from '@/services/api/whitelist'
import type { WhitelistEntryCreate, WhitelistEntryUpdate } from '@/types/api'
import { queryKeys } from '@/utils/queryKeys'

export function useWhitelistList(params: ListWhitelistParams) {
  return useQuery({
    queryKey: queryKeys.whitelist.list(params),
    queryFn: () => whitelistApi.listWhitelist(params),
    // Hold the current page on screen while the next one loads, instead of
    // collapsing to a skeleton and jumping the scroll position.
    placeholderData: (previous) => previous,
  })
}

/**
 * Every whitelist write invalidates two things.
 *
 * The backend clears its own in-memory match cache on write, but that is a
 * different cache from this one — the client has to be told separately. The
 * dashboard is included because `active_whitelist_entries` moves with every
 * create and delete.
 */
function useInvalidateWhitelist() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.whitelist.all })
    void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all })
  }
}

export function useCreateWhitelistEntry() {
  const invalidate = useInvalidateWhitelist()
  return useMutation({
    mutationFn: (payload: WhitelistEntryCreate) =>
      whitelistApi.createWhitelistEntry(payload),
    onSuccess: invalidate,
  })
}

export function useUpdateWhitelistEntry() {
  const invalidate = useInvalidateWhitelist()
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: WhitelistEntryUpdate }) =>
      whitelistApi.updateWhitelistEntry(id, patch),
    onSuccess: invalidate,
  })
}

export function useDeleteWhitelistEntry() {
  const invalidate = useInvalidateWhitelist()
  return useMutation({
    mutationFn: (id: number) => whitelistApi.deleteWhitelistEntry(id),
    onSuccess: invalidate,
  })
}

export function useImportWhitelist() {
  const invalidate = useInvalidateWhitelist()
  return useMutation({
    mutationFn: (file: File) => whitelistApi.importWhitelist(file),
    onSuccess: invalidate,
  })
}
