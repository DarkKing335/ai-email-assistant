/**
 * Toolbar badge. Written by the service worker, cleared by the panel — both
 * are extension contexts with `chrome.action` access, so no message passing is
 * needed for something this small.
 */

// brand-700 — the same step the primary button uses, and the only one dark
// enough to carry Chrome's white badge text. The icon PNGs are still the old
// indigo and no longer match; they need re-exporting.
const BADGE_BACKGROUND = '#0c7960'

const isAvailable = typeof chrome !== 'undefined' && Boolean(chrome.action)

export async function setBadgeCount(count: number): Promise<void> {
  if (!isAvailable) return

  // Chrome truncates anything past ~4 characters into unreadable mush.
  const text = count <= 0 ? '' : count > 99 ? '99+' : String(count)

  await chrome.action.setBadgeBackgroundColor({ color: BADGE_BACKGROUND })
  await chrome.action.setBadgeText({ text })
}

export async function clearBadge(): Promise<void> {
  if (!isAvailable) return
  await chrome.action.setBadgeText({ text: '' })
}
