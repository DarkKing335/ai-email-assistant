/**
 * Plain-fetch client — **service worker only**.
 *
 * Exists because axios cannot run in an MV3 service worker (see `http.ts`).
 * Produces the same `ApiError` values as the axios client, so error handling is
 * identical on both sides.
 *
 * Keep this dependency-free: the worker bundle should stay small enough to
 * start quickly, since MV3 tears it down after ~30s idle and restarts it on
 * every alarm.
 */

import {
  buildApiUrl,
  getApiBaseUrl,
  REQUEST_TIMEOUT_MS,
  type QueryParams,
} from './config'
import { apiErrorFromPayload, networkError, timeoutError } from './errors'

type FetchJsonOptions = {
  params?: QueryParams
  signal?: AbortSignal
  timeoutMs?: number
}

export async function fetchJson<T>(
  path: string,
  options: FetchJsonOptions = {},
): Promise<T> {
  const { params, signal, timeoutMs = REQUEST_TIMEOUT_MS } = options
  const url = buildApiUrl(path, params)

  // AbortSignal.timeout() would be tidier but is not available in every Chrome
  // version this targets (114+), so the controller is wired up by hand.
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort('timeout'), timeoutMs)

  const onExternalAbort = () => controller.abort(signal?.reason)
  signal?.addEventListener('abort', onExternalAbort, { once: true })

  let response: Response
  try {
    response = await fetch(url, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
  } catch (error) {
    if (controller.signal.reason === 'timeout') {
      throw timeoutError(getApiBaseUrl())
    }
    // A caller-initiated abort is not an error worth normalising — let it
    // propagate so cancellation stays distinguishable from failure.
    if (signal?.aborted) throw error
    throw networkError(getApiBaseUrl(), error)
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', onExternalAbort)
  }

  const requestId = response.headers.get('x-request-id')

  if (!response.ok) {
    // The error body may not be JSON (proxy HTML, empty 502). Failing to parse
    // it must not mask the real status.
    let payload: unknown = null
    try {
      payload = await response.json()
    } catch {
      payload = null
    }
    throw apiErrorFromPayload(response.status, payload, requestId)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
