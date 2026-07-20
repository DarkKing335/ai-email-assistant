import { normalizeError } from '@/services/errors'

import { Button } from './Button'

/**
 * The single place a failed request is rendered.
 *
 * Two rules live here so no panel has to remember them:
 *
 *  1. **Retry is offered only when the backend said the error is retryable.**
 *     Showing a Retry button on a 409 duplicate or a 422 validation failure
 *     invites people to click it forever against something that cannot succeed.
 *
 *  2. **`message` is shown verbatim.** Guardrail and duplicate messages are
 *     written for humans; replacing them with something generic destroys the
 *     only useful information in the response.
 */
export function ErrorState({
  error,
  onRetry,
  className = '',
}: {
  error: unknown
  onRetry?: () => void
  className?: string
}) {
  const apiError = normalizeError(error)
  const canRetry = apiError.retryable && Boolean(onRetry)

  return (
    <div
      role="alert"
      className={`rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-500/30 dark:bg-red-500/10 ${className}`}
    >
      <p className="text-sm font-medium text-red-800 dark:text-red-200">
        {apiError.message}
      </p>

      {canRetry && (
        <Button size="sm" variant="secondary" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}

      {/* Collapsed by default: useful when reporting a problem, noise otherwise. */}
      <details className="mt-2 group">
        <summary className="cursor-pointer list-none text-[11px] text-red-700/70 select-none hover:underline dark:text-red-300/70">
          Details
        </summary>
        <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 font-mono text-[11px] text-red-700/80 dark:text-red-300/80">
          <dt>code</dt>
          <dd>{apiError.code}</dd>
          <dt>status</dt>
          <dd>{apiError.status ?? '—'}</dd>
          <dt>source</dt>
          <dd>{apiError.source}</dd>
          {apiError.requestId && (
            <>
              <dt>request</dt>
              <dd className="break-all">{apiError.requestId}</dd>
            </>
          )}
        </dl>
      </details>
    </div>
  )
}
