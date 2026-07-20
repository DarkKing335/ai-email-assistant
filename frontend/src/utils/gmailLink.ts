/**
 * Deep links into the Gmail web UI.
 *
 * Opens a new tab rather than steering the one already docked beside the panel:
 * reusing that tab would need the `tabs` permission, which is prompted and
 * costs every installed user a re-approval on update. Not worth it for a
 * convenience link.
 */

/**
 * `#all/` rather than `#inbox/`: the thread may have been archived, and an
 * `#inbox/` link to archived mail lands on an empty view instead of the message.
 *
 * `/u/0/` — the numeric index — is the only account selector Gmail supports.
 * Addressing the mailbox by email (`/mail/u/someone@example.com/`) reads better
 * and *appears* to work, but it was always undocumented behaviour and Google
 * broke it in April 2026: the bare URL still opens, while anything with a
 * fragment appended fails with "Temporary Error (404)". Do not reintroduce it.
 *
 * The cost is that `0` is whichever account signed in first, which is not
 * necessarily the one the backend polls. There is no supported way to pick the
 * right index from here, so a multi-account user may land on the wrong mailbox.
 */
export function buildGmailThreadUrl(ids: {
  gmail_thread_id: string | null
  gmail_message_id: string
}): string {
  const target = ids.gmail_thread_id ?? ids.gmail_message_id
  return `https://mail.google.com/mail/u/0/#all/${target}`
}

/** `noopener` because the opened tab has no business reaching back into the panel. */
export function openGmailThread(url: string): void {
  window.open(url, '_blank', 'noopener')
}
