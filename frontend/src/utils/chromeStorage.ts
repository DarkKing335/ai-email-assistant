/**
 * Thin typed wrapper over `chrome.storage.local`.
 *
 * Falls back to an in-memory map when the Chrome APIs are absent, so the app
 * still runs when a bundle is opened as a plain page (`npm run dev` in a normal
 * tab, or a unit test) instead of throwing on the first read.
 *
 * `chrome.storage.local` rather than `sync`: the API base URL is machine-local
 * — syncing `127.0.0.1:8000` to another device would be actively wrong.
 */

const isAvailable =
  typeof chrome !== 'undefined' && Boolean(chrome.storage?.local)

const memoryFallback = new Map<string, unknown>()

export async function readStorage<T>(key: string): Promise<T | undefined> {
  if (!isAvailable) return memoryFallback.get(key) as T | undefined

  const stored = await chrome.storage.local.get(key)
  return stored[key] as T | undefined
}

export async function writeStorage<T>(key: string, value: T): Promise<void> {
  if (!isAvailable) {
    memoryFallback.set(key, value)
    return
  }
  await chrome.storage.local.set({ [key]: value })
}

export async function removeStorage(key: string): Promise<void> {
  if (!isAvailable) {
    memoryFallback.delete(key)
    return
  }
  await chrome.storage.local.remove(key)
}

/** Storage keys, in one place so the worker and panel cannot disagree. */
export const STORAGE_KEYS = {
  settings: 'settings',
  /** Watermark for "what is new" — written by the panel, read by the worker. */
  lastSeenAt: 'lastSeenAt',
  /**
   * The count the last notification was raised for.
   *
   * Must be persisted rather than held in a module variable: MV3 tears the
   * service worker down after ~30s idle, so in-memory state is gone by the
   * next alarm and every poll would re-notify for the same emails.
   */
  lastNotifiedCount: 'lastNotifiedCount',
  /**
   * The sender of the Gmail thread currently on screen.
   *
   * Written by the content script, read by the panel. Storage is used rather
   * than direct messaging because the two never run at the same time — the
   * panel may be opened long after the content script last saw a thread, and
   * `chrome.tabs.sendMessage` would additionally need a `tabs` permission the
   * extension does not otherwise want.
   */
  currentSender: 'currentSender',
} as const
