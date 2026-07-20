/**
 * One error type for the whole app.
 *
 * The backend speaks two dialects — `{ request_id, code, message, retryable }`
 * from the summarization/routing handlers, and `{ detail: "..." }` from every
 * FastAPI `HTTPException` in the auto_reply routers. A 422 can arrive in either
 * one, depending on whether it came from request validation or a guardrail.
 *
 * Components should never see either shape. Everything funnels through
 * `normalizeError` into `ApiError`.
 */

import type {
  BackendDetailResponse,
  BackendErrorResponse,
} from '@/types/api'

export type ErrorSource =
  /** The backend answered with an error payload. */
  | 'backend'
  /** No response at all — server down, CORS refused, DNS, timeout. */
  | 'network'
  /** We refused to make the call. Never reached the wire. */
  | 'client'

export class ApiError extends Error {
  readonly code: string
  readonly status: number | null
  /**
   * Taken from the backend's own `retryable` flag when it sends one, otherwise
   * derived from the status. Wire TanStack Query to this rather than inventing
   * a client-side retry policy.
   */
  readonly retryable: boolean
  /** From the `X-Request-ID` response header or a shape-A body. For support. */
  readonly requestId: string | null
  readonly source: ErrorSource

  constructor(init: {
    message: string
    code: string
    status?: number | null
    retryable?: boolean
    requestId?: string | null
    source?: ErrorSource
  }) {
    super(init.message)
    this.name = 'ApiError'
    this.code = init.code
    this.status = init.status ?? null
    this.retryable = init.retryable ?? false
    this.requestId = init.requestId ?? null
    this.source = init.source ?? 'backend'
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError
}

// ---------------------------------------------------------------------------
// Status → meaning
// ---------------------------------------------------------------------------

/**
 * Only consulted for shape-B errors, which carry no `retryable` flag.
 * 429 is retryable-with-backoff: the `/gmail/incoming` queue is full, not
 * broken.
 */
function retryableFromStatus(status: number | null): boolean {
  if (status === null) return true
  if (status === 429) return true
  return status >= 500
}

/** Synthesises a stable code for shape-B errors so the UI can switch on it. */
function codeFromStatus(status: number | null): string {
  switch (status) {
    case 400:
      return 'bad_request'
    case 404:
      return 'not_found'
    case 409:
      return 'duplicate'
    case 413:
      return 'payload_too_large'
    case 422:
      return 'validation_error'
    case 429:
      return 'queue_full'
    case 503:
      return 'service_unavailable'
    default:
      return status === null ? 'unknown_error' : `http_${status}`
  }
}

// ---------------------------------------------------------------------------
// Payload sniffing
// ---------------------------------------------------------------------------

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isBackendErrorResponse(value: unknown): value is BackendErrorResponse {
  return (
    isRecord(value) &&
    typeof value.code === 'string' &&
    typeof value.message === 'string' &&
    typeof value.retryable === 'boolean'
  )
}

function isDetailResponse(value: unknown): value is BackendDetailResponse {
  return isRecord(value) && 'detail' in value
}

/** FastAPI's built-in validation array, in case one ever slips through. */
function flattenDetailArray(detail: unknown[]): string {
  const messages = detail
    .map((item) =>
      isRecord(item) && typeof item.msg === 'string' ? item.msg : null,
    )
    .filter((msg): msg is string => msg !== null)

  return messages.length > 0 ? messages.join('; ') : 'Request validation failed.'
}

/**
 * Turns a parsed error body into an `ApiError`. Shared by the axios and fetch
 * clients so both produce identical errors.
 */
export function apiErrorFromPayload(
  status: number | null,
  payload: unknown,
  requestIdHeader?: string | null,
): ApiError {
  // Shape A — the backend told us everything, including retryability.
  if (isBackendErrorResponse(payload)) {
    return new ApiError({
      message: payload.message,
      code: payload.code,
      status,
      retryable: payload.retryable,
      requestId: payload.request_id ?? requestIdHeader ?? null,
      source: 'backend',
    })
  }

  // Shape B — a bare HTTPException. Guardrail text is user-readable, so it is
  // shown verbatim rather than replaced with something generic.
  if (isDetailResponse(payload)) {
    const { detail } = payload
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? flattenDetailArray(detail)
          : 'The request failed.'

    return new ApiError({
      message,
      code: codeFromStatus(status),
      status,
      retryable: retryableFromStatus(status),
      requestId: requestIdHeader ?? null,
      source: 'backend',
    })
  }

  // An error status with a body we do not recognise (HTML error page, empty).
  return new ApiError({
    message:
      status === null
        ? 'The request failed for an unknown reason.'
        : `The server returned an unexpected ${status} response.`,
    code: codeFromStatus(status),
    status,
    retryable: retryableFromStatus(status),
    requestId: requestIdHeader ?? null,
    source: 'backend',
  })
}

/**
 * No response came back. In development this is nearly always the backend not
 * running, so the message says so instead of "Network Error".
 */
export function networkError(baseUrl: string, cause?: unknown): ApiError {
  const error = new ApiError({
    message: `Cannot reach the backend at ${baseUrl}. Is it running?`,
    code: 'network_unreachable',
    status: null,
    retryable: true,
    source: 'network',
  })
  if (cause !== undefined) error.cause = cause
  return error
}

export function timeoutError(baseUrl: string): ApiError {
  return new ApiError({
    message: `The backend at ${baseUrl} did not respond in time.`,
    code: 'timeout',
    status: null,
    retryable: true,
    source: 'network',
  })
}

/** For calls we refuse to make — see `updateWhitelistEntry`. */
export function clientError(message: string, code: string): ApiError {
  return new ApiError({
    message,
    code,
    status: null,
    retryable: false,
    source: 'client',
  })
}

/** Last-resort catch-all, so nothing non-`ApiError` escapes into components. */
export function normalizeError(error: unknown): ApiError {
  if (isApiError(error)) return error

  return new ApiError({
    message: error instanceof Error ? error.message : 'Something went wrong.',
    code: 'unknown_error',
    status: null,
    retryable: false,
    source: 'client',
  })
}
