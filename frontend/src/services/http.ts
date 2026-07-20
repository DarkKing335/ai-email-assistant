/**
 * Axios instance — **side panel only**.
 *
 * Do not import this from `src/background/`. Axios's browser build is built on
 * `XMLHttpRequest`, which does not exist in an MV3 service worker; the calls
 * fail at runtime with nothing useful in the stack. The worker uses
 * `fetchClient.ts` instead.
 */

import axios from 'axios'

import { getApiBaseUrl, REQUEST_TIMEOUT_MS } from './config'
import { apiErrorFromPayload, networkError, normalizeError, timeoutError } from './errors'

const http = axios.create({
  timeout: REQUEST_TIMEOUT_MS,
  headers: { Accept: 'application/json' },
})

// Resolved per request so the Settings panel can repoint the base URL without
// recreating the client.
http.interceptors.request.use((config) => {
  config.baseURL = getApiBaseUrl()
  return config
})

// Every rejection leaving this client is an ApiError. Components and query
// hooks never deal with an AxiosError.
http.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (!axios.isAxiosError(error)) {
      return Promise.reject(normalizeError(error))
    }

    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      return Promise.reject(timeoutError(getApiBaseUrl()))
    }

    // No response object at all: server down, DNS failure, or a CORS rejection
    // (which the browser deliberately reports as an opaque network error).
    if (!error.response) {
      return Promise.reject(networkError(getApiBaseUrl(), error))
    }

    const requestId = error.response.headers?.['x-request-id']
    return Promise.reject(
      apiErrorFromPayload(
        error.response.status,
        error.response.data,
        typeof requestId === 'string' ? requestId : null,
      ),
    )
  },
)

export default http
