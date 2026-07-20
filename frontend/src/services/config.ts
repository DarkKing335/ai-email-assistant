/**
 * Where the backend lives, and how long we wait for it.
 *
 * Held in a module variable rather than a constant because the Settings panel
 * (step 7) hydrates it from `chrome.storage.local` at boot. Both clients read
 * it per request, so a change takes effect without rebuilding anything.
 */

/** 127.0.0.1 rather than localhost: it is what uvicorn binds by default. */
export const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

export const API_PREFIX = '/api/v1'

/**
 * Generous for the endpoints the panel actually calls (whitelist, logs,
 * dashboard — all simple queries). Draft generation is far slower but happens
 * in the backend worker, never on a request the panel is waiting on.
 */
export const REQUEST_TIMEOUT_MS = 15_000

let apiBaseUrl = DEFAULT_API_BASE_URL

function normalizeBaseUrl(url: string): string {
  return url.trim().replace(/\/+$/, '')
}

export function getApiBaseUrl(): string {
  return apiBaseUrl
}

export function setApiBaseUrl(url: string): void {
  apiBaseUrl = normalizeBaseUrl(url) || DEFAULT_API_BASE_URL
}

export type QueryParams = Record<
  string,
  string | number | boolean | undefined | null
>

/** Drops undefined/null so optional filters do not become "?status=undefined". */
export function toQueryString(params: QueryParams = {}): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.append(key, String(value))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

/** Absolute URL. Used by the fetch client; axios composes its own from baseURL. */
export function buildApiUrl(path: string, params?: QueryParams): string {
  return `${getApiBaseUrl()}${path}${toQueryString(params)}`
}
