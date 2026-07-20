import type { MatchLog } from '@/types/api'

const isAvailable =
  typeof chrome !== 'undefined' && Boolean(chrome.notifications)

/**
 * One notification id, reused. Chrome replaces a notification with the same id
 * rather than stacking, so a burst of processed mail updates one card instead
 * of burying the desktop.
 */
const NOTIFICATION_ID = 'ai-email-assistant-new-mail'

export async function notifyNewEmails(
  count: number,
  latest: MatchLog | undefined,
): Promise<void> {
  if (!isAvailable) return

  const title = count === 1 ? '1 new email processed' : `${count} new emails processed`
  const message = latest
    ? `Latest from ${latest.sender_email}${latest.subject ? ` — ${latest.subject}` : ''}`
    : 'Open the panel to review.'

  try {
    await chrome.notifications.create(NOTIFICATION_ID, {
      type: 'basic',
      iconUrl: chrome.runtime.getURL('icons/icon-128.png'),
      title,
      message,
      // Not `requireInteraction`: this is ambient information, not something
      // that should sit on screen until dismissed.
      priority: 0,
    })
  } catch (error) {
    console.error('[ai-email-assistant] notification failed', error)
  }
}
