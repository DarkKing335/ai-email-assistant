/**
 * Content script — Gmail pages only.
 *
 * Deliberately minimal. Because the backend polls Gmail server-side, the panel
 * renders backend data and barely needs Gmail's DOM. The single job here is
 * noticing which thread is open so the sender can be quick-added to the
 * whitelist.
 *
 * It reads. It never modifies Gmail's DOM, never touches message bodies, and
 * never sends anything anywhere except this extension's own storage.
 */

import { clearCurrentSender, writeCurrentSender } from '@/utils/currentSender'

import { readCurrentSender } from './readSender'

/**
 * Gmail mutates its DOM more or less continuously — a raw MutationObserver
 * callback fires hundreds of times a second while a thread renders. Everything
 * is funnelled through this delay so the expensive query runs once things
 * settle.
 */
const SETTLE_MS = 400

let timer: ReturnType<typeof setTimeout> | undefined
/** Guards redundant storage writes while the same thread stays open. */
let lastWritten: string | null = null

function capture(): void {
  const result = readCurrentSender()

  if (!result.found) {
    // Leaving a thread (back to the inbox list) should retract the offer, or
    // the panel would keep suggesting a sender that is no longer on screen.
    if (lastWritten !== null) {
      lastWritten = null
      void clearCurrentSender()
    }
    return
  }

  // Includes the subject so that moving between two threads from the same
  // sender still refreshes the capture.
  const signature = `${result.email}|${result.subject ?? ''}`
  if (signature === lastWritten) return

  lastWritten = signature
  void writeCurrentSender({
    email: result.email,
    name: result.name,
    subject: result.subject,
  })
}

function scheduleCapture(): void {
  if (timer) clearTimeout(timer)
  timer = setTimeout(capture, SETTLE_MS)
}

// Gmail is a single-page app: opening a thread changes the hash without a
// navigation, so the observer is what actually drives this. The hash listener
// is a cheap extra trigger for the common case.
const observer = new MutationObserver(scheduleCapture)
observer.observe(document.body, { childList: true, subtree: true })
window.addEventListener('hashchange', scheduleCapture)

// The script runs at document_idle, which can still precede Gmail's own
// rendering.
scheduleCapture()

/**
 * A capture describes what is on screen *now*. Leaving the page — closing the
 * tab, navigating away — makes it untrue, so it is retracted rather than left
 * behind for the panel to find.
 */
window.addEventListener('pagehide', () => {
  void clearCurrentSender()
})

export {}
