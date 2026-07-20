/**
 * The Gmail sender currently on screen, shared between the content script and
 * the side panel.
 */

import {
  readStorage,
  removeStorage,
  STORAGE_KEYS,
  writeStorage,
} from './chromeStorage'

export type CapturedSender = {
  email: string
  /** Display name, when Gmail rendered one. */
  name: string | null
  subject: string | null
  /** ISO-8601. Used to ignore a capture left over from an earlier session. */
  capturedAt: string
}

/**
 * How long a capture stays trustworthy.
 *
 * Storage persists across browser restarts, so without an expiry the panel
 * could offer to whitelist a sender from a thread read yesterday — presented as
 * "the email you are looking at", which would be wrong.
 */
const STALE_AFTER_MS = 5 * 60 * 1000

export async function writeCurrentSender(
  sender: Omit<CapturedSender, 'capturedAt'>,
): Promise<void> {
  await writeStorage<CapturedSender>(STORAGE_KEYS.currentSender, {
    ...sender,
    capturedAt: new Date().toISOString(),
  })
}

export async function clearCurrentSender(): Promise<void> {
  await removeStorage(STORAGE_KEYS.currentSender)
}

/** Returns the capture only while it is still fresh. */
export async function readCurrentSender(): Promise<CapturedSender | null> {
  const stored = await readStorage<CapturedSender>(STORAGE_KEYS.currentSender)
  if (!stored) return null

  const age = Date.now() - new Date(stored.capturedAt).getTime()
  if (Number.isNaN(age) || age > STALE_AFTER_MS) return null

  return stored
}
