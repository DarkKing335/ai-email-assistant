import { useMutation, useQueryClient } from '@tanstack/react-query'

import { Badge, Button, ErrorState, Skeleton } from '@/components/ui'
import { gmailAuthApi } from '@/services/api'
import { formatRelativeTime } from '@/utils/date'

import { GmailNotConfiguredNotice } from './GmailNotConfiguredNotice'
import { GMAIL_STATUS_KEY, useGmailAuthStatus } from './useGmailAuthStatus'

/**
 * Connect / disconnect the Google account the backend polls.
 *
 * The extension deliberately holds no Gmail credentials and requests no Gmail
 * scopes — it cannot read mail even in principle. Consent is granted to the
 * *backend*, which is what polls and will create drafts. This panel only
 * reports and triggers.
 */
export function GmailConnection() {
  const queryClient = useQueryClient()

  const status = useGmailAuthStatus()

  const disconnect = useMutation({
    mutationFn: gmailAuthApi.disconnectGmail,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: GMAIL_STATUS_KEY }),
  })

  if (status.isPending) return <Skeleton className="h-20 w-full" />

  if (status.isError) {
    return <ErrorState error={status.error} onRetry={() => void status.refetch()} />
  }

  const data = status.data

  // No client credentials on the backend — connecting is impossible until
  // someone sets them up, so say that instead of offering a button that 503s.
  if (!data.configured) return <GmailNotConfiguredNotice />

  if (!data.connected) {
    return (
      <div className="space-y-2 rounded-lg border border-ink-200 p-3 dark:border-ink-800">
        <div className="flex items-center gap-2">
          <Badge tone="neutral">Not connected</Badge>
        </div>
        <p className="text-xs leading-relaxed text-ink-500 dark:text-ink-400">
          No mail is being read. Connecting grants the backend permission to read
          your inbox and create drafts — it opens Google&rsquo;s consent screen in
          a new tab.
        </p>
        <Button
          size="sm"
          variant="primary"
          onClick={gmailAuthApi.openGmailConsent}
        >
          Connect Gmail
        </Button>
      </div>
    )
  }

  const pollerError = data.poller.last_error

  return (
    <div className="space-y-2 rounded-lg border border-ink-200 p-3 dark:border-ink-800">
      <div className="flex items-center justify-between gap-2">
        <Badge tone="success">Connected</Badge>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => disconnect.mutate()}
          disabled={disconnect.isPending}
        >
          {disconnect.isPending ? 'Disconnecting…' : 'Disconnect'}
        </Button>
      </div>

      <p className="font-mono text-xs break-all">{data.email_address}</p>

      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
        <dt className="text-ink-500 dark:text-ink-400">Checked</dt>
        <dd>
          {data.last_polled_at
            ? formatRelativeTime(data.last_polled_at)
            : 'not yet'}
        </dd>
        <dt className="text-ink-500 dark:text-ink-400">Every</dt>
        <dd>{data.poll_interval_seconds}s</dd>
        {data.poller.buffered > 0 && (
          <>
            <dt className="text-ink-500 dark:text-ink-400">Queued</dt>
            <dd>{data.poller.buffered}</dd>
          </>
        )}
      </dl>

      {/* Surfaced here because a failing poll is otherwise completely silent —
          mail simply stops arriving with no indication why. */}
      {pollerError && (
        <p className="rounded border border-red-200 bg-red-50 p-2 text-xs leading-relaxed text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
          {pollerError}
        </p>
      )}

      {disconnect.isError && (
        <ErrorState error={disconnect.error} />
      )}
    </div>
  )
}
