/**
 * One import site for every backend call.
 *
 * Keeping this barrel 1:1 with the backend routers is what makes adding auth
 * later a one-interceptor change rather than a thirty-component one.
 *
 * Not here yet, because the endpoints do not exist:
 *   - `inbox.ts`     → GET /auto-reply/inbox?since=   (log + summary + draft)
 *   - `summaries.ts` → summaries are generated and discarded, never persisted
 */

export * as dashboardApi from './dashboard'
export * as draftsApi from './drafts'
export * as gmailAuthApi from './gmailAuth'
export * as inboxApi from './inbox'
export * as healthApi from './health'
export * as logsApi from './logs'
export * as whitelistApi from './whitelist'
