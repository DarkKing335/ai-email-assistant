import { Badge, Button } from '@/components/ui'
import type { InboxDraft } from '@/types/api'
import { buildGmailThreadUrl, openGmailThread } from '@/utils/gmailLink'

/**
 * Confirmation that a reply draft exists, and a way to go read it.
 *
 * The draft text is deliberately *not* rendered here. It now lives in Gmail as
 * a real draft, and showing a second copy in the panel invites editing the one
 * that is never sent. The panel's job shrank to: say a draft was made, say
 * which template it used, and get you to it.
 */
export function DraftSection({
  draft,
  versionCount,
  threadIds,
}: {
  draft: InboxDraft
  versionCount: number
  /** Identifies the thread the draft was filed against. */
  threadIds: { gmail_thread_id: string | null; gmail_message_id: string }
}) {
  // Gmail has no working deep link to an individual draft, so this opens the
  // thread — where Gmail shows the draft inline under the conversation.
  const hasDraftInGmail = draft.gmail_draft_id !== null

  return (
    <div className="space-y-2 rounded-lg border border-ink-200 p-2.5 dark:border-ink-800">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-xs font-semibold tracking-wide uppercase text-ink-500 dark:text-ink-400">
          Draft reply
        </h4>
        <div className="flex items-center gap-1">
          <Badge tone="neutral">{draft.provider_used}</Badge>
          {versionCount > 1 && <Badge tone="neutral">v{draft.version}</Badge>}
        </div>
      </div>

      {hasDraftInGmail ? (
        <p className="text-xs leading-relaxed text-ink-700 dark:text-ink-300">
          A reply draft was created in Gmail, on this thread. Nothing has been
          sent.
        </p>
      ) : (
        // The reply text was still generated and stored — only the filing
        // failed. Saying "no draft" would be wrong; saying nothing would leave
        // a Check draft button that goes somewhere useless.
        <p className="rounded border border-amber-300 bg-amber-50 p-2 text-xs leading-relaxed text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
          The reply was generated but could not be filed in Gmail. Opening the
          thread will not show a draft.
        </p>
      )}

      <div className="flex items-center justify-between gap-2 pt-0.5">
        {/* The template is the one thing that says what *kind* of reply was
            written without showing the text itself. */}
        <span className="font-mono text-xs text-ink-500 dark:text-ink-400">
          {draft.template_id}
        </span>
        <Button
          size="sm"
          title="Open the thread in Gmail, where the draft is attached"
          onClick={() => openGmailThread(buildGmailThreadUrl(threadIds))}
        >
          Check draft
        </Button>
      </div>
    </div>
  )
}
