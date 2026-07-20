/**
 * "What is new" watermark.
 *
 * The backend has no unread concept — nothing server-side tracks what this user
 * has looked at. So "new" is defined entirely on the client: store the moment
 * the user last looked, then ask the logs endpoint how many rows arrived after
 * it. No backend work required.
 */

import {
  readStorage,
  removeStorage,
  STORAGE_KEYS,
  writeStorage,
} from './chromeStorage'
import { clearBadge } from './badge'

/**
 * Falls back to 24 hours ago on first run, rather than the epoch — a fresh
 * install should not announce every email the backend has ever processed.
 */
export async function getLastSeenAt(): Promise<string> {
  const stored = await readStorage<string>(STORAGE_KEYS.lastSeenAt)
  if (stored) return stored

  const fallback = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
  await writeStorage(STORAGE_KEYS.lastSeenAt, fallback)
  return fallback
}

/**
 * Called when the user views the list that shows new items. Advances the
 * watermark, drops the notification memory, and clears the badge.
 */
export async function markSeenNow(): Promise<void> {
  await writeStorage(STORAGE_KEYS.lastSeenAt, new Date().toISOString())
  await removeStorage(STORAGE_KEYS.lastNotifiedCount)
  await clearBadge()
}

export async function getLastNotifiedCount(): Promise<number> {
  return (await readStorage<number>(STORAGE_KEYS.lastNotifiedCount)) ?? 0
}

export async function setLastNotifiedCount(count: number): Promise<void> {
  await writeStorage(STORAGE_KEYS.lastNotifiedCount, count)
}
