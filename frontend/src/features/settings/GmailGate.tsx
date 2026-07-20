import type { ReactNode } from 'react'

import connectGif from '@/assets/connect-gmail.gif'
import { Button, EmptyState, ErrorState, Skeleton } from '@/components/ui'
import { gmailAuthApi } from '@/services/api'

import { GmailNotConfiguredNotice } from './GmailNotConfiguredNotice'
import { useGmailAuthStatus } from './useGmailAuthStatus'

/**
 * Renders `children` only once a Gmail account is linked.
 *
 * Every panel behind this gate is a view of mail the backend has polled, so
 * before a connection exists they have nothing to show and each would render
 * its own empty state — four different ways of saying the same thing, none of
 * which mention the one action that fixes it. The gate says it once, with the
 * button attached.
 */
export function GmailGate({ children }: { children: ReactNode }) {
  const status = useGmailAuthStatus()

  if (status.isPending) return <Skeleton className="h-20 w-full" />

  if (status.isError) {
    return <ErrorState error={status.error} onRetry={() => void status.refetch()} />
  }

  if (!status.data.configured) return <GmailNotConfiguredNotice />

  if (!status.data.connected) {
    return (
      <EmptyState
        media={
          // Decorative only: `alt=""` keeps it out of the accessibility tree,
          // since the title and description already say everything. Sized in
          // rem rather than left intrinsic — the panel is resizable and narrow,
          // and the source is ~230px, which would crowd it.
          <img
            src={connectGif}
            alt=""
            className="h-28 w-auto select-none"
            draggable={false}
          />
        }
        title="Please connect to Gmail"
        description="Nothing can be shown until an account is linked. Connecting grants the backend permission to read your inbox and create drafts — it opens Google's consent screen in a new tab."
        action={
          <Button
            size="sm"
            variant="primary"
            onClick={gmailAuthApi.openGmailConsent}
          >
            Connect Gmail
          </Button>
        }
      />
    )
  }

  return <>{children}</>
}
