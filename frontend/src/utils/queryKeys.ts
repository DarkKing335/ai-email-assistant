/**
 * Every TanStack Query key in the app, in one place.
 *
 * Defined as a tree so a prefix invalidates its children: invalidating
 * `queryKeys.whitelist.all` clears every page and filter combination at once.
 * That matters after a whitelist mutation — the backend drops its own match
 * cache, but the client cache is separate and would otherwise go stale.
 */

import type { ListWhitelistParams } from '@/services/api/whitelist'
import type { LogQueryParams } from '@/types/api'

export const queryKeys = {
  health: ['health'] as const,

  dashboard: {
    all: ['dashboard'] as const,
    summary: (sinceHours: number) =>
      ['dashboard', 'summary', sinceHours] as const,
  },

  inbox: {
    all: ['inbox'] as const,
    list: (params: Record<string, unknown>) => ['inbox', 'list', params] as const,
  },

  logs: {
    all: ['logs'] as const,
    list: (params: LogQueryParams) => ['logs', 'list', params] as const,
    countSince: (since: string) => ['logs', 'countSince', since] as const,
  },

  whitelist: {
    all: ['whitelist'] as const,
    list: (params: ListWhitelistParams) => ['whitelist', 'list', params] as const,
    detail: (id: number) => ['whitelist', 'detail', id] as const,
  },

  drafts: {
    all: ['drafts'] as const,
    detail: (draftId: number) => ['drafts', 'detail', draftId] as const,
    history: (logId: number) => ['drafts', 'history', logId] as const,
    processingStatus: (logId: number) =>
      ['drafts', 'processingStatus', logId] as const,
  },
} as const
