import { QueryClient } from '@tanstack/react-query'

import { isApiError } from '@/services/errors'

/**
 * Retry policy comes from the backend, not from us.
 *
 * `ErrorResponse.retryable` is the server's own judgement about whether the
 * same request could succeed on a second attempt — it knows which provider
 * failed and why. A client-side guess would either hammer 409s or give up on
 * transient 502s. Errors without the flag get one derived from their status in
 * `errors.ts`.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (failureCount, error) =>
          isApiError(error) && error.retryable && failureCount < 2,
        // Matches the 30s panel refresh interval, so a tab switch inside that
        // window reuses data instead of refetching.
        staleTime: 30_000,
        // The side panel sits beside Gmail and gains/loses focus constantly;
        // refetching on every focus change would be near-continuous polling.
        refetchOnWindowFocus: false,
      },
      mutations: {
        // A retried POST could create a duplicate whitelist entry. Mutations
        // are re-driven by the user, never automatically.
        retry: false,
      },
    },
  })
}
