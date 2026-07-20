/**
 * The settings shape and how to load it — deliberately free of zustand and
 * React.
 *
 * Both the side panel and the MV3 service worker need these values, but they
 * are separate JavaScript contexts that share nothing except
 * `chrome.storage.local`. The worker must not drag a state library in just to
 * read three fields; it is torn down after ~30s idle and restarted on every
 * alarm, so its bundle is on the hot path.
 */

import { DEFAULT_API_BASE_URL } from '@/services/config'

import { readStorage, STORAGE_KEYS } from './chromeStorage'

export type Settings = {
  apiBaseUrl: string
  /** How often the worker checks for new mail while the panel is closed. */
  backgroundIntervalMinutes: number
  notificationsEnabled: boolean
}

/** MV3 refuses to schedule an alarm below one minute; it silently clamps. */
export const MIN_BACKGROUND_INTERVAL_MINUTES = 1

export const BACKGROUND_INTERVAL_OPTIONS = [1, 5, 15, 30]

export const DEFAULT_SETTINGS: Settings = {
  apiBaseUrl: DEFAULT_API_BASE_URL,
  backgroundIntervalMinutes: 5,
  notificationsEnabled: true,
}

/**
 * Read persisted settings, merged over the defaults.
 *
 * Merging rather than replacing means a settings object written by an older
 * build that lacks a newer key still boots. The interval is clamped on read so
 * a bad stored value cannot produce an alarm Chrome will silently reject.
 */
export async function loadSettings(): Promise<Settings> {
  let stored: Partial<Settings> | undefined
  try {
    stored = await readStorage<Partial<Settings>>(STORAGE_KEYS.settings)
  } catch (error) {
    console.error('[ai-email-assistant] could not read settings', error)
  }

  const merged: Settings = { ...DEFAULT_SETTINGS, ...stored }
  merged.backgroundIntervalMinutes = Math.max(
    MIN_BACKGROUND_INTERVAL_MINUTES,
    merged.backgroundIntervalMinutes,
  )
  return merged
}
